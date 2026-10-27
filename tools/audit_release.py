"""Inspect decompressed release members without printing any private marker."""
import getpass
import json
import marshal
from pathlib import Path
import re
import socket
import sqlite3


def private_markers(root):
    markers = []
    def add(value, category, word=False):
        if isinstance(value, str) and len(value) >= 4:
            raw = value.encode()
            pattern = re.escape(raw)
            if word:
                pattern = rb'(?<![A-Za-z0-9_])' + pattern + rb'(?![A-Za-z0-9_])'
            markers.append((re.compile(pattern, re.I), category))
    add(str(Path.home()), 'builder home path')
    if getpass.getuser().lower() not in {'root','user','nobody'}:
        add(getpass.getuser(), 'builder username', True)
    add(socket.gethostname(), 'builder hostname', True)
    config = Path(root)/'config.json'
    if config.is_file():
        data = json.loads(config.read_text())
        if str(data.get('local_user', '')).lower() not in {'owner','user','admin','local','monitor','test','friend'}:
            add(data.get('local_user'), 'local owner name', True)
        for peer in data.get('peers', []):
            for target in peer.get('targets', []):
                if target.get('kind') == 'device' and target.get('host') not in {'1.1.1.1','8.8.8.8','127.0.0.1','::1'}:
                    add(target.get('host'), 'configured device address', True)
    private = Path(root)/'data'
    for key in private.glob('*.key'):
        add(key.read_text().strip(), 'installation key')
    database = private/'ping_a_friend.sqlite3'
    if database.is_file():
        db = sqlite3.connect(f'file:{database}?mode=ro', uri=True)
        try:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='destinations'").fetchone():
                for (value,) in db.execute('SELECT config FROM destinations'):
                    if value.startswith('fernet:v1:'):
                        key_path = database.with_suffix('.secrets.key')
                        if not key_path.exists(): continue
                        from cryptography.fernet import Fernet
                        value = Fernet(key_path.read_bytes()).decrypt(value[len('fernet:v1:'):].encode()).decode()
                    data = json.loads(value)
                    for field in ('secret','account','address','sender'):
                        add(data.get(field), 'provider credential/destination')
        finally:
            db.close()
    return markers


def audit_binary(binary, root):
    from PyInstaller.archive.readers import CArchiveReader
    reader = CArchiveReader(str(binary))
    markers = private_markers(root)
    findings = set()
    count = 0
    def check(name, payload):
        nonlocal count
        count += 1
        if not payload: return
        for pattern, category in markers:
            if pattern.search(payload): findings.add((name, category))
    prohibited = {'config.json','access.key','PROJECT_MEMORY.md','AGENTS.md','.env'}
    for name in reader.toc:
        normalized = name.replace('\\','/')
        if Path(normalized).name in prohibited or '/data/' in '/'+normalized or normalized.endswith(('.sqlite3','.secrets.key','.pem','.pfx')):
            findings.add((name, 'private file included'))
        if name.endswith('.pyz'):
            archive = reader.open_embedded_archive(name)
            for module in archive.toc:
                value = archive.extract(module)
                if value is not None:
                    check(module, marshal.dumps(value))
        else:
            check(name, reader.extract(name))
    return {'passed':not findings, 'members_checked':count,
            'private_marker_checks':len(markers),
            'findings':[{'member':name,'category':category} for name,category in sorted(findings)]}
