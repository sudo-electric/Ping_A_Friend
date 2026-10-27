"""Transport boundary. Local measurements never claim to observe a remote LAN."""
import asyncio
import platform
import re
import time
from dataclasses import dataclass, asdict
from typing import Protocol

from .config import Target
from .paths import external_environment


@dataclass
class Result:
    status: str
    latency_ms: float | None = None
    detail: str = ""

    def to_dict(self):
        return asdict(self)


class Transport(Protocol):
    async def check(self, target: Target, timeout: float) -> Result: ...


class LocalTransport:
    async def check(self, target, timeout):
        if not target.enabled:
            return Result("unconfigured", detail="Enable this device after setting its real LAN address")
        if target.method == "tcp":
            return await self.tcp(target, timeout)
        return await self.icmp(target, timeout)

    async def tcp(self, target, timeout):
        started = time.perf_counter()
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(target.host, target.port), timeout
            )
            ms = round((time.perf_counter() - started) * 1000, 2)
            writer.close()
            await writer.wait_closed()
            return Result("delayed" if ms > target.delayed_ms else "healthy", ms,
                          f"TCP port {target.port} accepted a connection (not ICMP)")
        except (OSError, asyncio.TimeoutError) as exc:
            return Result("failed", detail=f"TCP connection failed: {type(exc).__name__}")

    async def icmp(self, target, timeout):
        system = platform.system()
        if system == "Windows":
            args = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), target.host]
        else:
            # The outer timeout bounds DNS resolution and ping on Linux/macOS.
            args = ["ping", "-n", "-c", "1", target.host]
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env=external_environment()
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
            output = stdout.decode(errors="replace")
            match = re.search(r"time([=<])\s*([\d.,]+)\s*ms", output, re.I)
            if process.returncode != 0:
                error = stderr.decode(errors="replace").lower()
                if (system != "Windows" and process.returncode == 2) or any(
                    text in error for text in ("operation not permitted", "permission denied", "socket: ")
                ):
                    return Result("unknown", detail="ICMP probe error; check observer permissions, hostname resolution, and route")
                return Result("failed", detail="No ICMP reply; device, route, or firewall may be responsible")
            if not match:
                return Result("unknown", detail="Ping output could not be parsed; use TCP or an English ping locale")
            ms = float(match[2].replace(",", "."))
            detail = "ICMP round-trip" if match[1] == "=" else "ICMP round-trip upper bound"
            return Result("delayed" if ms > target.delayed_ms else "healthy", ms, detail)
        except FileNotFoundError:
            return Result("unknown", detail="ping executable is missing; install it or configure TCP")
        except asyncio.TimeoutError:
            return Result("failed", detail="ICMP timed out; device, route, or firewall may be responsible")
        except OSError as exc:
            return Result("unknown", detail=f"Unable to run ping: {type(exc).__name__}")
        finally:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()


class UnavailableRemoteTransport:
    async def check(self, target, timeout):
        return Result("unavailable", detail="Remote transport is not implemented. Twingate and remote authorization are later phase.")


def build_transport(name: str) -> Transport:
    if name == "local":
        return LocalTransport()
    if name == "remote":
        return UnavailableRemoteTransport()
    raise ValueError(f"Unsupported transport: {name}")
