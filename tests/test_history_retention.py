from app.notify import Notifier
from app.store import Store, HISTORY_RETENTION_SECONDS


def add_notification(store, created, owner='owner', peer='home', resolved=None):
    cursor = store.db.execute('''INSERT INTO incidents(peer,target,started_at,last_failure,confirmed_at,resolved_at,reason)
        VALUES(?,?,?,?,?,?,?)''', (peer, f'device-{created}-{owner}', created-90, created, created, resolved, 'test'))
    store.db.execute('INSERT INTO notifications(incident,peer,recipient,created_at,message) VALUES(?,?,?,?,?)',
                     (cursor.lastrowid, peer, owner, created, 'Test incident'))
    return cursor.lastrowid


def test_notification_history_includes_all_sixty_days_and_retains_owner_boundary(tmp_path):
    store = Store(tmp_path/'history.db')
    now = 100 * 86400
    cutoff = now - HISTORY_RETENTION_SECONDS
    with store.db:
        for i in range(75):
            add_notification(store, now-i)
        add_notification(store, cutoff)
        add_notification(store, cutoff-1)
        add_notification(store, now+1, owner='friend')
        add_notification(store, now+2, peer='other')
    rows = store.notifications(['home'], 'owner', now)
    assert len(rows) == 76
    assert rows[0]['created_at'] == now
    assert rows[-1]['created_at'] == cutoff
    store.close()


def test_sixty_day_cleanup_keeps_active_incidents_and_recent_notifications_past_raw_retention(tmp_path):
    store = Store(tmp_path/'cleanup.db')
    now = 100 * 86400
    with store.db:
        active = add_notification(store, now-61*86400)
        recent = add_notification(store, now-40*86400, resolved=now-35*86400)
    store.prune(now-30*86400, history_cutoff=now-HISTORY_RETENTION_SECONDS)
    assert store.db.execute('SELECT resolved_at FROM incidents WHERE id=?', (active,)).fetchone()['resolved_at'] is None
    assert store.db.execute('SELECT * FROM incidents WHERE id=?', (recent,)).fetchone()
    assert len(store.notifications(['home'], 'owner', now)) == 1
    assert store.db.execute('SELECT COUNT(*) FROM notifications').fetchone()[0] == 1
    store.prune(now, history_cutoff=now-39*86400)
    assert store.db.execute('SELECT * FROM incidents WHERE id=?', (recent,)).fetchone() is None
    assert store.db.execute('SELECT * FROM incidents WHERE id=?', (active,)).fetchone()
    store.close()


def test_delivery_history_has_no_thirty_row_limit_and_prunes_old_attempts(tmp_path):
    store = Store(tmp_path/'delivery.db')
    now = 100 * 86400
    notifier = Notifier(store, clock=lambda:now)
    with store.db:
        for i in range(75):
            store.db.execute("INSERT INTO deliveries(provider,event_key,message,created,state) VALUES('discord',?,'test',?,'accepted')", (f'test:{i}',now-i))
        for state in ('pending', 'accepted', 'failed', 'uncertain', 'sending'):
            store.db.execute("INSERT INTO deliveries(provider,event_key,message,created,state) VALUES('discord',?,'old',?,?)", (f'old:{state}',now-HISTORY_RETENTION_SECONDS-1,state))
    assert len(notifier.history()) == 75
    notifier.prune_history()
    assert store.db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0] == 76
    assert store.db.execute("SELECT state FROM deliveries WHERE event_key LIKE 'old:%'").fetchone()['state'] == 'sending'
    # Startup resolves ambiguous interrupted attempts, then applies retention.
    notifier = Notifier(store, clock=lambda:now)
    assert store.db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0] == 75
    store.close()
