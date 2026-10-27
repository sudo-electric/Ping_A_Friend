from contextlib import asynccontextmanager

import httpx
import pytest

from app.config import Settings
from app.transport import Result


@pytest.fixture
def settings():
    return Settings.model_validate({"local_user": "owner", "peers": [{
        "id": "home", "name": "Home", "owner": "owner", "targets": [
            {"id": "one", "name": "One", "kind": "device", "host": "192.168.1.10"},
            {"id": "two", "name": "Two", "kind": "device", "host": "192.168.1.11"},
            {"id": "outside", "name": "Outside", "kind": "external", "host": "1.1.1.1", "method": "tcp"}
        ]
    }]})


class FakeTransport:
    def __init__(self, status="healthy"):
        self.status = status
        self.overrides = {}
        self.calls = []

    async def check(self, target, timeout):
        self.calls.append(target.id)
        value = self.overrides.get(target.id, self.status)
        return Result(value, 12.5 if value in {"healthy", "delayed"} else None, "test measurement")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@asynccontextmanager
async def api_client(app):
    # Exercise lifespan and the full ASGI boundary without a thread or network socket.
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            yield client
