"""Optional outbound providers and a persistent, bounded-retry delivery queue.

No credentials are returned to the dashboard or included in delivery errors.
This is owner notification delivery, not friend authorization or a relay.
"""
import asyncio
import base64
import json
import logging
import re
import time
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from pydantic import Field, model_validator
from typing import Literal
from .config import StrictModel
from .store import HISTORY_RETENTION_SECONDS
from .vault import CredentialVault, PREFIX

PROVIDERS = ('discord', 'slack', 'telegram', 'twilio')


class Destination(StrictModel):
    provider: Literal['discord', 'slack', 'telegram', 'twilio']
    enabled: bool = False
    groups: list[str] = Field(default_factory=list, max_length=1000)
    recovery: bool = False
    monthly: bool = False
    daily_limit: int = Field(default=20, ge=1, le=1000)
    secret: str = Field(default='', max_length=2048)
    address: str = Field(default='', max_length=100)
    account: str = Field(default='', max_length=100)
    sender: str = Field(default='', max_length=100)

    @model_validator(mode='after')
    def validate_destination(self):
        if not self.enabled:
            return self
        if self.provider in {'slack', 'discord'}:
            url = urlsplit(self.secret)
            pattern = r'/services/[A-Za-z0-9_/-]+' if self.provider == 'slack' else r'/api/webhooks/[0-9]+/[A-Za-z0-9_-]+'
            host = 'hooks.slack.com' if self.provider == 'slack' else 'discord.com'
            if url.scheme != 'https' or url.netloc != host or url.query or url.fragment or not re.fullmatch(pattern, url.path):
                raise ValueError('Use the provider’s HTTPS incoming webhook URL')
        elif self.provider == 'telegram':
            if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', self.secret) or not re.fullmatch(r'-?[0-9]+', self.address):
                raise ValueError('Provide a bot token and numeric chat ID')
        else:
            if not re.fullmatch(r'AC[a-fA-F0-9]{32}', self.account) or not re.fullmatch(r'[a-fA-F0-9]{32}', self.secret):
                raise ValueError('Provide the Twilio account SID and auth token')
            if not all(re.fullmatch(r'\+[1-9][0-9]{6,14}', n) for n in (self.sender, self.address)):
                raise ValueError('Use international phone numbers, including + and country code')
        return self


class DestinationInput(StrictModel):
    provider: Literal['discord', 'slack', 'telegram', 'twilio']
    enabled: bool = False
    groups: list[str] = Field(default_factory=list, max_length=1000)
    recovery: bool = False
    monthly: bool = False
    daily_limit: int = Field(default=20, ge=1, le=1000)
    secret: str = Field(default='', max_length=2048)
    address: str = Field(default='', max_length=100)
    account: str = Field(default='', max_length=100)
    sender: str = Field(default='', max_length=100)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DeliveryError(Exception):
    def __init__(self, message, retry=False, uncertain=False):
        super().__init__(message)
        self.retry = retry
        self.uncertain = uncertain


class TestRateLimited(Exception):
    pass


def send(destination, message):
    """Blocking bounded HTTP call; invoked outside the event loop."""
    d = destination
    headers = {'Content-Type': 'application/json', 'User-Agent': 'Ping_A_Friend/0.2'}
    payload = {'text': message}
    if d.provider in {'discord', 'slack'}:
        url = d.secret
        if d.provider == 'discord':
            url += '?wait=true'
            payload = {'content': message, 'allowed_mentions': {'parse': []}}
    elif d.provider == 'telegram':
        url = f'https://api.telegram.org/bot{d.secret}/sendMessage'
        payload = {'chat_id': d.address, 'text': message, 'disable_notification': False}
    else:
        url = f'https://api.twilio.com/2010-04-01/Accounts/{d.account}/Messages.json'
        headers['Authorization'] = 'Basic ' + base64.b64encode(f'{d.account}:{d.secret}'.encode()).decode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        payload = {'From': d.sender, 'To': d.address, 'Body': message}
    data = (urlencode(payload).encode() if d.provider == 'twilio' else json.dumps(payload).encode())
    try:
        with build_opener(NoRedirect()).open(Request(url, data=data, headers=headers), timeout=10) as response:
            body = response.read(65536)
            if d.provider == 'telegram' and not json.loads(body).get('ok'):
                raise DeliveryError('Telegram rejected the message')
    except HTTPError as exc:
        raise DeliveryError(f'Provider returned HTTP {exc.code}', exc.code == 429 or exc.code >= 500) from None
    except (URLError, TimeoutError, OSError):
        # The provider may have accepted a timed-out POST. Retrying it could send
        # duplicate SMS; require an explicit new test instead.
        raise DeliveryError('Delivery uncertain: connection failed or timed out; not retried', uncertain=True) from None
    except (ValueError, KeyError):
        raise DeliveryError('Provider returned an invalid response') from None


class Notifier:
    def __init__(self, store, sender=send, clock=time.time):
        self.store, self.sender, self.clock = store, sender, clock
        self.lock = asyncio.Lock()
        store.db.executescript('''
            CREATE TABLE IF NOT EXISTS destinations(provider TEXT PRIMARY KEY, config TEXT NOT NULL, since REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS sms_usage(day INTEGER PRIMARY KEY, attempts INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS deliveries(
                id INTEGER PRIMARY KEY, provider TEXT NOT NULL, event_key TEXT NOT NULL,
                group_id TEXT, message TEXT NOT NULL, created REAL NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt REAL NOT NULL DEFAULT 0, detail TEXT NOT NULL DEFAULT '',
                UNIQUE(provider,event_key));
            CREATE INDEX IF NOT EXISTS delivery_queue ON deliveries(state,next_attempt);
            CREATE INDEX IF NOT EXISTS delivery_provider_time ON deliveries(provider,group_id,created);
        ''')
        # An interrupted request may already have been accepted. Do not replay.
        store.db.execute("UPDATE deliveries SET state='uncertain',detail='Application stopped during delivery; not retried' WHERE state='sending'")
        store.db.commit()
        rows = store.db.execute('SELECT provider,config FROM destinations').fetchall()
        self.vault = CredentialVault(store.path.with_suffix('.secrets.key'),
                                     required=any(r['config'].startswith(PREFIX) for r in rows))
        migrated = False
        with store.db:
            for row in rows:
                if row['config'].startswith(PREFIX):
                    self.decode(row['config'])  # Fail closed if the key is wrong.
                    continue
                try:
                    destination = Destination.model_validate_json(row['config'])
                except ValueError:
                    raise ValueError('Saved provider settings are invalid; private values have been withheld') from None
                store.db.execute('UPDATE destinations SET config=? WHERE provider=?',
                                 (self.vault.encrypt(destination.model_dump_json()), row['provider']))
                migrated = True
        if migrated:
            # Remove plaintext remnants from ordinary SQLite pages/WAL. Copies,
            # old backups, and SSD snapshots remain outside this migration.
            if store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]:
                raise ValueError('Close other application instances before migrating provider credentials')
            store.db.execute('VACUUM')
            store.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        self.prune_history()

    def decode(self, config):
        try:
            return Destination.model_validate_json(self.vault.decrypt(config))
        except ValueError:
            raise ValueError('Saved provider credentials could not be unlocked; restore the original installation key') from None

    def destinations(self):
        return {r['provider']: self.decode(r['config']) for r in self.store.db.execute('SELECT * FROM destinations')}

    def public(self):
        configured = self.destinations()
        return [dict(provider=p, enabled=p in configured and configured[p].enabled,
                     groups=configured[p].groups if p in configured else [],
                     recovery=configured[p].recovery if p in configured else False,
                     monthly=configured[p].monthly if p in configured else False,
                     daily_limit=configured[p].daily_limit if p in configured else 20,
                     configured=p in configured, secret='', address='', account='', sender='') for p in PROVIDERS]

    def resolve(self, payload, test=False):
        old = self.destinations().get(payload.provider)
        values = old.model_dump() if old else payload.model_dump()
        values.update(payload.model_dump(exclude_unset=True))
        if old:
            for key in ('secret', 'address', 'account', 'sender'):
                if not values[key]:
                    values[key] = getattr(old, key)
        if test:
            values['enabled'] = True  # Validate/send once without enabling alerts.
        return Destination.model_validate(values)

    async def configure(self, payload):
        async with self.lock:
            destination = self.resolve(payload)
            with self.store.db:
                # Settings changes cancel queued deliveries, so stale alerts cannot
                # be redirected to a newly entered recipient.
                self.store.db.execute("UPDATE deliveries SET state='cancelled',detail='Notification settings changed' WHERE provider=? AND state='pending'", (payload.provider,))
                self.store.db.execute('INSERT OR REPLACE INTO destinations VALUES(?,?,?)',
                                      (payload.provider, self.vault.encrypt(destination.model_dump_json()), self.clock()))

    def enqueue(self, provider, key, message, group=None):
        self.store.db.execute('INSERT OR IGNORE INTO deliveries(provider,event_key,group_id,message,created) VALUES(?,?,?,?,?)',
                              (provider, key, group, message, self.clock()))

    def collect(self, settings):
        from datetime import datetime, timezone
        from .presence import report
        now = self.clock()
        current = datetime.fromtimestamp(now, timezone.utc)
        previous = datetime(current.year, current.month, 1, tzinfo=timezone.utc).timestamp() - 1
        month = datetime.fromtimestamp(previous, timezone.utc).strftime('%Y-%m')
        with self.store.db:
            owned = {p.id for p in settings.peers if p.owner == settings.local_user and p.transport == 'local'}
            for delivery in self.store.db.execute("SELECT id,group_id FROM deliveries WHERE state='pending' AND group_id IS NOT NULL").fetchall():
                if delivery['group_id'] not in owned:
                    self.store.db.execute("UPDATE deliveries SET state='cancelled',detail='Group is no longer monitored by this owner' WHERE id=?", (delivery['id'],))
            for row in self.store.db.execute('SELECT * FROM destinations').fetchall():
                d = self.decode(row['config'])
                if not d.enabled:
                    continue
                groups = [p for p in settings.peers if p.owner == settings.local_user and p.transport == 'local' and (not d.groups or p.id in d.groups)]
                for group in groups:
                    events = self.store.db.execute('SELECT * FROM status_events WHERE group_id=? AND created>? ORDER BY id DESC LIMIT 1', (group.id, row['since'])).fetchall()
                    for event in events:
                        if event['state'] == 'green' and not d.recovery:
                            continue
                        # A noisy group gets at most one automatic message per five
                        # minutes; suppressed transitions remain in status history.
                        recent = self.store.db.execute("""SELECT 1 FROM deliveries d JOIN status_events e ON d.event_key='status:' || e.id
                            WHERE d.provider=? AND d.group_id=? AND e.state=? AND d.created>?""", (d.provider, group.id, event['state'], now - 300)).fetchone()
                        if not recent and now - event['created'] < 300:
                            self.enqueue(d.provider, f"status:{event['id']}", event['message'], group.id)
                    if d.monthly:
                        summary = report(self.store, group.id, month, now)
                        if summary['period_seconds'] > summary['seconds']['unknown']:
                            message = (f"{group.name} · {month} (UTC): available {summary['available_days']:.2f} days; "
                                       f"partial {summary['seconds']['yellow']/3600:.2f}h; unreachable {summary['seconds']['red']/3600:.2f}h; "
                                       f"unknown {summary['seconds']['unknown']/3600:.2f}h; device incidents {summary['device_incidents']}.")
                            delays = summary['delays']
                            message += f" Delayed checks {delays['count']}"
                            if delays['worst_ms'] is not None:
                                message += f"; worst {delays['worst_ms']:.2f} ms"
                            message += '. Delays still count as reachable.'
                            message += ' Delay totals cover recorded checks since delay logging began.'
                            self.enqueue(d.provider, f'month:{group.id}:{month}', message, group.id)

    async def deliver_once(self):
        async with self.lock:
            rows = self.store.db.execute("SELECT * FROM deliveries WHERE state='pending' AND next_attempt<=? ORDER BY id LIMIT 4", (self.clock(),)).fetchall()
            for row in rows:
                d = self.destinations().get(row['provider'])
                if not d or not d.enabled:
                    continue
                if not row['event_key'].startswith('month:') and self.clock() - row['created'] > 900:
                    with self.store.db:
                        self.store.db.execute("UPDATE deliveries SET state='expired',detail='Queued alert expired after 15 minutes' WHERE id=?", (row['id'],))
                    continue
                await self.deliver(row, d)

    async def test(self, payload):
        async with self.lock:
            destination = self.resolve(payload, test=True)
            recent = self.store.db.execute("SELECT 1 FROM deliveries WHERE provider=? AND event_key LIKE 'test:%' AND created>?", (payload.provider, self.clock() - 60)).fetchone()
            if recent:
                raise TestRateLimited('Wait a minute before sending another test')
            key = 'test:' + uuid4().hex
            with self.store.db:
                self.enqueue(payload.provider, key, 'Ping_A_Friend: your test notification. Monitoring status has not changed.')
            row = self.store.db.execute('SELECT * FROM deliveries WHERE provider=? AND event_key=?', (payload.provider, key)).fetchone()
            # Draft credentials exist only in memory. Never save them in the
            # queue, retry them later, or enable automatic alerts as a side effect.
            await self.deliver(row, destination, retry=False)
            result = self.store.db.execute('SELECT state,detail FROM deliveries WHERE id=?', (row['id'],)).fetchone()
            return dict(result)

    async def deliver(self, row, d, retry=True):
        if d.provider == 'twilio':
            day = self.clock() // 86400 * 86400
            usage = self.store.db.execute('SELECT attempts FROM sms_usage WHERE day=?', (day,)).fetchone()
            used = usage['attempts'] if usage else 0
            if used >= d.daily_limit:
                with self.store.db:
                    self.store.db.execute("UPDATE deliveries SET state='skipped',detail='Daily SMS request limit reached' WHERE id=?", (row['id'],))
                return
        with self.store.db:
            if d.provider == 'twilio':
                self.store.db.execute('INSERT INTO sms_usage VALUES(?,1) ON CONFLICT(day) DO UPDATE SET attempts=attempts+1', (day,))
            self.store.db.execute("UPDATE deliveries SET state='sending',attempts=attempts+1 WHERE id=?", (row['id'],))
        state, detail, delay = 'accepted', 'Provider accepted the message; recipient receipt is not verified', 0
        try:
            await asyncio.to_thread(self.sender, d, row['message'])
        except DeliveryError as exc:
            state = 'uncertain' if exc.uncertain else 'pending' if retry and exc.retry and row['attempts'] < 2 else 'failed'
            detail, delay = str(exc), 60 * (row['attempts'] + 1)
        except Exception:
            state, detail = 'failed', 'Unexpected delivery failure; credentials and provider response withheld'
        with self.store.db:
            self.store.db.execute('UPDATE deliveries SET state=?,detail=?,next_attempt=? WHERE id=?', (state, detail, self.clock() + delay, row['id']))

    async def loop(self, monitor):
        while True:
            try:
                self.prune_history()
                self.collect(monitor.settings)
                await self.deliver_once()
            except Exception:
                logging.getLogger(__name__).error('Notification worker could not process its queue; monitoring continues')
            await asyncio.sleep(5)

    def history(self):
        return [dict(r) for r in self.store.db.execute('SELECT id,provider,created,state,attempts,detail FROM deliveries WHERE created>=? ORDER BY created DESC,id DESC', (self.clock() - HISTORY_RETENTION_SECONDS,))]

    def prune_history(self):
        cutoff = self.clock() - HISTORY_RETENTION_SECONDS
        with self.store.db:
            self.store.db.execute("DELETE FROM deliveries WHERE created<? AND state!='sending'", (cutoff,))
            self.store.db.execute('DELETE FROM sms_usage WHERE day<?', (cutoff // 86400 * 86400,))
