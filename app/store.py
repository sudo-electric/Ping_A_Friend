import json
import sqlite3
from pathlib import Path
from .paths import private_file

HISTORY_RETENTION_SECONDS = 60 * 86400


class Store:
    def __init__(self, path):
        self.path = private_file(path, create=True)
        for suffix in ('-wal', '-shm', '-journal'):
            sidecar = Path(str(self.path) + suffix)
            if sidecar.exists() or sidecar.is_symlink():
                private_file(sidecar)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute('PRAGMA secure_delete=ON')
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
        INSERT OR IGNORE INTO schema_version VALUES (1);
        CREATE TABLE IF NOT EXISTS samples(
            id INTEGER PRIMARY KEY, peer TEXT NOT NULL, target TEXT NOT NULL,
            checked_at REAL NOT NULL, result TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS samples_time ON samples(checked_at);
        CREATE TABLE IF NOT EXISTS incidents(
            id INTEGER PRIMARY KEY, peer TEXT NOT NULL, target TEXT NOT NULL,
            started_at REAL NOT NULL, last_failure REAL NOT NULL,
            confirmed_at REAL, resolved_at REAL, reason TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS active_incident ON incidents(peer,target)
            WHERE resolved_at IS NULL;
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY, incident INTEGER UNIQUE NOT NULL REFERENCES incidents(id),
            peer TEXT NOT NULL, recipient TEXT NOT NULL, created_at REAL NOT NULL,
            message TEXT NOT NULL, delivery TEXT NOT NULL DEFAULT 'local-dashboard');
        CREATE INDEX IF NOT EXISTS notifications_created ON notifications(created_at);
        """)
        self.db.commit()
        from .presence import initialize
        initialize(self.db)
        Path(path).chmod(0o600)

    def reset_pending(self, now):
        # Do not count unobserved server downtime toward continuous failure.
        with self.db:
            self.db.execute("UPDATE incidents SET resolved_at=? WHERE resolved_at IS NULL AND confirmed_at IS NULL", (now,))

    def record(self, peer, target, result, now, confirmation, max_gap):
        with self.db:
            self.db.execute("INSERT INTO samples(peer,target,checked_at,result) VALUES(?,?,?,?)",
                            (peer.id, target.id, now, json.dumps(result.to_dict())))
            incident = self.db.execute("SELECT * FROM incidents WHERE peer=? AND target=? AND resolved_at IS NULL",
                                       (peer.id, target.id)).fetchone()
            if result.status in ("healthy", "delayed"):
                if incident:
                    self.db.execute("UPDATE incidents SET resolved_at=? WHERE id=?", (now, incident["id"]))
                return
            if result.status != "failed":
                # Unknown measurements cannot confirm a pending failure.
                if incident and incident["confirmed_at"] is None:
                    self.db.execute("UPDATE incidents SET resolved_at=? WHERE id=?", (now, incident["id"]))
                return
            if incident and incident["confirmed_at"] is None and now - incident["last_failure"] > max_gap:
                self.db.execute("UPDATE incidents SET resolved_at=? WHERE id=?", (now, incident["id"]))
                incident = None
            if incident is None:
                self.db.execute("INSERT INTO incidents(peer,target,started_at,last_failure,reason) VALUES(?,?,?,?,?)",
                                (peer.id, target.id, now, now, result.detail))
                return
            self.db.execute("UPDATE incidents SET last_failure=?, reason=? WHERE id=?", (now, result.detail, incident["id"]))
            if incident["confirmed_at"] is None and now - incident["started_at"] >= confirmation:
                self.db.execute("UPDATE incidents SET confirmed_at=? WHERE id=?", (now, incident["id"]))
                self.db.execute("INSERT OR IGNORE INTO notifications(incident,peer,recipient,created_at,message) VALUES(?,?,?,?,?)",
                                (incident["id"], peer.id, peer.owner, now,
                                 f"{target.name} at {target.host} has failed for at least {confirmation:g} seconds from {peer.name}'s observer. Check the device, firewall, and network; this does not prove the entire network is down."))

    def latest(self, peer, target):
        row = self.db.execute("SELECT * FROM samples WHERE peer=? AND target=? ORDER BY id DESC LIMIT 1", (peer, target)).fetchone()
        return {**json.loads(row["result"]), "checked_at": row["checked_at"]} if row else None

    def incidents(self, peer):
        return [dict(r) for r in self.db.execute("""SELECT * FROM incidents WHERE peer=? AND
            (resolved_at IS NULL OR id IN (SELECT id FROM incidents WHERE peer=? AND resolved_at IS NOT NULL ORDER BY id DESC LIMIT 50))
            ORDER BY id DESC""", (peer, peer))]

    def notifications(self, peers, user, now=None):
        if not peers:
            return []
        placeholders = ",".join("?" for _ in peers)
        cutoff = float('-inf') if now is None else now - HISTORY_RETENTION_SECONDS
        return [dict(r) for r in self.db.execute(
            f"SELECT * FROM notifications WHERE peer IN ({placeholders}) AND recipient=? AND created_at>=? ORDER BY created_at DESC,id DESC", (*peers, user, cutoff))]

    def prune(self, cutoff, summary_cutoff=None, history_cutoff=None):
        with self.db:
            self.db.execute("DELETE FROM samples WHERE checked_at < ?", (cutoff,))
            if history_cutoff is not None:
                self.db.execute('DELETE FROM notifications WHERE created_at < ?', (history_cutoff,))
            # Keep resolved incident rows while their 60-day notifications still
            # reference them, independently of the shorter raw-sample retention.
            self.db.execute("DELETE FROM incidents WHERE resolved_at < ? AND NOT EXISTS (SELECT 1 FROM notifications WHERE incident=incidents.id)", (cutoff,))
            if summary_cutoff is not None:
                self.db.execute('DELETE FROM availability WHERE expires < ?', (summary_cutoff,))
                self.db.execute('DELETE FROM device_events WHERE confirmed < ?', (summary_cutoff,))
                self.db.execute('DELETE FROM status_events WHERE created < ?', (summary_cutoff,))

    def close(self):
        self.db.close()
