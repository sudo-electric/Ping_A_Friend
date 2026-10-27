"""Durable slow-check observations, separate from reachability incidents."""
import math


def initialize(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS delay_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, group_id TEXT NOT NULL,
            target_id TEXT NOT NULL, name TEXT NOT NULL, method TEXT NOT NULL,
            port INTEGER NOT NULL, checked_at REAL NOT NULL,
            latency_ms REAL NOT NULL, threshold_ms REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS delay_group_time ON delay_events(group_id,checked_at);
        CREATE INDEX IF NOT EXISTS delay_target_time ON delay_events(group_id,target_id,checked_at);
        CREATE TABLE IF NOT EXISTS delay_log_info(
            id INTEGER PRIMARY KEY CHECK(id=1), started REAL NOT NULL);
    ''')
    db.commit()


def record(db, peer, target, result, now):
    if target.kind != 'device' or not target.enabled:
        return
    db.execute('INSERT OR IGNORE INTO delay_log_info VALUES(1,?)', (now,))
    ms = result.latency_ms
    if result.status != 'delayed' or ms is None or not math.isfinite(ms) or ms < 0:
        return
    db.execute('''INSERT INTO delay_events(group_id,target_id,name,method,port,checked_at,latency_ms,threshold_ms)
                  VALUES(?,?,?,?,?,?,?,?)''',
               (peer.id,target.id,target.name,target.method,target.port,now,ms,target.delayed_ms))


def report(db, group_id, start, stop):
    rows = db.execute('''SELECT target_id,method,COUNT(*) AS count,AVG(latency_ms) AS average_ms,
                        MAX(latency_ms) AS worst_ms,MIN(checked_at) AS first_at,MAX(checked_at) AS last_at
                        FROM delay_events WHERE group_id=? AND checked_at>=? AND checked_at<?
                        GROUP BY target_id,method ORDER BY count DESC,target_id''', (group_id,start,stop)).fetchall()
    devices = []
    for row in rows:
        name = db.execute('''SELECT name FROM delay_events WHERE group_id=? AND target_id=?
                             AND checked_at>=? AND checked_at<? ORDER BY checked_at DESC,id DESC LIMIT 1''',
                          (group_id,row['target_id'],start,stop)).fetchone()[0]
        devices.append(dict(row, name=name, average_ms=round(row['average_ms'],2)))
    recent = [dict(r) for r in db.execute('''SELECT target_id,name,method,port,checked_at,latency_ms,threshold_ms
              FROM delay_events WHERE group_id=? AND checked_at>=? AND checked_at<?
              ORDER BY checked_at DESC,id DESC LIMIT 50''', (group_id,start,stop))]
    info = db.execute('SELECT started FROM delay_log_info WHERE id=1').fetchone()
    return {'count':sum(d['count'] for d in devices),
            'worst_ms':max((d['worst_ms'] for d in devices),default=None),
            'devices':devices, 'recent':recent, 'recent_limit':50,
            'logging_started_at':info['started'] if info else None}
