import json

import pytest
from app.config import Grant
from app.main import create_app
from conftest import FakeTransport, api_client

pytestmark = pytest.mark.anyio


def payload():
    return {"local_user": "alex", "network_name": "Alex's home", "devices": [
        {"name": "Router", "host": "192.168.1.1", "method": "icmp"},
        {"name": "NAS", "host": "192.168.1.20", "method": "tcp", "port": 443},
    ]}


async def test_first_launch_save_monitor_and_restart(settings, tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setenv("PAF_CONFIG", str(path))
    app = create_app(db_path=tmp_path / "first.db", background=False)
    async with api_client(app) as client:
        setup = (await client.get("/api/setup")).json()
        assert setup["required"]
        assert all(d["host"] == "" for d in setup["devices"])
        assert not path.exists()  # Opening or skipping setup doesn't write anything.
        app.state.monitor.transports = {"home": FakeTransport()}
        assert (await client.post("/api/setup", json=payload())).status_code == 200
        assert not (await client.get("/api/setup")).json()["required"]
        result = (await client.post("/api/peers/home/recheck", json={})).json()
        assert result["local_user"] == "alex"
        assert result["peers"][0]["status"] == "healthy"
    async with api_client(create_app(db_path=tmp_path / "first.db", background=False)) as client:
        setup = (await client.get("/api/setup")).json()
        assert setup["local_user"] == "alex"
        assert setup["network_name"] == "Alex's home"
        assert setup["devices"][1]["host"] == "192.168.1.20"
        assert not setup["required"]


async def test_changes_do_not_reuse_old_device_measurements(settings, tmp_path):
    app = create_app(settings, tmp_path / "history.db", {"home": FakeTransport()}, background=False,
                     settings_path=tmp_path / "config.json")
    async with api_client(app) as client:
        (await client.post("/api/peers/home/recheck", json={}))
        before = (await client.get("/api/status")).json()["peers"][0]
        assert (await client.post("/api/setup", json=payload())).status_code == 200
        after = (await client.get("/api/status")).json()["peers"][0]
        devices = [t for t in after["targets"] if t["kind"] == "device"]
        assert all(t["checked_at"] is None for t in devices)
        assert not {t["id"] for t in devices} & {t["id"] for t in before["targets"]}
        assert next(t for t in after["targets"] if t["kind"] == "external")["checked_at"] is not None
        same_ids = [t["id"] for t in devices]
        assert (await client.post("/api/setup", json=payload())).status_code == 200
        assert [t.id for t in app.state.monitor.settings.peers[0].targets if t.kind == "device"] == same_ids


async def test_invalid_setup_leaves_live_and_saved_settings_intact(settings, tmp_path):
    path = tmp_path / "config.json"
    path.write_text(settings.model_dump_json())
    original = path.read_text()
    async with api_client(create_app(settings, tmp_path / "validation.db", background=False, settings_path=path)) as client:
        for host in ["192.168.1.1", "https://example.com", "-bad", "localhost; id"]:
            bad = payload()
            bad["devices"][1]["host"] = host
            assert (await client.post("/api/setup", json=bad)).status_code == 422
            assert path.read_text() == original
            assert (await client.get("/api/status")).json()["local_user"] == "owner"
        bad = payload()
        bad["local_user"] = " "
        assert (await client.post("/api/setup", json=bad)).status_code == 422


async def test_write_failure_and_busy_cycle_leave_current_settings(settings, tmp_path, monkeypatch):
    app = create_app(settings, tmp_path / "failure.db", background=False, settings_path=tmp_path / "config.json")
    async with api_client(app) as client:
        await app.state.monitor.lock.acquire()
        try:
            assert (await client.post("/api/setup", json=payload())).status_code == 409
        finally:
            app.state.monitor.lock.release()
        def fail(*args):
            raise PermissionError("read only")
        monkeypatch.setattr("app.main.save_settings", fail)
        assert (await client.post("/api/setup", json=payload())).status_code == 500
        assert (await client.get("/api/status")).json()["local_user"] == "owner"


async def test_setup_cannot_modify_another_owner_or_acquire_their_identity(settings, tmp_path):
    other = settings.peers[0].model_copy(deep=True)
    other.id, other.owner = "friend", "friend"
    other.grants = [Grant(user="owner")]
    settings.peers.append(other)
    path = tmp_path / "config.json"
    async with api_client(create_app(settings, tmp_path / "owners.db", background=False, settings_path=path)) as client:
        bad = payload()
        bad["local_user"] = "friend"
        assert (await client.post("/api/setup", json=bad)).status_code == 422
        assert (await client.post("/api/setup", json=payload())).status_code == 200
        saved = json.loads(path.read_text())
        assert saved["peers"][1]["owner"] == "friend"
        assert saved["peers"][1]["targets"] == other.model_dump()["targets"]
        assert saved["peers"][1]["grants"] == [{"user": "alex", "recheck": False}]
    settings.peers = [other]
    async with api_client(create_app(settings, tmp_path / "readonly.db", background=False, settings_path=path)) as client:
        assert (await client.get("/api/setup")).status_code == 403
        assert (await client.post("/api/setup", json=payload())).status_code == 403


async def test_setup_uses_existing_browser_security_boundary(settings, tmp_path):
    path = tmp_path / "config.json"
    async with api_client(create_app(settings, tmp_path / "csrf.db", background=False, settings_path=path)) as client:
        assert (await client.post("/api/setup", json=payload(), headers={"origin": "https://attacker.example"})).status_code == 403
        assert (await client.post("/api/setup", json=payload(), headers={"sec-fetch-site": "cross-site"})).status_code == 403
        assert (await client.post("/api/setup", content=json.dumps(payload()))).status_code == 415
        assert not path.exists()
