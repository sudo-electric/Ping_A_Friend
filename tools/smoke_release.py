"""Exercise the compiled application with disposable data and loopback probes."""
import argparse
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import signal
import socket
import sqlite3
import stat
import subprocess
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPCookieProcessor, build_opener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    with tempfile.TemporaryDirectory(prefix='paf-release-smoke-') as temporary:
        root = Path(temporary)
        home = root/'home'
        home.mkdir()
        working = root/'working'
        working.mkdir()
        (working/'config.json').write_text('{"private":"neighboring file must not load"}')
        env = {k:v for k,v in os.environ.items() if not k.startswith('PAF_')}
        env.update(HOME=str(home), XDG_DATA_HOME=str(home/'share'))
        with socket.socket() as picker:
            picker.bind(('127.0.0.1',0))
            port = picker.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        profile = home/'share'/'Ping_A_Friend'
        client = build_opener(HTTPCookieProcessor(CookieJar()))
        def request(path, payload=None):
            data = None if payload is None else json.dumps(payload).encode()
            return client.open(Request(base+path, data=data, headers={'Content-Type':'application/json'}), timeout=15)
        processes = []
        logs = []
        def start():
            process = subprocess.Popen([str(binary),'--no-browser','--port',str(port)], cwd=working, env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            processes.append(process)
            deadline = time.monotonic()+20
            while time.monotonic()<deadline:
                if process.poll() is not None:
                    raise AssertionError('Compiled application exited before readiness')
                try:
                    with request('/healthz') as response:
                        assert response.status == 200
                    return process
                except (URLError, OSError): time.sleep(.1)
            raise AssertionError('Compiled application did not become ready')
        def stop(process):
            process.send_signal(signal.SIGINT)
            output = process.communicate(timeout=15)[0]
            logs.append(output)
            assert process.returncode == 0
        listener = socket.socket()
        listener.bind(('127.0.0.2',0))
        listener.listen()
        listener.settimeout(.2)
        tcp_port = listener.getsockname()[1]
        finished = threading.Event()
        def accept():
            while not finished.is_set():
                try:
                    connection,_ = listener.accept()
                    connection.close()
                except socket.timeout: pass
                except OSError: break
        thread = threading.Thread(target=accept,daemon=True)
        thread.start()
        try:
            process = start()
            try: request('/api/status')
            except HTTPError as error: assert error.code == 401
            else: raise AssertionError('Anonymous LAN access was accepted')
            owner_key = (profile/'access.key').read_text().strip()
            request('/api/login', {'key':owner_key}).close()
            with request('/api/setup') as response:
                setup = json.load(response)
            assert setup['required'] and setup['local_user']=='owner'
            for resource in ('index.html','app.js','privacy.js','history.js','style.css','logo.svg'):
                with request('/static/'+resource) as response: assert response.status == 200
            payload = {'local_user':'owner','batch_size':2,'groups':[{'id':'home','name':'Loopback smoke','devices':[
                {'name':'Loopback ping','host':'127.0.0.1','method':'icmp'},
                {'name':'Loopback service','host':'127.0.0.2','method':'tcp','port':tcp_port}]}]}
            request('/api/setup', payload).close()
            with request('/api/peers/home/recheck', {}) as response:
                status = json.load(response)
            assert all(t['status']=='healthy' for t in status['peers'][0]['targets'])
            fake = 'https://hooks.slack.com/services/EXAMPLE/SMOKE/not-a-real-token'
            request('/api/notifications/settings', {'provider':'slack','enabled':False,'secret':fake}).close()
            db = sqlite3.connect(profile/'ping_a_friend.sqlite3')
            assert db.execute('SELECT config FROM destinations').fetchone()[0].startswith('fernet:v1:')
            assert fake not in '\n'.join(db.iterdump())
            db.close()
            assert stat.S_IMODE(profile.stat().st_mode)==0o700
            for filename in ('access.key','config.json','ping_a_friend.sqlite3','ping_a_friend.secrets.key'):
                assert stat.S_IMODE((profile/filename).stat().st_mode)==0o600
            stop(process)
            assert all(owner_key not in log and fake not in log and str(home) not in log for log in logs)
            # Existing owner cookies and encrypted settings survive executable restarts.
            process = start()
            with request('/api/status') as response: assert json.load(response)['local_user']=='owner'
            with request('/api/notifications/settings') as response:
                slack = next(d for d in json.load(response)['destinations'] if d['provider']=='slack')
                assert slack['configured'] and not slack['enabled'] and not slack['secret']
            stop(process)
        finally:
            finished.set()
            listener.close()
            thread.join(timeout=1)
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    process.communicate(timeout=10)
        print(json.dumps({'passed':True, 'checks':['fresh private profile','neighbor configuration ignored',
            'unauthenticated access denied','owner sign-in','bundled dashboard assets','real loopback ICMP/TCP',
            'encrypted provider settings','private file modes','restart persistence','no credentials in stdout'],
            'external_notifications_sent':False}, indent=2))


if __name__ == '__main__':
    main()
