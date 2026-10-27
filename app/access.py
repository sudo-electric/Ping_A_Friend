"""Owner access for LAN dashboards; no external account or service is involved."""
import hashlib
import hmac
import ipaddress
import os
import re
import secrets
import socket
import tempfile
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from .paths import private_path, private_directory, private_file

COOKIE = "paf_session"
SESSION_SECONDS = 30 * 24 * 3600


def key_path():
    return Path(os.environ['PAF_ACCESS_KEY_FILE']) if os.environ.get('PAF_ACCESS_KEY_FILE') else private_path('access.key', 'data/access.key')


def load_access_key(path=None, reset=False):
    path = Path(path) if path is not None else key_path()
    private_directory(path.parent)
    if path.is_symlink():
        raise ValueError('Access key files must not be symlinks')
    if reset or not path.exists():
        key = secrets.token_urlsafe(24)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as file:
                temporary = Path(file.name)
                file.write(key + "\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    private_file(path)
    key = path.read_text().strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,128}", key):
        raise ValueError("Invalid dashboard access key file; reset the key with --reset-access-key")
    return key


@lru_cache(maxsize=1)
def local_names():
    names = {socket.gethostname().lower(), socket.getfqdn().lower()}
    return names | {name + ".local" for name in names if "." not in name}


def valid_host(raw, lan):
    try:
        parsed = urlsplit("//" + raw)
        host = parsed.hostname
        port = parsed.port  # Validate malformed/out-of-range ports, even when not used.
        if not host or parsed.username is not None or parsed.path or parsed.query or parsed.fragment:
            return False
    except ValueError:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    if not lan:
        return False
    try:
        address = ipaddress.ip_address(host)
        return address.is_private and not address.is_multicast and not address.is_unspecified
    except ValueError:
        names = set(local_names())
        names |= {n.strip().lower() for n in os.environ.get("PAF_ALLOWED_HOSTS", "").split(",") if n.strip()}
        return host.lower() in names


def loopback_client(host):
    try:
        address = ipaddress.ip_address(host)
        return address.is_loopback or bool(getattr(address, "ipv4_mapped", None) and address.ipv4_mapped.is_loopback)
    except ValueError:
        return False


def local_addresses():
    addresses = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(info[4][0])
    except OSError:
        pass
    # UDP connect selects a local route without transmitting a message.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            connection.connect(("192.0.2.1", 9))
            addresses.add(connection.getsockname()[0])
    except OSError:
        pass
    return sorted(a for a in addresses if ipaddress.ip_address(a).is_private and not ipaddress.ip_address(a).is_loopback)


class Access:
    def __init__(self, enabled, path=None, clock=time.time):
        self.enabled = enabled
        self.key = load_access_key(path) if enabled else None
        self.cookie = f'{COOKIE}_{hashlib.sha256(self.key.encode()).hexdigest()[:16]}' if enabled else COOKIE
        self.clock = clock
        self.attempts = OrderedDict()
        self.bootstrap = os.environ.pop('PAF_BROWSER_TOKEN', None) if enabled else None
        self.bootstrap_expires = self.clock() + 60

    def use_bootstrap(self, token, source):
        if not self.bootstrap or not loopback_client(source) or self.clock() >= self.bootstrap_expires:
            return False
        if not hmac.compare_digest(token.encode(), self.bootstrap.encode()):
            return False
        self.bootstrap = None
        return True

    def authenticated(self, token):
        if not token or len(token) > 256:
            return False
        try:
            nonce, expires, signature = token.split(".")
            expected = hmac.new(self.key.encode(), f"{nonce}.{expires}".encode(), hashlib.sha256).hexdigest()
            return int(expires) > self.clock() and hmac.compare_digest(expected, signature)
        except (ValueError, AttributeError):
            return False

    def new_session(self):
        payload = f"{secrets.token_urlsafe(24)}.{int(self.clock() + SESSION_SECONDS)}"
        signature = hmac.new(self.key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{signature}"

    def allow_attempt(self, source):
        now = self.clock()
        since, count = self.attempts.get(source, (now, 0))
        if now - since >= 60:
            since, count = now, 0
        self.attempts[source] = (since, count + 1)
        self.attempts.move_to_end(source)
        while len(self.attempts) > 1024:
            self.attempts.popitem(last=False)
        return count < 8
