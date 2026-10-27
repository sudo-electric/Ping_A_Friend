import stat

import httpx
import pytest

from app.access import Access, COOKIE, load_access_key, valid_host
from app.main import create_app
from conftest import FakeTransport


@pytest.fixture
def lan_app(settings, tmp_path):
    return create_app(settings, tmp_path / 'data.db', {'home': FakeTransport()}, background=False,
                      lan_mode=True, access_key_path=tmp_path / 'access.key', settings_path=tmp_path / 'config.json')


def remote_client(app, host='192.168.10.25', source='192.168.10.50'):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=(source, 43210)),
                            base_url=f'http://{host}')


@pytest.mark.anyio
async def test_lan_requires_signin_including_localhost_and_spoofed_forwarding(lan_app):
    async with lan_app.router.lifespan_context(lan_app):
        async with remote_client(lan_app) as client:
            assert (await client.get('/')).status_code == 303
            for path in ['/api/status', '/api/setup', '/docs', '/openapi.json']:
                assert (await client.get(path)).status_code == 401
            assert (await client.post('/api/peers/home/recheck', json={})).status_code == 401
            assert (await client.get('/healthz')).json() == {'status': 'ok'}
            assert (await client.get('/api/status', headers={'x-forwarded-for':'127.0.0.1'})).status_code == 401
        async with remote_client(lan_app, host='127.0.0.1', source='127.0.0.1') as client:
            assert (await client.get('/api/status')).status_code == 401


@pytest.mark.anyio
async def test_signin_full_owner_access_logout_and_cookie_attributes(lan_app):
    async with lan_app.router.lifespan_context(lan_app):
        async with remote_client(lan_app) as client:
            assert (await client.post('/api/login', json={'key':'incorrect'})).status_code == 401
            result = await client.post('/api/login', json={'key':lan_app.state.access.key})
            assert result.status_code == 200
            cookie = result.headers['set-cookie']
            assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Max-Age=2592000' in cookie
            status = (await client.get('/api/status')).json()
            assert status['local_user'] == 'owner'
            assert status['network_access'] == 'lan'
            assert (await client.get('/api/setup')).status_code == 200
            result = await client.post('/api/peers/home/recheck', json={})
            assert result.status_code == 200
            assert result.json()['peers'][0]['status'] == 'healthy'
            assert (await client.post('/api/logout', json={})).status_code == 200
            assert (await client.get('/api/status')).status_code == 401


@pytest.mark.anyio
async def test_pairing_survives_restart_but_key_reset_revokes(lan_app, tmp_path, settings):
    async with lan_app.router.lifespan_context(lan_app):
        async with remote_client(lan_app) as client:
            await client.post('/api/login', json={'key':lan_app.state.access.key})
            cookies = dict(client.cookies)
            original_key = lan_app.state.access.key
    next_app = create_app(settings, tmp_path / 'data.db', background=False, lan_mode=True,
                          access_key_path=tmp_path / 'access.key')
    async with next_app.router.lifespan_context(next_app):
        async with remote_client(next_app) as client:
            client.cookies.update(cookies)
            assert next_app.state.access.key == original_key
            assert (await client.get('/api/status')).status_code == 200
    load_access_key(tmp_path / 'access.key', reset=True)
    async with next_app.router.lifespan_context(next_app):
        async with remote_client(next_app) as client:
            client.cookies.update(cookies)
            assert (await client.get('/api/status')).status_code == 401
            assert (await client.post('/api/login', json={'key':original_key})).status_code == 401


@pytest.mark.anyio
async def test_local_only_cannot_be_exposed_by_changing_uvicorn_bind(settings, tmp_path):
    app = create_app(settings, tmp_path / 'local.db', background=False, lan_mode=False)
    async with app.router.lifespan_context(app):
        async with remote_client(app, host='127.0.0.1') as client:
            assert (await client.get('/api/status')).status_code == 403
        async with remote_client(app, host='127.0.0.1', source='127.0.0.1') as client:
            assert (await client.get('/api/status')).status_code == 200


@pytest.mark.anyio
async def test_lan_preserves_host_and_same_origin_boundaries(lan_app):
    async with lan_app.router.lifespan_context(lan_app):
        async with remote_client(lan_app) as client:
            key = lan_app.state.access.key
            assert (await client.post('/api/login', json={'key':key}, headers={'origin':'https://attacker.example'})).status_code == 403
            assert (await client.post('/api/login', content='{}')).status_code == 415
            assert (await client.post('/api/login', json={'key':key}, headers={'sec-fetch-site':'cross-site'})).status_code == 403
            assert (await client.get('/api/status', headers={'host':'attacker.example'})).status_code == 400
            assert (await client.post('/api/login', json={'key':key}, headers={'origin':'http://192.168.10.25'})).status_code == 200
            assert (await client.post('/api/peers/home/recheck', json={}, headers={'origin':'http://192.168.10.99'})).status_code == 403
            assert (await client.post('/api/peers/home/recheck', json={}, headers={'origin':'http://192.168.10.25'})).status_code == 200


@pytest.mark.anyio
async def test_login_throttling(lan_app):
    async with lan_app.router.lifespan_context(lan_app):
        async with remote_client(lan_app) as client:
            now = [100.0]
            lan_app.state.access.clock = lambda: now[0]
            for _ in range(8):
                assert (await client.post('/api/login', json={'key':'bad'})).status_code == 401
            assert (await client.post('/api/login', json={'key':lan_app.state.access.key})).status_code == 429
            now[0] += 61
            assert (await client.post('/api/login', json={'key':lan_app.state.access.key})).status_code == 200


def test_expired_modified_and_wrong_installation_sessions(tmp_path):
    clock = [100.0]
    control = Access(True, tmp_path / 'one.key', clock=lambda: clock[0])
    token = control.new_session()
    assert control.authenticated(token)
    assert not control.authenticated(token + 'x')
    assert not control.authenticated('bad')
    assert not Access(True, tmp_path / 'two.key').authenticated(token)
    clock[0] += 30 * 24 * 3600 + 1
    assert not control.authenticated(token)


def test_key_generated_once_private_permissions_and_reset(tmp_path):
    path = tmp_path / 'keys' / 'access.key'
    first = load_access_key(path)
    assert len(first) == 32
    assert load_access_key(path) == first
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load_access_key(path, reset=True) != first
    path.write_text('bad')
    with pytest.raises(ValueError, match='Invalid dashboard access key'):
        load_access_key(path)


@pytest.mark.parametrize('host', ['192.168.10.25:8000','10.0.0.5:8000','[fd00::123]:8000'])
def test_lan_literal_addresses_allowed(host):
    assert valid_host(host, True)
    assert not valid_host(host, False)


@pytest.mark.parametrize('host', ['attacker.example:8000','testserver:8000','8.8.8.8:8000','0.0.0.0:8000',
                                   'evil@192.168.10.25:8000','192.168.10.25:99999','192.168.10.25/path'])
def test_lan_bad_hosts_rejected(host):
    assert not valid_host(host, True)


def test_exact_custom_hostname_for_private_dns(monkeypatch):
    monkeypatch.setenv('PAF_ALLOWED_HOSTS', 'monitor.example.internal')
    assert valid_host('monitor.example.internal:8000', True)
    assert not valid_host('other.example.internal:8000', True)


def test_launcher_loads_key_automatically_and_uses_lan_binding(tmp_path, monkeypatch, capsys):
    from app import launch
    path = tmp_path / 'startup.key'
    monkeypatch.setenv('PAF_ACCESS_KEY_FILE', str(path))
    monkeypatch.setattr('sys.argv', ['launch', '--no-browser'])
    monkeypatch.setattr(launch, 'local_addresses', lambda: ['192.168.10.25'])
    configs = []
    class Server:
        def __init__(self, config):
            configs.append(config)
        def run(self):
            pass
    monkeypatch.setattr(launch.uvicorn, 'Server', Server)
    launch.main()
    first = path.read_text()
    output = capsys.readouterr().out
    assert configs[0].host == '0.0.0.0'
    assert configs[0].proxy_headers is False
    assert '/login#key=' not in output
    assert first.strip() not in output
    launch.main()
    assert path.read_text() == first
    monkeypatch.setattr('sys.argv', ['launch', '--no-browser', '--local-only'])
    launch.main()
    assert configs[-1].host == '127.0.0.1'
    assert launch.os.environ['PAF_LAN_MODE'] == '0'


def test_launcher_opens_host_browser_with_automatic_pairing(tmp_path, monkeypatch):
    from app import launch
    monkeypatch.delenv('PAF_BROWSER_TOKEN', raising=False)
    monkeypatch.setenv('PAF_ACCESS_KEY_FILE', str(tmp_path / 'auto.key'))
    monkeypatch.setenv('PAF_LAN_MODE', '0')
    monkeypatch.setattr('sys.argv', ['launch'])
    monkeypatch.setattr(launch, 'local_addresses', lambda: [])
    opened = []
    monkeypatch.setattr(launch.webbrowser, 'open', opened.append)
    class Server:
        started = True
        should_exit = False
        def __init__(self, config):
            pass
        def run(self):
            pass
    class Thread:
        def __init__(self, target, daemon):
            self.target = target
        def start(self):
            self.target()
    monkeypatch.setattr(launch.uvicorn, 'Server', Server)
    monkeypatch.setattr(launch.threading, 'Thread', Thread)
    launch.main()
    key = (tmp_path / 'auto.key').read_text().strip()
    assert len(opened) == 1
    assert opened[0].startswith('http://127.0.0.1:8000/login#key=')
    assert key not in opened[0]
    assert opened[0].endswith(launch.os.environ['PAF_BROWSER_TOKEN'])
