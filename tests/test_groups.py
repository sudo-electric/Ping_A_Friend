import asyncio

import pytest
from pydantic import ValidationError

from app.config import Settings, Target
from app.main import create_app
from app.monitor import Monitor
from app.store import Store
from app.transport import Result
from conftest import FakeTransport, api_client


def device(number, **extra):
    return {"name": f"Device {number}", "host": f"device-{number}.test", **extra}


def configuration(batch_size=2):
    return {"local_user": "owner", "batch_size": batch_size, "groups": [
        {"name": "Basic tests", "devices": [device(i) for i in range(4)]},
        {"name": "Extended IoT", "devices": [device(i) for i in range(4, 7)]},
    ]}


@pytest.mark.anyio
async def test_groups_save_edit_reorder_and_restart(settings, tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    app = create_app(settings, tmp_path / "group.db", background=False, settings_path=path)
    async with api_client(app) as client:
        assert (await client.post('/api/setup', json=configuration(3))).status_code == 200
        setup = (await client.get('/api/setup')).json()
        assert setup['batch_size'] == 3
        assert [g['name'] for g in setup['groups']] == ['Basic tests', 'Extended IoT']
        assert [len(g['devices']) for g in setup['groups']] == [4, 3]
        assert all(not g['external_checks'] for g in setup['groups'])
        ids = [g['id'] for g in setup['groups']]
        app.state.monitor.transports = {id: FakeTransport() for id in ids}
        snapshot = (await client.post(f'/api/peers/{ids[0]}/recheck', json={})).json()
        assert snapshot['peers'][0]['status'] == 'healthy'
        assert all(t['checked_at'] is None for t in snapshot['peers'][1]['targets'])
        setup['groups'][0]['devices'].reverse()
        before = setup['groups'][0]['devices'][0]['id']
        payload = {k: setup[k] for k in ['local_user', 'batch_size', 'groups']}
        assert (await client.post('/api/setup', json=payload)).status_code == 200
        assert app.state.monitor.settings.peers[0].targets[0].id == before
        assert app.state.monitor.store.latest(ids[0], before) is not None
        # Change the endpoint under a stable row ID: it must get a fresh history ID.
        payload['groups'][0]['devices'][0]['host'] = 'changed.test'
        assert (await client.post('/api/setup', json=payload)).status_code == 200
        assert app.state.monitor.settings.peers[0].targets[0].id != before
        assert app.state.monitor.store.latest(ids[0], before) is not None
    monkeypatch.setenv('PAF_CONFIG', str(path))
    async with api_client(create_app(db_path=tmp_path / 'group.db', background=False)) as client:
        setup = (await client.get('/api/setup')).json()
        assert setup['batch_size'] == 3
        assert setup['groups'][0]['devices'][0]['host'] == 'changed.test'
        assert len(setup['groups'][1]['devices']) == 3


@pytest.mark.parametrize('size', [2, 3, 4, 5])
def test_strict_batches_wait_for_slowest_and_share_limit_across_groups(settings, tmp_path, size):
    async def run():
        settings.batch_size = size
        settings.peers[0].targets = [Target(id=f'd-{i}', kind='device', **device(i)) for i in range(size + 1)]
        second = settings.peers[0].model_copy(deep=True)
        second.id = 'iot'
        second.targets = [Target(id='last', kind='device', **device(99))]
        settings.peers.append(second)
        gate = asyncio.Event()
        started = []
        running = 0
        peak = 0

        class Controlled:
            async def check(self, target, timeout):
                nonlocal running, peak
                started.append(target.id)
                running += 1
                peak = max(peak, running)
                try:
                    if target.id == 'd-0':
                        await gate.wait()
                    else:
                        await asyncio.sleep(0)
                    return Result('healthy', 1)
                finally:
                    running -= 1

        store = Store(tmp_path / f'batch-{size}.db')
        monitor = Monitor(settings, store, {p.id: Controlled() for p in settings.peers})
        task = asyncio.create_task(monitor.run_once())
        try:
            for _ in range(10):
                await asyncio.sleep(0)
            assert started == [f'd-{i}' for i in range(size)]
            assert monitor.progress['group_id'] == 'home'
            assert monitor.progress['batch'] == 1
            assert monitor.progress['batches'] == 2
            gate.set()
            await task
            assert started == [f'd-{i}' for i in range(size + 1)] + ['last']
            assert peak == size
            assert monitor.progress is None
            assert not monitor.lock.locked()
            assert monitor.max_gap == 2 * (settings.interval_seconds + 3 * (settings.timeout_seconds + 1))
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            store.close()
    asyncio.run(run())


def test_two_devices_run_together_even_when_batch_setting_is_five(settings, tmp_path):
    async def run():
        settings.batch_size = 5
        settings.peers[0].targets = settings.peers[0].targets[:2]
        started = asyncio.Event()
        count = 0
        class Both:
            async def check(self, target, timeout):
                nonlocal count
                count += 1
                if count == 2:
                    started.set()
                await asyncio.wait_for(started.wait(), 0.5)
                return Result('healthy', 1)
        store = Store(tmp_path / 'two.db')
        try:
            await Monitor(settings, store, {'home': Both()}).run_once()
            assert all(store.latest('home', t.id)['status'] == 'healthy' for t in settings.peers[0].targets)
        finally:
            store.close()
    asyncio.run(run())


@pytest.mark.anyio
async def test_no_fixed_device_or_group_count_cap_and_invalid_batches(settings, tmp_path):
    path = tmp_path / 'many.json'
    app = create_app(settings, tmp_path / 'many.db', background=False, settings_path=path)
    async with api_client(app) as client:
        payload = configuration()
        payload['groups'][0]['devices'] = [device(i) for i in range(250)]
        assert (await client.post('/api/setup', json=payload)).status_code == 200
        assert len(app.state.monitor.settings.peers[0].targets) == 250
        assert len((await client.get('/api/setup')).json()['groups'][0]['devices']) == 250
        previous = path.read_text()
        for size in [0, 1, 6]:
            payload['batch_size'] = size
            assert (await client.post('/api/setup', json=payload)).status_code == 422
            assert path.read_text() == previous
    raw = settings.model_dump()
    raw['peers'] = [{**raw['peers'][0], 'id': f'group-{i}'} for i in range(105)]
    assert len(Settings.model_validate(raw).peers) == 105


@pytest.mark.anyio
async def test_groups_cannot_edit_hidden_or_remote_groups(settings, tmp_path):
    other = settings.peers[0].model_copy(deep=True)
    other.id, other.owner = 'hidden', 'friend'
    settings.peers.append(other)
    path = tmp_path / 'protected.json'
    app = create_app(settings, tmp_path / 'protected.db', background=False, settings_path=path)
    async with api_client(app) as client:
        bad = configuration()
        bad['groups'][0]['id'] = 'hidden'
        assert (await client.post('/api/setup', json=bad)).status_code == 403
        assert not path.exists()
        # The editor only replaces groups owned by this local operator.
        assert (await client.post('/api/setup', json=configuration())).status_code == 200
        assert next(p for p in app.state.monitor.settings.peers if p.id == 'hidden') == other
        assert 'hidden' not in [g['id'] for g in (await client.get('/api/setup')).json()['groups']]


@pytest.mark.anyio
async def test_remove_group_and_device_preserves_remaining_and_stored_history(settings, tmp_path):
    app = create_app(settings, tmp_path / 'remove.db', background=False, settings_path=tmp_path / 'config.json')
    async with api_client(app) as client:
        await client.post('/api/setup', json=configuration())
        setup = (await client.get('/api/setup')).json()
        ids = [g['id'] for g in setup['groups']]
        app.state.monitor.transports = {id: FakeTransport() for id in ids}
        for id in ids:
            await client.post(f'/api/peers/{id}/recheck', json={})
        removed_device = setup['groups'][0]['devices'].pop()['id']
        removed_group_device = setup['groups'][1]['devices'][0]['id']
        setup['groups'].pop()
        payload = {k: setup[k] for k in ['local_user', 'batch_size', 'groups']}
        assert (await client.post('/api/setup', json=payload)).status_code == 200
        assert len(app.state.monitor.settings.peers) == 1
        assert len(app.state.monitor.settings.peers[0].targets) == 3
        assert app.state.monitor.store.latest(ids[0], removed_device) is not None
        assert app.state.monitor.store.latest(ids[1], removed_group_device) is not None
        assert (await client.post(f'/api/peers/{ids[1]}/recheck', json={})).status_code == 404


@pytest.mark.anyio
async def test_failed_save_does_not_rename_other_peers_grants(settings, tmp_path, monkeypatch):
    other = settings.peers[0].model_copy(deep=True)
    other.id, other.owner = 'other', 'friend'
    settings.peers.append(other)
    app = create_app(settings, tmp_path / 'atomic.db', background=False, settings_path=tmp_path / 'config.json')
    async with api_client(app) as client:
        setup = (await client.get('/api/setup')).json()
        payload = {k: setup[k] for k in ['local_user', 'batch_size', 'groups']}
        payload['local_user'] = 'alex'
        def fail(*args):
            raise OSError('disk full')
        monkeypatch.setattr('app.main.save_settings', fail)
        assert (await client.post('/api/setup', json=payload)).status_code == 500
        assert app.state.monitor.settings.local_user == 'owner'
        assert app.state.monitor.settings.peers == settings.peers


@pytest.mark.parametrize('groups', [[], [{'name':'Empty', 'devices':[]}], [{'name':' ', 'devices':[device(1)]}]])
def test_empty_groups_rejected(groups):
    from app.config import Setup
    with pytest.raises(ValidationError):
        Setup(local_user='owner', groups=groups)


def test_failed_batch_cleans_up_other_probes_before_unlock(settings, tmp_path, monkeypatch):
    async def run():
        store = Store(tmp_path / 'cleanup.db')
        both_started = asyncio.Event()
        started = []
        active = 0
        class Controlled:
            async def check(self, target, timeout):
                nonlocal active
                started.append(target.id)
                active += 1
                if active == 2:
                    both_started.set()
                try:
                    await both_started.wait()
                    if target.id == 'one':
                        return Result('healthy', 1)
                    await asyncio.Event().wait()
                finally:
                    active -= 1
        def fail_record(*args):
            raise OSError('disk full')
        monkeypatch.setattr(store, 'record', fail_record)
        monitor = Monitor(settings, store, {'home': Controlled()})
        try:
            with pytest.raises(ExceptionGroup):
                await monitor.run_once()
            assert active == 0
            assert started == ['one', 'two']
            assert not monitor.lock.locked()
            assert monitor.progress is None
        finally:
            store.close()
    asyncio.run(run())
