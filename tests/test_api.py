import pytest
from app.config import Grant
from app.main import create_app
from conftest import FakeTransport, api_client

pytestmark = pytest.mark.anyio


async def test_dashboard_recheck_and_permissions(settings, tmp_path):
    home = settings.peers[0]
    friend = home.model_copy(deep=True)
    friend.id, friend.owner, friend.name = "friend", "friend", "Friend"
    parent = friend.model_copy(deep=True)
    parent.id, parent.name = "parents", "Parents"
    friend.grants = [Grant(user="owner", recheck=False)]
    settings.peers.extend([friend, parent])
    transports = {p.id: FakeTransport() for p in settings.peers}
    async with api_client(create_app(settings, tmp_path / "api.db", transports, background=False)) as client:
        assert (await client.get("/")).status_code == 200
        assert "Ping_A_Friend" in (await client.get("/")).text
        assert (await client.get("/static/style.css")).status_code == 200
        assert (await client.get("/healthz")).json()["status"] == "ok"
        snapshot = (await client.get("/api/status")).json()
        assert {p["id"] for p in snapshot["peers"]} == {"home", "friend"}
        assert (await client.post("/api/peers/parents/recheck", json={})).status_code == 404
        assert (await client.post("/api/peers/friend/recheck", json={})).status_code == 403
        response = (await client.post("/api/peers/home/recheck", json={}))
        assert response.status_code == 200
        assert response.json()["peers"][0]["status"] == "healthy"
        assert transports["home"].calls == ["one", "two", "outside"]
        assert not transports["friend"].calls
        assert {p["id"] for p in (await client.get("/api/status?user=friend")).json()["peers"]} == {"home", "friend"}


async def test_remote_is_honestly_unavailable(settings, tmp_path):
    settings.peers[0].transport = "remote"
    async with api_client(create_app(settings, tmp_path / "remote.db", background=False)) as client:
        assert (await client.get("/api/status")).json()["peers"][0]["status"] == "unavailable"
        assert (await client.post("/api/peers/home/recheck", json={})).status_code == 501


async def test_host_and_csrf_boundary(settings, tmp_path):
    async with api_client(create_app(settings, tmp_path / "security.db", {"home": FakeTransport()}, background=False)) as client:
        assert (await client.get("/api/status", headers={"host": "attacker.example"})).status_code == 400
        assert (await client.post("/api/peers/home/recheck", json={}, headers={"origin": "https://attacker.example"})).status_code == 403
        assert (await client.post("/api/peers/home/recheck", json={}, headers={"sec-fetch-site": "cross-site"})).status_code == 403
        assert (await client.post("/api/peers/home/recheck", content="{}")).status_code == 415
        assert (await client.post("/api/peers/home/recheck", json={}, headers={"origin": "http://localhost"})).status_code == 200


async def test_two_devices_required_for_healthy_and_stale_not_healthy(settings, tmp_path):
    transport = FakeTransport()
    app = create_app(settings, tmp_path / "classification.db", {"home": transport}, background=False)
    async with api_client(app) as client:
        transport.overrides["two"] = "failed"
        assert (await client.post("/api/peers/home/recheck", json={})).json()["peers"][0]["status"] == "degraded"
        transport.overrides["one"] = "failed"
        assert (await client.post("/api/peers/home/recheck", json={})).json()["peers"][0]["status"] == "suspected_outage"
        transport.overrides = {"outside": "failed"}
        assert (await client.post("/api/peers/home/recheck", json={})).json()["peers"][0]["status"] == "degraded"
        transport.overrides = {"one": "delayed"}
        assert (await client.post("/api/peers/home/recheck", json={})).json()["peers"][0]["status"] == "delayed"
        now = app.state.monitor.clock()
        app.state.monitor.clock = lambda: now + 1000
        snapshot = (await client.get("/api/status")).json()["peers"][0]
        assert snapshot["status"] == "unknown"
        assert all(t["status"] == "stale" for t in snapshot["targets"])


async def test_manual_recheck_during_cycle_returns_conflict(settings, tmp_path):
    app = create_app(settings, tmp_path / "busy.db", {"home": FakeTransport()}, background=False)
    async with api_client(app) as client:
        await app.state.monitor.lock.acquire()
        try:
            assert (await client.post("/api/peers/home/recheck", json={})).status_code == 409
        finally:
            app.state.monitor.lock.release()


async def test_observer_restart_changes_instance_so_open_dashboards_reset_address_privacy(settings, tmp_path):
    app = create_app(settings, tmp_path / 'restart-privacy.db', {'home': FakeTransport()}, background=False)
    async with api_client(app) as client:
        first = (await client.get('/api/status')).json()['observer_instance']
        assert first
        assert (await client.get('/api/status')).json()['observer_instance'] == first
    async with api_client(app) as client:
        assert (await client.get('/api/status')).json()['observer_instance'] != first
