import asyncio
import os
import hmac
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError

from .access import Access, COOKIE, SESSION_SECONDS, loopback_client, valid_host, local_addresses
from .config import StrictModel, Peer, Setup, SetupGroup, Settings, Target, config_path, load_settings, save_settings
from pydantic import Field

from .monitor import BusyError, Monitor
from .store import Store, HISTORY_RETENTION_SECONDS
from .transport import build_transport
from .notify import Notifier, DestinationInput, TestRateLimited
from .presence import report, month_bounds
from .paths import private_path
from . import __version__

STATIC = Path(__file__).parent / "static"


def create_app(settings=None, db_path=None, transports=None, background=True, settings_path=None,
               lan_mode=None, access_key_path=None):
    lan = os.environ.get("PAF_LAN_MODE", "0") == "1" if lan_mode is None else lan_mode
    @asynccontextmanager
    async def lifespan(app):
        app.state.access = Access(lan, access_key_path)
        config = settings or load_settings()
        store = Store(db_path or os.environ.get('PAF_DB') or private_path('ping_a_friend.sqlite3', 'data/ping_a_friend.sqlite3'))
        monitor = Monitor(config, store, transports)
        store.reset_pending(monitor.clock())
        store.prune(monitor.clock() - config.retention_days * 86400,
                    monitor.clock() - 400 * 86400, monitor.clock() - HISTORY_RETENTION_SECONDS)
        app.state.monitor = monitor
        app.state.observer_instance = uuid4().hex
        notifier = Notifier(store)
        app.state.notifier = notifier
        task = asyncio.create_task(monitor.loop()) if background else None
        delivery_task = asyncio.create_task(notifier.loop(monitor)) if background else None
        try:
            yield
        finally:
            if delivery_task:
                delivery_task.cancel()
                with suppress(asyncio.CancelledError):
                    await delivery_task
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            store.close()

    app = FastAPI(title="Ping_A_Friend", version=__version__, lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # FastAPI's default includes submitted values, which can contain keys,
        # addresses, or other private configuration in screenshots/error logs.
        return JSONResponse({'detail': [{'loc': e['loc'], 'msg': e['msg'], 'type': e['type']}
                                        for e in exc.errors()]}, status_code=422)

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if not valid_host(request.headers.get("host", ""), lan):
            return JSONResponse({"detail": "Invalid host header"}, status_code=400)
        if not lan and request.client and not loopback_client(request.client.host):
            return JSONResponse({"detail": "Network access is disabled. Start with the LAN launcher."}, status_code=403)
        # No CORS access; retain the same-origin boundary for network clients.
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin:
                parsed = urlsplit(origin)
                if parsed.netloc != request.headers.get("host") or parsed.scheme not in {"http", "https"}:
                    return JSONResponse({"detail": "Cross-origin mutation is blocked"}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Cross-site mutation is blocked"}, status_code=403)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"detail": "Send application/json"}, status_code=415)
        access = app.state.access
        public = request.url.path in {"/login", "/api/login", "/healthz", "/favicon.ico"} or request.url.path.startswith("/static/")
        authenticated = access.authenticated(request.cookies.get(access.cookie)) or access.authenticated(request.cookies.get(COOKIE)) if lan else True
        if lan and not public and not authenticated:
            if request.url.path == "/" and request.method == "GET":
                return RedirectResponse("/login", status_code=303, headers={"Cache-Control": "no-store"})
            return JSONResponse({"detail": "Sign in with this installation's access key"}, status_code=401,
                                headers={"Cache-Control": "no-store"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path in {"/", "/login"}:
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    class Login(StrictModel):
        key: str = Field(min_length=1, max_length=256)

    @app.get("/login", include_in_schema=False)
    async def login_page():
        if not lan:
            return RedirectResponse("/", status_code=303)
        return FileResponse(STATIC / "login.html")

    @app.post("/api/login", include_in_schema=False)
    async def login(payload: Login, request: Request):
        if not lan:
            raise HTTPException(404, "LAN sign-in is not enabled")
        access = app.state.access
        source = request.client.host if request.client else "unknown"
        if not access.allow_attempt(source):
            raise HTTPException(429, "Too many attempts. Wait a minute and try again.", headers={"Retry-After": "60"})
        if not hmac.compare_digest(payload.key.encode(), access.key.encode()) and not access.use_bootstrap(payload.key, source):
            raise HTTPException(401, "The access key is incorrect")
        access.attempts.pop(source, None)
        response = JSONResponse({"signed_in": True})
        response.set_cookie(access.cookie, access.new_session(), max_age=SESSION_SECONDS, httponly=True,
                            secure=request.url.scheme == "https", samesite="strict", path="/")
        return response

    @app.post("/api/logout", include_in_schema=False)
    async def logout(request: Request):
        response = JSONResponse({"signed_out": True})
        access = app.state.access
        response.delete_cookie(access.cookie, path="/", httponly=True, samesite="strict")
        if lan and access.authenticated(request.cookies.get(COOKIE)):
            response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
        return response

    @app.get('/api/access/pairing', include_in_schema=False)
    async def pairing_details(request: Request):
        if not lan:
            raise HTTPException(404, 'LAN pairing is not enabled')
        key = app.state.access.key
        suffix = f':{request.url.port}' if request.url.port else ''
        urls = [f'{request.url.scheme}://{address}{suffix}/login#key={key}' for address in local_addresses()]
        return {'key': key, 'links': urls}

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return RedirectResponse("/static/logo.svg", status_code=307)

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(STATIC / "index.html")

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/api/status")
    async def status():
        monitor = app.state.monitor
        return {**monitor.snapshot(monitor.settings.local_user), "network_access": "lan" if lan else "local",
                "observer_instance": app.state.observer_instance}

    @app.get('/api/reports/{month}')
    async def monthly_report(month: str):
        try:
            month_bounds(month)
        except ValueError:
            raise HTTPException(422, 'Use a month in YYYY-MM format') from None
        monitor = app.state.monitor
        return {'groups': [dict(name=p.name, **report(monitor.store, p.id, month, monitor.clock()))
                           for p in monitor.settings.peers if p.owner == monitor.settings.local_user and p.transport == 'local']}

    @app.get('/api/notifications/settings')
    async def notification_settings():
        return {'destinations': app.state.notifier.public(), 'deliveries': app.state.notifier.history()}

    @app.post('/api/notifications/settings')
    async def configure_notifications(request: Request):
        # Validation errors must not echo credentials or phone numbers.
        try:
            payload = DestinationInput.model_validate(await request.json())
            owned = {p.id for p in app.state.monitor.settings.peers if p.owner == app.state.monitor.settings.local_user and p.transport == 'local'}
            if not set(payload.groups) <= owned:
                raise HTTPException(422, 'Choose owned local groups')
            await app.state.notifier.configure(payload)
        except ValueError:
            raise HTTPException(422, 'Check the provider credentials and destination format. Existing secrets can be left blank.') from None
        return {'saved': True}

    @app.post('/api/notifications/test/{provider}')
    async def test_notification(provider: str, request: Request):
        notifier = app.state.notifier
        try:
            values = await request.json()
            if not isinstance(values, dict) or values.get('provider', provider) != provider:
                raise ValueError('Provider mismatch')
            payload = DestinationInput.model_validate({**values, 'provider': provider})
            result = await notifier.test(payload)
        except ValueError:
            raise HTTPException(422, 'Enter valid provider credentials and a destination before testing. Blank private fields use saved values.') from None
        except TestRateLimited as exc:
            raise HTTPException(429, str(exc)) from None
        return {**result, 'message': f"Test {result['state']}: {result['detail']}. Saved settings unchanged."}

    def setup_peer():
        config = app.state.monitor.settings
        return next((p for p in config.peers if p.owner == config.local_user and p.transport == "local"), None)

    @app.get("/api/setup")
    async def get_setup():
        peer = setup_peer()
        if peer is None:
            raise HTTPException(403, "This local user has no owned local network to configure")
        config = app.state.monitor.settings
        groups = []
        for group in config.peers:
            if group.owner != config.local_user or group.transport != "local":
                continue
            devices = [{"id": t.id, "name": t.name, "host": t.host if t.enabled else "",
                        "method": t.method, "port": t.port, "delayed_ms": t.delayed_ms}
                       for t in group.targets if t.kind == "device"]
            groups.append({"id": group.id, "name": group.name, "devices": devices,
                           "external_checks": any(t.enabled for t in group.targets if t.kind == "external")})
        return {"required": any(not d["host"] for g in groups for d in g["devices"]),
                "local_user": config.local_user, "batch_size": config.batch_size, "groups": groups,
                "network_name": peer.name, "devices": groups[0]["devices"]}

    @app.post("/api/setup")
    async def configure(payload: Setup):
        monitor = app.state.monitor
        if monitor.lock.locked():
            raise HTTPException(409, "Checks are running. Please save again in a moment.")
        async with monitor.lock:
            peer = setup_peer()
            if peer is None:
                raise HTTPException(403, "Only an owned local network can be configured")
            current = monitor.settings
            candidate = current.model_copy(deep=True)
            new_user = payload.local_user.strip()
            if new_user != current.local_user and any(
                p.owner == new_user or any(g.user == new_user for g in p.grants)
                for p in current.peers
            ):
                raise HTTPException(422, "That name already belongs to another configured owner")
            owned = {p.id: p for p in current.peers if p.owner == current.local_user and p.transport == "local"}
            requested = payload.groups
            legacy = requested is None
            if legacy:
                requested = [SetupGroup(id=peer.id, name=payload.network_name, devices=payload.devices,
                                        external_checks=any(t.enabled for t in peer.targets if t.kind == "external"))]
            updates = {}
            for group in requested:
                if group.id is not None and group.id not in owned:
                    raise HTTPException(403, "Only owned local groups can be configured")
                old = owned.get(group.id)
                group_id = group.id or "group-" + uuid4().hex[:16]
                old_devices = {t.id: t for t in old.targets if t.kind == "device"} if old else {}
                replacements = []
                for device in group.devices:
                    previous = old_devices.get(device.id)
                    if device.id is not None and previous is None:
                        raise HTTPException(422, "Device does not belong to this group")
                    if device.id is None:
                        previous = next((t for t in old_devices.values() if
                            (t.host.lower(), t.method, t.port) == (device.host.lower(), device.method, device.port)), None)
                    same = previous is not None and (previous.host.lower(), previous.method, previous.port) == (device.host.lower(), device.method, device.port)
                    replacements.append(Target(id=previous.id if same else "device-" + uuid4().hex[:16],
                        kind="device", enabled=True, **device.model_dump(exclude={"id"})))
                externals = [t.model_copy(deep=True) for t in old.targets if t.kind == "external"] if old else []
                if group.external_checks and not externals:
                    externals = [Target(id="cloudflare-path", name="External path · Cloudflare", kind="external", host="1.1.1.1", method="tcp", port=443, delayed_ms=250),
                                 Target(id="google-path", name="External path · Google DNS", kind="external", host="8.8.8.8", method="tcp", port=53, delayed_ms=250)]
                for target in externals:
                    target.enabled = group.external_checks
                updates[group_id] = Peer(id=group_id, name=group.name.strip(), owner=new_user,
                    grants=[g.model_copy(deep=True) for g in old.grants] if old else [], targets=replacements + externals)
            merged = []
            for group in candidate.peers:
                if group.id in updates:
                    merged.append(updates.pop(group.id))
                elif group.id not in owned or legacy:
                    merged.append(group)
            merged.extend(updates.values())
            candidate.peers = merged
            for group in candidate.peers:
                if group.owner == current.local_user:
                    group.owner = new_user
                for grant in group.grants:
                    if grant.user == current.local_user:
                        grant.user = new_user
            candidate.local_user = new_user
            candidate.batch_size = payload.batch_size
            try:
                candidate = Settings.model_validate(candidate.model_dump())
            except ValueError:
                raise HTTPException(422, "These settings conflict with an existing group, device, or grant")
            try:
                save_settings(candidate, settings_path or config_path())
            except OSError:
                raise HTTPException(500, "Settings could not be saved. Check that the application data folder is writable.")
            monitor.settings = candidate
            monitor.transports = {p.id: monitor.transports.get(p.id) or build_transport(p.transport) for p in candidate.peers}
        # The running observer uses the new settings on its next cycle; no restart.
        return {"saved": True, "message": "Settings saved. Monitoring will use them on the next check."}

    @app.post("/api/peers/{peer_id}/recheck")
    async def recheck(peer_id: str):
        monitor = app.state.monitor
        peer = next((p for p in monitor.settings.peers if p.id == peer_id and p.can_view(monitor.settings.local_user)), None)
        if peer is None:
            raise HTTPException(404, "Peer not found")
        if not peer.can_recheck(monitor.settings.local_user):
            raise HTTPException(403, "This local user has view-only access")
        if peer.transport != "local":
            raise HTTPException(501, "Remote transport and authorization are later phase")
        try:
            await monitor.run_once(peer_id, manual=True)
        except BusyError as exc:
            raise HTTPException(409, str(exc)) from exc
        return monitor.snapshot(monitor.settings.local_user)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
