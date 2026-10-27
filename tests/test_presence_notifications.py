import asyncio
import json
from urllib.parse import parse_qs

import pytest

from app.main import create_app
from app.monitor import Monitor
from app.notify import Destination, DestinationInput, DeliveryError, Notifier, send
from app.presence import month_bounds, record, report, summarize
from app.store import Store
from conftest import FakeTransport, api_client


def test_availability_does_not_confuse_latency_external_failure_or_unknown():
    def target(status, kind='device', enabled=True):
        return dict(status=status, kind=kind, enabled=enabled)
    assert summarize([target('healthy'), target('delayed'), target('failed', 'external')])['state'] == 'green'
    assert summarize([target('healthy'), target('failed')]) == dict(state='yellow', reachable=1, total=2, failed=1, unknown=0)
    assert summarize([target('failed'), target('failed')])['state'] == 'red'
    assert summarize([target('healthy'), target('stale')])['state'] == 'unknown'
    assert summarize([target('healthy', enabled=False)])['state'] == 'unknown'


def test_monthly_time_clips_gaps_and_survives_raw_retention(settings, tmp_path):
    store = Store(tmp_path / 'history.db')
    start, _ = month_bounds('2026-10')
    peer = settings.peers[0]
    green = dict(state='green', reachable=2, total=2)
    yellow = dict(state='yellow', reachable=1, total=2)
    record(store, peer, green, start, 20, [])
    record(store, peer, yellow, start + 10, 20, [])
    record(store, peer, yellow, start + 20, 20, [])
    store.prune(start + 1000)
    data = report(store, 'home', '2026-10', start + 100)
    assert data['seconds'] == dict(green=10, yellow=30, red=0, unknown=60)
    assert data['available_seconds'] == 40
    assert data['device_availability_seconds'] == 25
    assert data['period_seconds'] == 100
    store.close()


def test_confirmed_group_transitions_and_incidents_once_across_restart(settings, tmp_path):
    path = tmp_path / 'history.db'
    store = Store(path)
    now = [month_bounds('2026-10')[0]]
    transport = FakeTransport()
    monitor = Monitor(settings, store, {'home': transport}, clock=lambda: now[0])
    asyncio.run(monitor.run_once())
    transport.overrides['one'] = 'failed'
    now[0] += 1
    asyncio.run(monitor.run_once())
    assert store.db.execute('SELECT COUNT(*) FROM status_events').fetchone()[0] == 0
    for _ in range(6):
        now[0] += 15
        asyncio.run(monitor.run_once())
    assert store.db.execute('SELECT state FROM status_events').fetchone()[0] == 'yellow'
    assert report(store, 'home', '2026-10', now[0])['device_incidents'] == 1
    store.close()
    store = Store(path)
    monitor = Monitor(settings, store, {'home': transport}, clock=lambda: now[0])
    now[0] += 15
    asyncio.run(monitor.run_once())
    assert store.db.execute('SELECT COUNT(*) FROM status_events').fetchone()[0] == 1
    assert report(store, 'home', '2026-10', now[0])['device_incidents'] == 1
    transport.overrides = {}
    now[0] += 15
    asyncio.run(monitor.run_once())
    assert [r[0] for r in store.db.execute('SELECT state FROM status_events ORDER BY id')] == ['yellow', 'green']
    store.close()


@pytest.mark.anyio
async def test_queue_dedup_retries_and_no_secret_leak(settings, tmp_path):
    store = Store(tmp_path / 'delivery.db')
    now = [10.]
    calls = []
    def failure(destination, message):
        calls.append(message)
        raise DeliveryError('Provider returned HTTP 503', retry=True)
    notifier = Notifier(store, sender=failure, clock=lambda: now[0])
    await notifier.configure(DestinationInput(provider='discord', enabled=True, secret='https://discord.com/api/webhooks/123/secret'))
    assert 'secret' not in json.dumps(notifier.public()).replace('"secret": ""', '')
    with store.db:
        notifier.enqueue('discord', 'test:1', 'hello')
        notifier.enqueue('discord', 'test:1', 'hello')
    for _ in range(3):
        await notifier.deliver_once()
        now[0] += 200
    assert calls == ['hello'] * 3
    assert notifier.history()[0]['state'] == 'failed'
    assert notifier.history()[0]['attempts'] == 3
    store.close()


@pytest.mark.anyio
async def test_reconfiguration_cancels_queued_messages_and_preserves_secret(tmp_path):
    store = Store(tmp_path / 'delivery.db')
    notifier = Notifier(store)
    await notifier.configure(DestinationInput(provider='telegram', enabled=True, secret='123:abc', address='456'))
    with store.db:
        notifier.enqueue('telegram', 'test:1', 'hello')
    await notifier.configure(DestinationInput(provider='telegram', enabled=False))
    assert notifier.history()[0]['state'] == 'cancelled'
    await notifier.configure(DestinationInput(provider='telegram', enabled=True))
    assert notifier.destinations()['telegram'].secret == '123:abc'
    store.close()


@pytest.mark.anyio
async def test_notification_api_redacts_credentials_rejects_redirects_and_throttles(settings, tmp_path):
    app = create_app(settings, tmp_path / 'api.db', {'home': FakeTransport()}, background=False)
    async with api_client(app) as client:
        app.state.notifier.sender = lambda d, m: None
        secret = 'https://discord.com/api/webhooks/123/private-token'
        payload = dict(provider='discord', enabled=True, secret=secret)
        assert (await client.post('/api/notifications/settings', json=payload)).status_code == 200
        result = await client.get('/api/notifications/settings')
        assert 'private-token' not in result.text
        assert (await client.post('/api/notifications/test/discord', json={})).status_code == 200
        assert (await client.post('/api/notifications/test/discord', json={})).status_code == 429
        payload['secret'] = 'https://discord.com.evil.test/api/webhooks/123/private-token'
        result = await client.post('/api/notifications/settings', json=payload)
        assert result.status_code == 422 and 'private-token' not in result.text
        assert (await client.get('/api/reports/invalid')).status_code == 422
        assert (await client.get('/api/reports/2026-10')).json()['groups'][0]['timezone'] == 'UTC'


@pytest.mark.parametrize('provider', ['discord', 'slack', 'telegram', 'twilio'])
def test_provider_wire_formats_without_network(provider, monkeypatch):
    from app import notify
    configs = {
        'discord': dict(secret='https://discord.com/api/webhooks/123/token'),
        'slack': dict(secret='https://hooks.slack.com/services/A/B/C'),
        'telegram': dict(secret='123:token', address='456'),
        'twilio': dict(secret='f'*32, account='AC'+'a'*32, sender='+15551234567', address='+15557654321')}
    captured = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b'{"ok":true}'
    class Opener:
        def open(self, request, timeout):
            captured.append(request)
            assert timeout == 10
            return Response()
    monkeypatch.setattr(notify, 'build_opener', lambda handler: Opener())
    send(Destination(provider=provider, enabled=True, **configs[provider]), 'hello @everyone')
    request = captured[0]
    if provider == 'twilio':
        assert parse_qs(request.data.decode())['Body'] == ['hello @everyone']
        assert request.get_header('Authorization').startswith('Basic ')
    else:
        payload = json.loads(request.data)
        assert payload['content' if provider == 'discord' else 'text'] == 'hello @everyone'
        if provider == 'discord':
            assert payload['allowed_mentions'] == {'parse': []}
            assert request.full_url.endswith('?wait=true')


@pytest.mark.anyio
async def test_lan_notification_and_reporting_endpoints_require_owner(settings, tmp_path):
    app = create_app(settings, tmp_path / 'auth.db', background=False, lan_mode=True, access_key_path=tmp_path/'key')
    async with api_client(app) as client:
        for path in ('/api/notifications/settings', '/api/reports/2026-10'):
            assert (await client.get(path)).status_code == 401
        assert (await client.post('/api/notifications/test/discord', json={})).status_code == 401


@pytest.mark.anyio
async def test_sms_daily_request_limit_includes_tests_and_resets_at_utc_midnight(tmp_path):
    store = Store(tmp_path / 'limit.db')
    now = [100.]
    calls = []
    notifier = Notifier(store, sender=lambda d, m: calls.append(m), clock=lambda: now[0])
    await notifier.configure(DestinationInput(provider='twilio', enabled=True, daily_limit=1,
        account='AC'+'a'*32, secret='f'*32, sender='+15551234567', address='+15557654321'))
    with store.db:
        notifier.enqueue('twilio', 'test:1', 'first')
        notifier.enqueue('twilio', 'test:2', 'second')
    await notifier.deliver_once()
    assert calls == ['first']
    assert notifier.history()[0]['state'] == 'skipped'
    now[0] = 86401
    with store.db:
        notifier.enqueue('twilio', 'test:3', 'new day')
    await notifier.deliver_once()
    assert calls == ['first', 'new day']
    store.close()


@pytest.mark.anyio
async def test_latest_status_wins_recovery_opt_in_and_repeated_collection_is_idempotent(settings, tmp_path):
    store = Store(tmp_path / 'collection.db')
    now = [100.]
    notifier = Notifier(store, sender=lambda d, m: None, clock=lambda: now[0])
    await notifier.configure(DestinationInput(provider='telegram', enabled=True, secret='123:abc', address='456'))
    with store.db:
        store.db.execute("INSERT INTO status_events(group_id,state,created,message) VALUES('home','yellow',101,'yellow')")
        store.db.execute("INSERT INTO status_events(group_id,state,created,message) VALUES('home','red',102,'red')")
    now[0] = 103
    notifier.collect(settings)
    notifier.collect(settings)
    assert store.db.execute('SELECT message FROM deliveries').fetchall()[0][0] == 'red'
    assert len(notifier.history()) == 1
    with store.db:
        store.db.execute("INSERT INTO status_events(group_id,state,created,message) VALUES('home','green',104,'green')")
    now[0] = 105
    notifier.collect(settings)
    assert len(notifier.history()) == 1
    settings.peers[0].owner = 'other'
    notifier.collect(settings)
    assert notifier.history()[0]['state'] == 'cancelled'
    store.close()


def test_pruned_incident_id_reuse_does_not_erase_new_device_incidents(settings, tmp_path):
    from app.transport import Result
    store = Store(tmp_path / 'reuse.db')
    peer, target = settings.peers[0], settings.peers[0].targets[0]
    start = month_bounds('2026-10')[0]
    for offset in (0, 1000):
        for delta in (0, 15, 30, 45, 60, 75, 90):
            store.record(peer, target, Result('failed'), start + offset + delta, 90, 40)
        incident = store.incidents(peer.id)[0]
        record(store, peer, dict(state='red', reachable=0, total=1), start + offset + 90, 40,
               [dict(id=target.id, name=target.name, kind='device', enabled=True, status='failed', incident=incident)])
        store.record(peer, target, Result('healthy', 1), start + offset + 91, 90, 40)
        store.prune(start + offset + 100, history_cutoff=start + offset + 100)
    assert report(store, 'home', '2026-10', start+2000)['device_incidents'] == 2
    store.close()


@pytest.mark.anyio
async def test_monthly_summary_is_queued_once_and_timeout_is_not_replayed(settings, tmp_path):
    store = Store(tmp_path / 'monthly.db')
    start, end = month_bounds('2026-10')
    record(store, settings.peers[0], dict(state='yellow', reachable=1, total=2), start, 3600, [])
    now = [end + 10]
    def uncertain(destination, message):
        raise DeliveryError('Delivery uncertain', uncertain=True)
    notifier = Notifier(store, sender=uncertain, clock=lambda: now[0])
    await notifier.configure(DestinationInput(provider='telegram', enabled=True, monthly=True, secret='123:abc', address='456'))
    notifier.collect(settings)
    notifier.collect(settings)
    assert len(notifier.history()) == 1
    message = store.db.execute('SELECT message FROM deliveries').fetchone()[0]
    assert '2026-10 (UTC)' in message and 'partial 1.00h' in message
    await notifier.deliver_once()
    assert notifier.history()[0]['state'] == 'uncertain'
    now[0] += 120
    await notifier.deliver_once()
    assert notifier.history()[0]['attempts'] == 1
    store.close()


def test_more_than_fifty_active_device_failures_remain_visible_and_counted(settings, tmp_path):
    from app.config import Target
    settings.peers[0].targets = [Target(id=f'd{i}', name=f'Device {i}', kind='device', host=f'10.0.0.{i+1}') for i in range(60)]
    store = Store(tmp_path / 'many.db')
    now = [month_bounds('2026-10')[0]]
    monitor = Monitor(settings, store, {'home': FakeTransport('failed')}, clock=lambda: now[0])
    asyncio.run(monitor.run_once())
    now[0] += 90
    asyncio.run(monitor.run_once())
    assert len(store.incidents('home')) == 60
    assert report(store, 'home', '2026-10', now[0])['device_incidents'] == 60
    assert store.db.execute('SELECT state FROM status_events').fetchone()[0] == 'red'
    store.close()


@pytest.mark.anyio
async def test_draft_webhook_can_be_tested_before_save_without_enabling_or_storing_secrets(settings, tmp_path):
    app = create_app(settings, tmp_path / 'draft.db', background=False)
    async with api_client(app) as client:
        calls = []
        app.state.notifier.sender = lambda d, m: calls.append(d.secret)
        secret = 'https://discord.com/api/webhooks/123/draft-token'
        response = await client.post('/api/notifications/test/discord', json={'provider':'discord', 'enabled':False, 'secret':secret})
        assert response.status_code == 200
        assert response.json()['state'] == 'accepted'
        assert calls == [secret]
        assert app.state.notifier.destinations() == {}
        assert 'draft-token' not in response.text
        assert 'draft-token' not in (await client.get('/api/notifications/settings')).text
        assert 'draft-token' not in '\n'.join(app.state.monitor.store.db.iterdump())
        assert (await client.post('/api/notifications/test/discord', json={'secret':secret})).status_code == 429


@pytest.mark.anyio
async def test_test_uses_new_draft_instead_of_saved_destination_and_keeps_saved_values(settings, tmp_path):
    app = create_app(settings, tmp_path / 'draft-change.db', background=False)
    async with api_client(app) as client:
        old = 'https://discord.com/api/webhooks/123/old-token'
        new = 'https://discord.com/api/webhooks/456/new-token'
        await client.post('/api/notifications/settings', json={'provider':'discord', 'enabled':True, 'secret':old})
        calls = []
        app.state.notifier.sender = lambda d, m: calls.append(d.secret)
        response = await client.post('/api/notifications/test/discord', json={'secret':new})
        assert response.json()['state'] == 'accepted'
        assert calls == [new]
        assert app.state.notifier.destinations()['discord'].secret == old
        assert 'new-token' not in '\n'.join(app.state.monitor.store.db.iterdump())


@pytest.mark.anyio
async def test_draft_test_failure_is_reported_without_retry_or_saving(settings, tmp_path):
    app = create_app(settings, tmp_path / 'draft-failure.db', background=False)
    async with api_client(app) as client:
        def reject(d, m):
            raise DeliveryError('Provider returned HTTP 503', retry=True)
        app.state.notifier.sender = reject
        response = await client.post('/api/notifications/test/slack', json={'secret':'https://hooks.slack.com/services/A/B/C'})
        assert response.json()['state'] == 'failed'
        assert 'HTTP 503' in response.json()['message']
        await app.state.notifier.deliver_once()
        assert app.state.notifier.history()[0]['attempts'] == 1
        assert not app.state.notifier.destinations()
        bad = await client.post('/api/notifications/test/discord', json={'secret':'https://evil.example/private-token'})
        assert bad.status_code == 422 and 'private-token' not in bad.text
