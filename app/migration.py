"""Encrypted, explicit transfer to a fresh installation; no remote fetching."""
import base64
import json
import os
import math
import sqlite3

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .config import Settings, save_settings
from .notify import Destination

MAX_TRANSFER_BYTES = 32 * 1024 * 1024
TABLES = ('samples', 'incidents', 'notifications', 'availability', 'device_events',
          'status_events', 'alert_state', 'sms_usage', 'deliveries')


def cipher(key, salt):
    if not isinstance(key, str) or not 16 <= len(key) <= 256:
        raise ValueError('Use the original host pairing key (at least 16 characters)')
    derived = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                        iterations=600000).derive(key.encode())
    return Fernet(base64.urlsafe_b64encode(derived))


def export_data(monitor, notifier, key):
    db = monitor.store.db
    payload = {'version': 1, 'settings': monitor.settings.model_dump(),
               'providers': [d.model_dump() for d in notifier.destinations().values()],
               'tables': {table: [dict(r) for r in db.execute(f'SELECT * FROM {table}')]
                          for table in TABLES}}
    raw = json.dumps(payload, allow_nan=False).encode()
    if len(raw) > MAX_TRANSFER_BYTES // 2:
        raise ValueError('History is too large for the dashboard transfer limit')
    salt = os.urandom(16)
    return json.dumps({'format': 'Ping_A_Friend transfer v1',
                       'salt': base64.b64encode(salt).decode(),
                       'data': cipher(key, salt).encrypt(raw).decode()})


def read_transfer(archive, key):
    try:
        if len(archive.encode()) > MAX_TRANSFER_BYTES:
            raise ValueError()
        envelope = json.loads(archive)
        if envelope['format'] != 'Ping_A_Friend transfer v1':
            raise ValueError()
        salt = base64.b64decode(envelope['salt'], validate=True)
        if len(salt) != 16:
            raise ValueError()
        value = json.loads(cipher(key, salt).decrypt(envelope['data'].encode()))
        if value['version'] != 1 or set(value['tables']) != set(TABLES):
            raise ValueError()
        settings = Settings.model_validate(value['settings'])
        providers = [Destination.model_validate(p) for p in value['providers']]
        if len({p.provider for p in providers}) != len(providers):
            raise ValueError()
        for rows in value['tables'].values():
            if not isinstance(rows, list) or len(rows) > 500000:
                raise ValueError()
        return settings, providers, value['tables']
    except (ValueError, TypeError, KeyError, InvalidToken, UnicodeError):
        raise ValueError('Unable to unlock this transfer file. Check its pairing key and file version.') from None


def is_fresh(monitor, notifier):
    return (not any(t.enabled for p in monitor.settings.peers for t in p.targets)
            and not notifier.destinations()
            and not any(monitor.store.db.execute(f'SELECT 1 FROM {t} LIMIT 1').fetchone()
                        for t in ('incidents', 'notifications', 'deliveries'))
            and not any(json.loads(r[0]).get('status') != 'unconfigured'
                        for r in monitor.store.db.execute('SELECT result FROM samples')))


def restore_data(monitor, notifier, archive, key, path):
    if not is_fresh(monitor, notifier):
        raise ValueError('Restore is available only on a fresh installation with no monitoring or provider settings')
    settings, providers, tables = read_transfer(archive, key)
    db = monitor.store.db
    # Validate against our own schema in memory. The file supplies data only,
    # never SQL, filesystem paths, database schema, or installation keys.
    stage = sqlite3.connect(':memory:')
    stage.execute('PRAGMA foreign_keys=ON')
    try:
        for row in db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            stage.execute(row[0])
        for row in db.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"):
            stage.execute(row[0])
        for table in TABLES:
            columns = [r[1] for r in db.execute(f'PRAGMA table_info({table})')]
            rows = tables[table]
            types = {r[1]: (r[2], r[3] or r[5]) for r in db.execute(f'PRAGMA table_info({table})')}
            if any(not isinstance(r, dict) or set(r) != set(columns) for r in rows):
                raise ValueError('Transfer history does not match this application version')
            for r in rows:
                for column, (kind, required) in types.items():
                    v = r[column]
                    if v is None:
                        if required:
                            raise ValueError('Missing history value')
                    elif kind == 'TEXT' and not isinstance(v, str):
                        raise ValueError('Invalid history text')
                    elif kind == 'INTEGER' and (not isinstance(v, int) or isinstance(v, bool)):
                        raise ValueError('Invalid history count')
                    elif kind == 'REAL' and (not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)):
                        raise ValueError('Invalid history timestamp')
            # Interrupted/queued sends from the old machine must never replay.
            if table == 'deliveries':
                for r in rows:
                    if r['state'] in {'pending', 'sending'}:
                        r['state'], r['detail'] = 'cancelled', 'Transferred from another host; not replayed'
            sql = f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})'
            stage.executemany(sql, [[r[c] for c in columns] for r in rows])
        # Validate JSON sample records before they can reach dashboard rendering.
        for (result,) in stage.execute('SELECT result FROM samples'):
            r = json.loads(result)
            if not isinstance(r, dict) or r.get('status') not in {'healthy','delayed','failed','unknown','unconfigured','unavailable'}:
                raise ValueError('Invalid measurement history')
            ms = r.get('latency_ms')
            if ms is not None and (not isinstance(ms, (float,int)) or not 0 <= ms <= 1e9):
                raise ValueError('Invalid measurement time')
        stage.commit()
        old_settings = monitor.settings
        # One database transaction; a failed settings write rolls back history.
        try:
            with db:
                # Fresh observers may already have saved unknown availability.
                for table in reversed(TABLES):
                    db.execute(f'DELETE FROM {table}')
                for table in TABLES:
                    columns = [r[1] for r in db.execute(f'PRAGMA table_info({table})')]
                    sql = f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})'
                    db.executemany(sql, stage.execute(f'SELECT {",".join(columns)} FROM {table}'))
                for p in providers:
                    p.enabled = False
                    db.execute('INSERT INTO destinations VALUES(?,?,?)',
                               (p.provider, notifier.vault.encrypt(p.model_dump_json()), notifier.clock()))
                save_settings(settings, path)
        except Exception:
            save_settings(old_settings, path)
            raise
        monitor.settings = settings
        from .transport import build_transport
        monitor.transports = {p.id: build_transport(p.transport) for p in settings.peers}
        monitor.store.reset_pending(monitor.clock())
        monitor.last_error = None
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        raise ValueError('Transfer data is invalid or incompatible; no restore was completed') from None
    finally:
        stage.close()
