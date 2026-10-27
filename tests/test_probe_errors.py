import asyncio

from app.config import Target
from app.transport import LocalTransport


def test_icmp_parse_and_permission_errors(monkeypatch):
    class Process:
        returncode = 0
        stderr = b""
        stdout = b"64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=1.234 ms"

        async def communicate(self):
            return self.stdout, self.stderr

    process = Process()
    async def spawn(*args, **kwargs):
        assert args[0] == "ping"
        return process
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr("app.transport.platform.system", lambda: "Linux")
    target = Target(id="one", name="One", kind="device", host="127.0.0.1")
    assert asyncio.run(LocalTransport().check(target, 1)).latency_ms == 1.234
    process.returncode = 2
    process.stderr = b"ping: socket: Operation not permitted"
    assert asyncio.run(LocalTransport().check(target, 1)).status == "unknown"
    process.returncode = 1
    process.stderr = b""
    assert asyncio.run(LocalTransport().check(target, 1)).status == "failed"


def test_icmp_timeout_reaps_process(monkeypatch):
    class Process:
        returncode = None
        killed = False
        reaped = False

        async def communicate(self):
            await asyncio.sleep(10)

        def kill(self):
            self.killed = True

        async def wait(self):
            self.returncode = -9
            self.reaped = True

    process = Process()
    async def spawn(*args, **kwargs):
        return process
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    target = Target(id="one", name="One", kind="device", host="127.0.0.1")
    result = asyncio.run(LocalTransport().check(target, 0.01))
    assert result.status == "failed"
    assert process.killed and process.reaped


def test_notifications_are_owner_scoped(settings, tmp_path):
    from app.store import Store
    from app.transport import Result

    store = Store(tmp_path / "notifications.db")
    peer, target = settings.peers[0], settings.peers[0].targets[0]
    for now in range(0, 91, 15):
        store.record(peer, target, Result("failed"), now, 90, 36)
    assert len(store.notifications(["home"], "owner")) == 1
    assert store.notifications(["home"], "friend") == []
    assert store.notifications(["parents"], "owner") == []
    store.close()
