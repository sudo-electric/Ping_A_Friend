import json
import os
from pathlib import Path
import stat
import sys

import pytest
from cryptography.fernet import Fernet

from app.access import Access, load_access_key
from app.config import config_path, load_settings
from app.main import create_app
from app.notify import DestinationInput, Notifier
from app.paths import data_directory, external_environment
from app.store import Store
from conftest import api_client


def test_private_directory_and_existing_key_permissions_are_hardened(tmp_path):
    directory = tmp_path/'data'
    directory.mkdir(mode=0o755)
    key = directory/'access.key'
    key.write_text('a'*32)
    key.chmod(0o644)
    assert load_access_key(key) == 'a'*32
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700


def test_private_storage_rejects_symlinks_without_touching_target(tmp_path):
    target = tmp_path/'unrelated.txt'
    target.write_text('private')
    key = tmp_path/'access.key'
    key.symlink_to(target)
    with pytest.raises(ValueError, match='symlink'):
        load_access_key(key)
    assert target.read_text() == 'private'
    db = tmp_path/'db.sqlite3'
    db.symlink_to(target)
    with pytest.raises(ValueError, match='symlink'):
        Store(db)


@pytest.mark.anyio
async def test_provider_settings_are_encrypted_and_reopen_with_the_installation_key(tmp_path):
    path = tmp_path/'data'/'private.sqlite3'
    store = Store(path)
    notifier = Notifier(store)
    secret = 'https://discord.com/api/webhooks/123/private-persisted-token'
    await notifier.configure(DestinationInput(provider='discord', enabled=True, secret=secret))
    dump = '\n'.join(store.db.iterdump())
    assert secret not in dump and 'fernet:v1:' in dump
    assert secret.encode() not in path.read_bytes()
    assert notifier.destinations()['discord'].secret == secret
    key = path.with_suffix('.secrets.key')
    original = key.read_bytes()
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    store.close()
    store = Store(path)
    assert Notifier(store).destinations()['discord'].secret == secret
    key.unlink()
    with pytest.raises(ValueError, match='key is missing'):
        Notifier(store)
    key.write_bytes(Fernet.generate_key())
    with pytest.raises(ValueError, match='could not be unlocked'):
        Notifier(store)
    key.write_bytes(original)
    assert Notifier(store).destinations()['discord'].secret == secret
    store.close()


def test_legacy_plaintext_credentials_migrate_and_are_removed_from_database_pages(tmp_path):
    store = Store(tmp_path/'migration.sqlite3')
    # This is the previous schema; populate it before starting the new notifier.
    store.db.execute('CREATE TABLE destinations(provider TEXT PRIMARY KEY, config TEXT NOT NULL, since REAL NOT NULL)')
    secret = 'https://hooks.slack.com/services/EXAMPLE/TEST/legacy-private-token'
    config = dict(provider='slack', enabled=True, secret=secret, recovery=True)
    with store.db:
        store.db.execute('INSERT INTO destinations VALUES(?,?,?)', ('slack', json.dumps(config), 0))
    notifier = Notifier(store)
    assert notifier.destinations()['slack'].secret == secret
    assert notifier.destinations()['slack'].recovery
    for path in tmp_path.glob('migration.sqlite3*'):
        assert secret.encode() not in path.read_bytes()
    assert secret not in json.dumps(notifier.public())
    store.close()


def test_frozen_defaults_use_private_profile_and_ignore_neighbor_configuration(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path/'profile'))
    monkeypatch.delenv('PAF_CONFIG', raising=False)
    monkeypatch.delenv('PAF_DATA_DIR', raising=False)
    monkeypatch.chdir(tmp_path)
    Path('config.json').write_text('{"private":"must not be imported"}')
    assert data_directory() == tmp_path/'profile'/'Ping_A_Friend'
    assert config_path() == data_directory()/'config.json'
    defaults = load_settings()
    assert defaults.local_user == 'owner'
    assert all(not t.enabled for p in defaults.peers for t in p.targets)


def test_bootstrap_is_local_one_use_short_lived_and_not_the_owner_key(tmp_path, monkeypatch):
    monkeypatch.setenv('PAF_BROWSER_TOKEN', 'bootstrap-test-token')
    now = [100.]
    access = Access(True, tmp_path/'access.key', clock=lambda:now[0])
    assert 'PAF_BROWSER_TOKEN' not in os.environ
    assert not access.use_bootstrap('bootstrap-test-token', '192.0.2.1')
    assert not access.use_bootstrap('wrong', '127.0.0.1')
    assert access.use_bootstrap('bootstrap-test-token', '127.0.0.1')
    assert not access.use_bootstrap('bootstrap-test-token', '127.0.0.1')
    monkeypatch.setenv('PAF_BROWSER_TOKEN', 'second-token')
    access = Access(True, tmp_path/'access.key', clock=lambda:now[0])
    now[0] += 61
    assert not access.use_bootstrap('second-token', '127.0.0.1')


@pytest.mark.anyio
async def test_pairing_details_require_owner_and_validation_errors_do_not_echo_keys(settings, tmp_path, monkeypatch):
    monkeypatch.setattr('app.main.local_addresses', lambda:['192.0.2.99'])
    app = create_app(settings, tmp_path/'data.db', background=False, lan_mode=True, access_key_path=tmp_path/'access.key')
    async with api_client(app) as client:
        assert (await client.get('/api/access/pairing')).status_code == 401
        secret = 'do-not-echo-private-key-'*30
        invalid = await client.post('/api/login', json={'key':secret})
        assert invalid.status_code == 422 and secret not in invalid.text
        app.state.access.bootstrap = 'one-use-login'
        assert (await client.post('/api/login', json={'key':'one-use-login'})).status_code == 200
        details = (await client.get('/api/access/pairing')).json()
        assert details['key'] == app.state.access.key
        assert details['links'][0].startswith('http://192.0.2.99/login#key=')
        assert details['key'] not in (await client.get('/api/status')).text
        assert app.state.access.bootstrap is None


def test_frozen_external_helpers_use_system_library_paths(monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setenv('LD_LIBRARY_PATH', '/temporary/bundle')
    monkeypatch.setenv('LD_LIBRARY_PATH_ORIG', '/system/libraries')
    assert external_environment()['LD_LIBRARY_PATH'] == '/system/libraries'
    monkeypatch.delenv('LD_LIBRARY_PATH_ORIG')
    assert 'LD_LIBRARY_PATH' not in external_environment()
    assert os.environ['LD_LIBRARY_PATH'] == '/temporary/bundle'


def test_invalid_configuration_does_not_echo_private_addresses(tmp_path, monkeypatch):
    path = tmp_path/'config.json'
    path.write_text(json.dumps({'local_user':'private-owner-label','peers':[{'host':'private-device.example'}]}))
    monkeypatch.setenv('PAF_CONFIG', str(path))
    with pytest.raises(ValueError) as error:
        load_settings()
    assert 'private-owner-label' not in str(error.value)
    assert 'private-device.example' not in str(error.value)


def test_release_staging_is_an_allowlist_not_a_copy_of_the_live_folder(tmp_path, monkeypatch):
    from tools import build_release
    root = tmp_path/'project'
    (root/'app'/'static').mkdir(parents=True)
    (root/'app'/'__init__.py').write_text('')
    (root/'app'/'static'/'index.html').write_text('<h1>Example</h1>')
    (root/'config.example.json').write_text(json.dumps({'local_user':'owner','peers':[{
        'owner':'owner','grants':[], 'targets':[{'enabled':False,'host':'192.0.2.10'}]}]}))
    for name in ('config.json','.env','PROJECT_MEMORY.md','AGENTS.md'):
        (root/name).write_text('must never be staged')
    (root/'data').mkdir()
    (root/'data'/'access.key').write_text('must never be staged')
    monkeypatch.setattr(build_release, 'ROOT', root)
    stage = tmp_path/'stage'
    build_release.stage_sources(stage)
    names = {str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file()}
    assert names == {'app/__init__.py','app/static/index.html','config.example.json','run_app.py'}
    # A private file accidentally put in static fails the build instead of leaking.
    (root/'app'/'static'/'access.key').write_text('private')
    with pytest.raises(ValueError, match='Unexpected static asset'):
        build_release.stage_sources(tmp_path/'second-stage')


def test_installation_cookie_names_are_distinct_and_stable(tmp_path):
    first = Access(True, tmp_path/'first.key')
    second = Access(True, tmp_path/'second.key')
    assert first.cookie != second.cookie
    assert Access(True, tmp_path/'first.key').cookie == first.cookie
    assert not second.authenticated(first.new_session())


@pytest.mark.anyio
async def test_legacy_cookie_still_authenticates_after_upgrade(settings, tmp_path):
    from app.access import COOKIE
    app = create_app(settings, tmp_path/'legacy.db', background=False, lan_mode=True, access_key_path=tmp_path/'access.key')
    async with api_client(app) as client:
        client.cookies.set(COOKIE, app.state.access.new_session(), domain='localhost.local', path='/')
        assert (await client.get('/api/status')).status_code == 200
        assert (await client.post('/api/logout', json={})).status_code == 200
        assert (await client.get('/api/status')).status_code == 401
