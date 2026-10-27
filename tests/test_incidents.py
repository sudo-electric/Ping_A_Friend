import asyncio

from app.monitor import Monitor
from app.store import Store
from app.transport import Result
from conftest import FakeTransport


def test_confirmation_recovery_dedup_and_new_incident(settings, tmp_path):
    store = Store(tmp_path / "test.db")
    peer, target = settings.peers[0], settings.peers[0].targets[0]
    failure = Result("failed", detail="No reply")
    for now in range(0, 90, 15):
        store.record(peer, target, failure, now, 90, 36)
    assert not store.notifications(["home"], "owner")
    assert store.incidents("home")[0]["confirmed_at"] is None
    store.record(peer, target, failure, 90, 90, 36)
    assert store.incidents("home")[0]["confirmed_at"] == 90
    store.record(peer, target, failure, 105, 90, 36)
    assert len(store.notifications(["home"], "owner")) == 1
    store.record(peer, target, Result("healthy", 5), 110, 90, 36)
    assert store.incidents("home")[0]["resolved_at"] == 110
    store.record(peer, target, failure, 120, 90, 36)
    assert store.incidents("home")[0]["started_at"] == 120
    assert store.incidents("home")[0]["confirmed_at"] is None
    store.close()


def test_manual_recheck_does_not_reset_failure_window(settings, tmp_path):
    store = Store(tmp_path / "test.db")
    clock = [0]
    transport = FakeTransport("failed")
    monitor = Monitor(settings, store, {"home": transport}, clock=lambda: clock[0])
    for now in [0, 15, 30, 45, 60, 75, 89]:
        clock[0] = now
        asyncio.run(monitor.run_once("home", manual=True))
    assert not store.notifications(["home"], "owner")
    assert monitor.snapshot("owner")["peers"][0]["targets"][0]["confirmation_remaining"] == 1
    clock[0] = 90
    asyncio.run(monitor.run_once("home", manual=True))
    assert len(store.notifications(["home"], "owner")) == 3
    assert store.incidents("home")[0]["started_at"] == 0
    transport.status = "healthy"
    clock[0] = 91
    asyncio.run(monitor.run_once("home", manual=True))
    assert all(i["resolved_at"] == 91 for i in store.incidents("home"))
    store.close()


def test_restart_gap_and_unknown_do_not_confirm(settings, tmp_path):
    path = tmp_path / "test.db"
    peer, target = settings.peers[0], settings.peers[0].targets[0]
    store = Store(path)
    store.record(peer, target, Result("failed"), 0, 90, 36)
    store.close()
    store = Store(path)
    store.reset_pending(100)
    store.record(peer, target, Result("failed"), 101, 90, 36)
    assert store.incidents("home")[0]["started_at"] == 101
    store.record(peer, target, Result("failed"), 200, 90, 36)
    assert store.incidents("home")[0]["started_at"] == 200
    store.record(peer, target, Result("unknown"), 215, 90, 36)
    assert store.incidents("home")[0]["resolved_at"] == 215
    assert not store.notifications(["home"], "owner")
    store.close()


def test_pending_recovery_prevents_notification_and_delays_are_not_outages(settings, tmp_path):
    store = Store(tmp_path / "test.db")
    peer, target = settings.peers[0], settings.peers[0].targets[0]
    store.record(peer, target, Result("failed"), 0, 90, 36)
    store.record(peer, target, Result("delayed", 300), 30, 90, 36)
    assert store.incidents("home")[0]["resolved_at"] == 30
    assert not store.notifications(["home"], "owner")
    store.close()


def test_retention_keeps_active_incidents(settings, tmp_path):
    store = Store(tmp_path / "test.db")
    peer, target = settings.peers[0], settings.peers[0].targets[0]
    for now in range(0, 91, 15):
        store.record(peer, target, Result("failed"), now, 90, 36)
    store.prune(1000)
    assert len(store.incidents("home")) == 1
    assert len(store.notifications(["home"], "owner")) == 1
    store.record(peer, target, Result("healthy", 1), 1001, 90, 36)
    store.prune(1002, history_cutoff=1002)
    assert not store.incidents("home")
    assert not store.notifications(["home"], "owner")
    store.close()
