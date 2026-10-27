import asyncio

import pytest
from pydantic import ValidationError

from app.config import Settings, Target
from app.transport import LocalTransport, UnavailableRemoteTransport


@pytest.mark.parametrize("host", ["-c", "127.0.0.1; touch x", "https://example.org", "$(whoami)", "", "bad host"])
def test_unsafe_targets_rejected(host):
    with pytest.raises(ValidationError):
        Target(id="one", name="One", kind="device", host=host)


def test_tcp_real_socket_success_and_refusal():
    async def run():
        async def accept(reader, writer):
            writer.close()
            await writer.wait_closed()
        server = await asyncio.start_server(accept, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        target = Target(id="one", name="One", kind="device", host="127.0.0.1", method="tcp", port=port)
        result = await LocalTransport().check(target, 1)
        assert result.status == "healthy"
        assert result.latency_ms is not None
        assert "not ICMP" in result.detail
        server.close()
        await server.wait_closed()
        result = await LocalTransport().check(target, 1)
        assert result.status == "failed"
        assert result.latency_ms is None
    asyncio.run(run())


def test_disabled_device_and_remote_do_not_call_network():
    target = Target(id="one", name="One", kind="device", host="192.168.1.10", enabled=False)
    assert asyncio.run(LocalTransport().check(target, 1)).status == "unconfigured"
    target.enabled = True
    result = asyncio.run(UnavailableRemoteTransport().check(target, 1))
    assert result.status == "unavailable"
    assert result.latency_ms is None


def test_duplicate_devices_and_peer_ids_rejected(settings):
    raw = settings.model_dump()
    raw["peers"][0]["targets"][1]["host"] = raw["peers"][0]["targets"][0]["host"]
    with pytest.raises(ValidationError):
        Settings.model_validate(raw)
    raw = settings.model_dump()
    raw["peers"].append(raw["peers"][0])
    with pytest.raises(ValidationError):
        Settings.model_validate(raw)
