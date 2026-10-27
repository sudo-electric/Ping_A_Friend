import asyncio
import logging
import math
import time

from .transport import Result, build_transport
from .presence import record as record_presence, summarize
from .store import HISTORY_RETENTION_SECONDS

log = logging.getLogger(__name__)


class BusyError(Exception):
    pass


class Monitor:
    def __init__(self, settings, store, transports=None, clock=time.time):
        self.settings = settings
        self.store = store
        self.clock = clock
        self.transports = transports or {p.id: build_transport(p.transport) for p in settings.peers}
        self.lock = asyncio.Lock()
        self.progress = None
        self.last_error = None

    @property
    def max_gap(self):
        batches = sum(math.ceil(len(p.targets) / self.settings.batch_size) for p in self.settings.peers)
        return 2 * (self.settings.interval_seconds + batches * (self.settings.timeout_seconds + 1))

    async def run_once(self, peer_id=None, manual=False):
        if manual and self.lock.locked():
            raise BusyError("Checks are already running. Try again shortly.")
        async with self.lock:
            peers = [p for p in self.settings.peers if peer_id is None or p.id == peer_id]

            async def check(peer, target):
                try:
                    result = await asyncio.wait_for(
                        self.transports[peer.id].check(target, self.settings.timeout_seconds),
                        self.settings.timeout_seconds + 1,
                    )
                except asyncio.TimeoutError:
                    result = Result("unknown", detail="Transport exceeded its time budget")
                except Exception:
                    log.exception("Transport error for %s/%s", peer.id, target.id)
                    result = Result("unknown", detail="Observer error; inspect the server log")
                self.store.record(peer, target, result, self.clock(),
                                  self.settings.confirmation_seconds, self.max_gap)

            # Only create one small batch of tasks at a time, even for large lists.
            try:
                for peer in peers:
                    size = self.settings.batch_size
                    for start in range(0, len(peer.targets), size):
                        self.progress = {"group_id": peer.id, "group_name": peer.name,
                                         "batch": start // size + 1,
                                         "batches": math.ceil(len(peer.targets) / size)}
                        async with asyncio.TaskGroup() as batch:
                            for target in peer.targets[start:start + size]:
                                batch.create_task(check(peer, target))
                    snapshot = self.snapshot(peer.owner, peer.id)['peers'][0]
                    record_presence(self.store, peer, snapshot['availability'], self.clock(), self.max_gap, snapshot['targets'])
            finally:
                self.progress = None
            self.store.prune(self.clock() - self.settings.retention_days * 86400,
                             self.clock() - 400 * 86400,
                             self.clock() - HISTORY_RETENTION_SECONDS)
            self.last_error = None

    async def loop(self):
        while True:
            try:
                await self.run_once()
            except Exception:
                log.exception("Monitor cycle failed")
                self.last_error = "Observer cycle failed; inspect server logs"
            await asyncio.sleep(self.settings.interval_seconds)

    def snapshot(self, user, peer_id=None):
        now = self.clock()
        visible = [p for p in self.settings.peers if p.can_view(user) and (peer_id is None or p.id == peer_id)]
        peers = []
        for peer in visible:
            incidents = self.store.incidents(peer.id)
            active = {i["target"]: i for i in incidents if i["resolved_at"] is None}
            targets = []
            for target in peer.targets:
                result = self.store.latest(peer.id, target.id) or {
                    "status": "unknown", "latency_ms": None, "checked_at": None, "detail": "Waiting for first check"
                }
                if result["checked_at"] is not None and now - result["checked_at"] > self.max_gap:
                    result = {**result, "status": "stale", "detail": "Observer has not supplied a fresh measurement"}
                incident = active.get(target.id)
                targets.append({**target.model_dump(), **result, "incident": incident,
                                "confirmation_remaining": max(0, self.settings.confirmation_seconds - (now - incident["started_at"])) if incident and incident["confirmed_at"] is None else None})
            devices = [t for t in targets if t["kind"] == "device"]
            externals = [t for t in targets if t["kind"] == "external" and t["enabled"]]
            good = {"healthy", "delayed"}
            if peer.transport == "remote":
                status, advice = "unavailable", "Remote monitoring is a later phase. No remote connectivity or authorization has been established."
            elif any(not t["enabled"] for t in devices):
                status, advice = "unconfigured", "Open Settings to configure the devices in this group."
            elif any(t["status"] in {"unknown", "stale", "unavailable"} for t in devices + externals):
                status, advice = "unknown", "Some measurements are unavailable or stale; check the observer before diagnosing the network."
            elif all(t["status"] in good for t in devices):
                if not externals or all(t["status"] in good for t in externals):
                    status = "delayed" if any(t["status"] == "delayed" for t in devices + externals) else "healthy"
                    advice = "All devices in this group respond." if status == "healthy" else "Checks respond, but one or more exceed the latency threshold."
                    advice += " External paths are reachable." if externals else " Internet access is not tested by this group."
                else:
                    status, advice = "degraded", "Group devices respond; an external endpoint failed. Inspect the service, route, or ISP; this does not prove an internet outage."
            elif any(t["status"] in good for t in devices):
                status, advice = "degraded", "One or more LAN devices are unreachable. Inspect that device, its firewall, and its route."
            else:
                status, advice = "suspected_outage", "Every device in this group is unreachable from this observer. Check device power, routing/VPN, and filtering; this does not prove a whole-network outage."
            peers.append({"id": peer.id, "name": peer.name, "owner": peer.owner,
                          "availability": summarize(targets),
                          "transport": peer.transport, "status": status, "advice": advice,
                          "can_recheck": peer.can_recheck(user), "targets": targets, "incidents": incidents})
        return {"app_name": "Ping_A_Friend", "local_user": user, "now": now,
                "interval_seconds": self.settings.interval_seconds,
                "confirmation_seconds": self.settings.confirmation_seconds,
                "batch_size": self.settings.batch_size,
                "progress": self.progress if self.progress and any(p.id == self.progress["group_id"] for p in visible) else None,
                "checking": self.lock.locked(), "observer_error": self.last_error,
                "peers": peers, "notifications": self.store.notifications([p.id for p in visible], user, now)}
