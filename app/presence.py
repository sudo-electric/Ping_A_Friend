"""Device availability, separate from latency, internet checks and user presence."""
import calendar
from datetime import datetime, timezone


def summarize(targets):
    devices = [t for t in targets if t['kind'] == 'device' and t['enabled']]
    reachable = sum(t['status'] in {'healthy', 'delayed'} for t in devices)
    failed = sum(t['status'] == 'failed' for t in devices)
    total = len(devices)
    state = ('unknown' if not total or reachable + failed != total else
             'green' if reachable == total else 'yellow' if reachable else 'red')
    return {'state': state, 'reachable': reachable, 'total': total,
            'failed': failed, 'unknown': total - reachable - failed}


def month_bounds(month):
    start = datetime.strptime(month, '%Y-%m').replace(tzinfo=timezone.utc)
    if start.strftime('%Y-%m') != month:
        raise ValueError('Use YYYY-MM')
    days = calendar.monthrange(start.year, start.month)[1]
    return start.timestamp(), start.timestamp() + days * 86400


def initialize(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS availability(
            id INTEGER PRIMARY KEY, group_id TEXT NOT NULL, start REAL NOT NULL,
            end REAL NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL,
            reachable INTEGER NOT NULL, total INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS availability_group_time ON availability(group_id,start);
        CREATE TABLE IF NOT EXISTS device_events(
            incident_id INTEGER NOT NULL, group_id TEXT NOT NULL, target_id TEXT NOT NULL,
            name TEXT NOT NULL, confirmed REAL NOT NULL, started REAL NOT NULL,
            PRIMARY KEY(group_id,target_id,started));
        CREATE TABLE IF NOT EXISTS status_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, group_id TEXT NOT NULL, state TEXT NOT NULL,
            created REAL NOT NULL, message TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS device_events_group_time ON device_events(group_id,confirmed);
        CREATE INDEX IF NOT EXISTS status_events_group_time ON status_events(group_id,created);
        CREATE TABLE IF NOT EXISTS alert_state(
            group_id TEXT PRIMARY KEY, state TEXT NOT NULL);
    ''')
    db.commit()


def record(store, peer, summary, now, max_gap, targets):
    db = store.db
    with db:
        # Merge only contiguous identical observations. Expiry limits how far a
        # sample can account for time while the observer is stopped.
        old = db.execute('SELECT * FROM availability WHERE group_id=? ORDER BY id DESC LIMIT 1', (peer.id,)).fetchone()
        same = old and old['expires'] >= now and all(old[k] == summary[k] for k in ('state', 'reachable', 'total'))
        if same:
            db.execute('UPDATE availability SET end=?,expires=? WHERE id=?', (now, now + max_gap, old['id']))
        else:
            if old:
                db.execute('UPDATE availability SET expires=MIN(expires,?) WHERE id=?', (now, old['id']))
            db.execute('INSERT INTO availability(group_id,start,end,expires,state,reachable,total) VALUES(?,?,?,?,?,?,?)',
                       (peer.id, now, now, now + max_gap, summary['state'], summary['reachable'], summary['total']))
        for t in targets:
            incident = t.get('incident')
            if t['kind'] == 'device' and incident and incident['confirmed_at'] is not None:
                db.execute('INSERT OR IGNORE INTO device_events VALUES(?,?,?,?,?,?)',
                           (incident['id'], peer.id, t['id'], t['name'], incident['confirmed_at'], incident['started_at']))
        # Unknown resets the transition baseline; it never fabricates a recovery.
        state = summary['state']
        previous = db.execute('SELECT state FROM alert_state WHERE group_id=?', (peer.id,)).fetchone()
        confirmed = state in {'green', 'unknown'} or all(
            t.get('incident') and t['incident']['confirmed_at'] is not None
            for t in targets if t['kind'] == 'device' and t['enabled'] and t['status'] == 'failed')
        if confirmed and (not previous or previous['state'] != state):
            if state in {'yellow', 'red'} or (state == 'green' and previous and previous['state'] in {'yellow', 'red'}):
                message = (f"{peer.name}: {summary['reachable']}/{summary['total']} devices reachable. " +
                           ('Check your devices.' if state == 'yellow' else
                            'No devices are reachable from this observer. Please check in.' if state == 'red' else
                            'All devices are reachable again.'))
                db.execute('INSERT INTO status_events(group_id,state,created,message) VALUES(?,?,?,?)', (peer.id, state, now, message))
            db.execute('INSERT OR REPLACE INTO alert_state VALUES(?,?)', (peer.id, state))


def report(store, group_id, month, now):
    start, end = month_bounds(month)
    stop = min(end, now)
    seconds = dict(green=0., yellow=0., red=0., unknown=0.)
    weighted = 0.
    if stop > start:
        rows = store.db.execute('SELECT * FROM availability WHERE group_id=? AND start<? AND expires>? ORDER BY start', (group_id, stop, start))
        for row in rows:
            duration = max(0, min(row['expires'], stop) - max(row['start'], start))
            seconds[row['state']] += duration
            if row['total'] and row['state'] != 'unknown':
                weighted += duration * row['reachable'] / row['total']
        seconds['unknown'] += max(0, stop - start - sum(seconds.values()))
    devices = [dict(r) for r in store.db.execute('''SELECT target_id, MAX(name) AS name, COUNT(*) AS incidents
        FROM device_events WHERE group_id=? AND confirmed>=? AND confirmed<? AND confirmed<=? GROUP BY target_id''', (group_id, start, end, now))]
    from .delay_history import report as delay_report
    # Include an observation exactly at now, but never one at next month's boundary.
    import math
    delays = delay_report(store.db, group_id, start, min(end, math.nextafter(now, math.inf)))
    return {'delays': delays, 'month': month, 'timezone': 'UTC', 'group_id': group_id, 'seconds': seconds,
            'available_seconds': seconds['green'] + seconds['yellow'],
            'available_days': (seconds['green'] + seconds['yellow']) / 86400,
            'device_availability_seconds': weighted, 'device_incidents': sum(d['incidents'] for d in devices),
            'devices': devices, 'period_seconds': max(0, stop - start)}
