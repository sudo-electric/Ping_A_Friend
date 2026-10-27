import ipaddress
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from .paths import private_path, private_file


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Target(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["device", "external"]
    host: str
    method: Literal["icmp", "tcp"] = "icmp"
    port: int = Field(default=443, ge=1, le=65535)
    enabled: bool = True
    delayed_ms: float = Field(default=100, gt=0, le=60000)

    @field_validator("host")
    @classmethod
    def safe_host(cls, value):
        try:
            ipaddress.ip_address(value)
        except ValueError:
            if not re.fullmatch(r"(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", value):
                raise ValueError("Use a bare IP address or hostname; no URL, flags, or shell syntax")
        return value


class Grant(StrictModel):
    user: str = Field(min_length=1, max_length=64)
    recheck: bool = False


class Peer(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=100)
    owner: str = Field(min_length=1, max_length=64)
    transport: Literal["local", "remote"] = "local"
    grants: list[Grant] = Field(default_factory=list)
    targets: list[Target]

    @model_validator(mode="after")
    def validate_targets(self):
        if len({t.id for t in self.targets}) != len(self.targets):
            raise ValueError("Target IDs must be unique within a peer")
        devices = [t for t in self.targets if t.kind == "device"]
        if not devices:
            raise ValueError("Each group needs at least one device definition")
        enabled = [t for t in devices if t.enabled]
        if len({t.host.lower() for t in enabled}) != len(enabled):
            raise ValueError("Enabled devices must have distinct hosts")
        if len({g.user for g in self.grants}) != len(self.grants):
            raise ValueError("Duplicate peer grants")
        return self

    def can_view(self, user):
        return user == self.owner or any(g.user == user for g in self.grants)

    def can_recheck(self, user):
        return user == self.owner or any(g.user == user and g.recheck for g in self.grants)


class Settings(StrictModel):
    local_user: str = Field(default="owner", min_length=1, max_length=64)
    interval_seconds: float = Field(default=15, ge=1, le=3600)
    timeout_seconds: float = Field(default=3, ge=0.1, le=30)
    confirmation_seconds: float = Field(default=90, ge=1, le=3600)
    retention_days: int = Field(default=30, ge=1, le=365)
    batch_size: int = Field(default=2, ge=2, le=5)
    peers: list[Peer] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_peers(self):
        if len({p.id for p in self.peers}) != len(self.peers):
            raise ValueError("Peer IDs must be unique")
        return self


def config_path():
    return Path(os.environ['PAF_CONFIG']) if os.environ.get('PAF_CONFIG') else private_path('config.json', 'config.json')


def load_settings():
    path = config_path()
    if not path.exists():
        path = Path(__file__).resolve().parent.parent / "config.example.json"
    else:
        private_file(path)
    try:
        return Settings.model_validate(json.loads(path.read_text()))
    except ValueError:
        raise ValueError('Monitoring settings are invalid; private configuration values have been withheld') from None


def save_settings(settings, path):
    """Replace atomically so a failed write leaves the previous config intact."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Configuration files must not be symlinks')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(settings.model_dump_json(indent=2) + "\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class SetupDevice(StrictModel):
    id: str | None = Field(default=None, pattern=r"^[a-z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=100)
    host: str
    method: Literal["icmp", "tcp"] = "icmp"
    port: int = Field(default=443, ge=1, le=65535)
    delayed_ms: float = Field(default=100, gt=0, le=60000)

    _safe_host = field_validator("host")(Target.safe_host.__func__)


class SetupGroup(StrictModel):
    id: str | None = Field(default=None, pattern=r"^[a-z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=100)
    devices: list[SetupDevice] = Field(min_length=1)
    external_checks: bool = False

    @model_validator(mode="after")
    def validate_devices(self):
        if len({d.host.lower() for d in self.devices}) != len(self.devices):
            raise ValueError("Choose different device addresses within each group")
        ids = [d.id for d in self.devices if d.id is not None]
        if len(set(ids)) != len(ids):
            raise ValueError("Device IDs must be unique within a group")
        if not self.name.strip() or any(not d.name.strip() for d in self.devices):
            raise ValueError("Names cannot be blank")
        return self


class Setup(StrictModel):
    local_user: str = Field(min_length=1, max_length=64)
    batch_size: int = Field(default=2, ge=2, le=5)
    groups: list[SetupGroup] | None = Field(default=None, min_length=1)
    # Accept the previous setup shape for existing local clients.
    network_name: str | None = Field(default=None, min_length=1, max_length=100)
    devices: list[SetupDevice] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_setup(self):
        if not self.local_user.strip():
            raise ValueError("Names cannot be blank")
        if self.groups is None:
            if self.network_name is None or self.devices is None:
                raise ValueError("Provide groups with at least one device each")
            SetupGroup(name=self.network_name, devices=self.devices)
        elif self.network_name is not None or self.devices is not None:
            raise ValueError("Provide groups or the legacy device list, not both")
        else:
            ids = [g.id for g in self.groups if g.id is not None]
            if len(set(ids)) != len(ids):
                raise ValueError("Group IDs must be unique")
        return self
