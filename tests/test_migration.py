import json
import time
from pathlib import Path

import pytest

from app.config import Settings, load_settings
from app.main import create_app
from app.migration import export_data, read_transfer, restore_data
from app.monitor import Monitor
from app.notify import DestinationInput, Notifier
from app.store import Store
from app.transport import Result
from conftest import api_client


def fresh_settings():
    return Settings.model_validate_json(Path('config.example.json').read_text())


@pytest.mark.anyio
async def test_encrypted_roundtrip_preserves_history_disables_sends_and_keeps_new_key(settings, tmp_path):
    source = create_app(settings, tmp_path/'source.db', background=False, lan_mode=True,
                        access_key_path=tmp_path/'source.key')
    dest_path = tmp_path/'restored.json'
    destination = create_app(fresh_settings(), tmp_path/'destination.db', background=False,
                             lan_mode=True, access_key_path=tmp_path/'destination.key', settings_path=dest_path)
    async with api_client(source) as src, api_client(destination) as dst:
        source_key = source.state.access.key
        new_key = destination.state.access.key
        assert (await src.post('/api/login', json={'key':source_key})).status_code == 200
        assert (await dst.post('/api/login', json={'key':new_key})).status_code == 200
        monitor = source.state.monitor
        monitor.store.record(settings.peers[0], settings.peers[0].targets[0], Result('healthy', 2.5), time.time(), 90, 60)
        secret = 'https://hooks.slack.com/services/test/transfer/token'
        await source.state.notifier.configure(DestinationInput(provider='slack', enabled=True, secret=secret))
        source.state.notifier.enqueue('slack','transfer-pending','Must not send')
        source.state.monitor.store.db.commit()
        # Fresh monitoring may already have sampled its disabled placeholders.
        target = destination.state.monitor.settings.peers[0].targets[0]
        destination.state.monitor.store.record(destination.state.monitor.settings.peers[0],target,Result('unconfigured'),time.time(),90,60)
        result = await src.post('/api/access/export', json={})
        assert result.status_code == 200
        archive = result.text
        assert secret not in archive and settings.peers[0].targets[0].host not in archive
        response = await dst.post('/api/access/import', json={'archive':archive,'key':source_key,'confirm':True})
        assert response.status_code == 200, response.text
        assert destination.state.access.key == new_key != source_key
        assert destination.state.monitor.settings == settings
        assert destination.state.monitor.store.latest('home','one')['latency_ms'] == 2.5
        provider = destination.state.notifier.destinations()['slack']
        assert provider.secret == secret and not provider.enabled
        assert destination.state.notifier.history()[0]['state'] == 'cancelled'
        assert 'fernet:v1:' in destination.state.monitor.store.db.execute('SELECT config FROM destinations').fetchone()[0]
        assert json.loads(dest_path.read_text()) == settings.model_dump()
        assert (await dst.get('/api/status')).status_code == 200
        assert (await dst.post('/api/access/import', json={'archive':archive,'key':source_key,'confirm':True})).status_code == 422
    # Reload from saved files, including the destination's own encryption key.
    store = Store(tmp_path/'destination.db')
    assert Notifier(store).destinations()['slack'].secret == secret
    store.close()


def test_bad_key_tamper_and_malformed_history_leave_destination_untouched(settings, tmp_path):
    store = Store(tmp_path/'fresh.db')
    monitor = Monitor(fresh_settings(), store)
    notifier = Notifier(store)
    key = 'a'*32
    archive = export_data(monitor, notifier, key)
    for bad, password in [(archive,'b'*32),(archive[:-10]+'tampered',key),('not json',key)]:
        with pytest.raises(ValueError):
            restore_data(monitor, notifier, bad, password, tmp_path/'config.json')
        assert monitor.settings == fresh_settings()
        assert not (tmp_path/'config.json').exists()
    # Authenticated encryption does not make incompatible data valid.
    original = export_data(monitor, notifier, key)
    from app.migration import cipher
    import base64
    envelope=json.loads(original)
    c=cipher(key,base64.b64decode(envelope['salt']))
    raw=json.loads(c.decrypt(envelope['data'].encode()))
    raw['tables']['samples']=[{'unexpected':'value'}]
    envelope['data']=c.encrypt(json.dumps(raw).encode()).decode()
    with pytest.raises(ValueError):
        restore_data(monitor,notifier,json.dumps(envelope),key,tmp_path/'config.json')
    assert not store.db.execute('SELECT 1 FROM samples').fetchone()
    store.close()


@pytest.mark.anyio
async def test_transfer_requires_owner_confirmation_and_serializes_with_probes(tmp_path):
    app=create_app(fresh_settings(),tmp_path/'db.sqlite3',background=False,lan_mode=True,
                   access_key_path=tmp_path/'access.key',settings_path=tmp_path/'config.json')
    async with api_client(app) as client:
        assert (await client.post('/api/access/export',json={})).status_code==401
        assert (await client.post('/api/access/import',json={})).status_code==401
        await client.post('/api/login',json={'key':app.state.access.key})
        # Pairing is available before any device has been configured.
        assert (await client.get('/api/setup')).json()['required']
        assert (await client.get('/api/access/pairing')).status_code==200
        archive=(await client.post('/api/access/export',json={})).text
        assert (await client.post('/api/access/import',json={'archive':archive,'key':app.state.access.key,'confirm':False})).status_code==422
        async with app.state.monitor.lock:
            assert (await client.post('/api/access/export',json={})).status_code==409
            assert (await client.post('/api/access/import',json={'archive':archive,'key':app.state.access.key,'confirm':True})).status_code==409
        response=await client.post('/api/access/import',json={'archive':'bad','key':'private-unlock-value','confirm':True})
        assert response.status_code==422 and 'private-unlock-value' not in response.text
