# Current architecture

Reviewed November 4, 2026 against application 0.2.2. This document describes working
code; proposed friend/bot connections are listed separately below.

## Runtime

```text
Paired browser on host / LAN / customer-provided private route
  → FastAPI owner-authenticated dashboard APIs
      ├─ Monitor → sequential groups → batches of 2–5 ICMP/TCP probes
      ├─ SQLite → checks, incidents, availability and delayed-response history
      ├─ Notifier → durable queue → optional Discord / Slack / Telegram / Twilio
      └─ Transfer → encrypted file export / explicit restore to a fresh host
```

One process and one Uvicorn worker own a profile. Startup loads JSON configuration,
initializes compatible SQLite tables, resets pending failure confirmation, prunes
expired history, and initializes encrypted provider settings. Background tasks run
monitoring and notification delivery. Stopping the server stops both; closing a
browser does not. Standard Compose restarts the container automatically; native
launchers do not install an OS background service.

## Settings, identity and access

Setup happens after launch and may be deferred. The dashboard configures owned
local groups/devices, batch size, per-device thresholds and optional external
checks. IDs stay stable across renaming/reordering; changing host/method/port
creates a new target ID. Removed definitions stop checks but do not erase history.
Changes save atomically to JSON and apply under the monitor lock without restart.

Standard native/Compose startup enables LAN owner-key authentication. Host-browser
bootstrap is one-use, loopback-only and expires after 60 seconds. Other browsers
pair using an explicitly revealed key/link; signed sessions last 30 days and survive
restarts. Key reset revokes all sessions. Pairing is available before setup.
**Connect to an existing host** opens its dashboard; it does not copy data.

All paired browsers act as the configured local operator. Existing per-group
owner/view/recheck grants filter that configured identity; they are not separate
personal logins or friend invitations. A hidden group returns 404 for rechecks;
a view-only grant returns 403. Settings cannot edit another configured owner's
groups or switch to an existing configured identity.

Host validation, same-origin JSON mutations, cookie controls and login throttling
apply. The launcher does not trust forwarded client headers. Default LAN HTTP is
unencrypted; TLS certificate/key options exist. `--local-only` binds loopback,
skips sign-in, and rejects non-loopback clients at the application layer. Direct
Uvicorn startup defaults to local-only unless LAN mode is explicitly enabled.

## Checks and incident semantics

There is no fixed group/device-count cap. A group needs at least one device.
Groups and cycles run sequentially; only the current batch's tasks are created.
The default batch size is 2, configurable to 3, 4 or 5; external probes share that
budget. The interval (default 15 seconds) is a pause after the cycle, not a fixed
sampling interval for every device. Freshness/gap limits account for worst-case
batch duration. Manual rechecks share the lock and return 409 while busy.

ICMP records ping round-trip time. TCP records connection-establishment time,
including resolution/scheduling where applicable, then closes without requesting
content or performing a TLS handshake. Checks use existing host/container routes.
Groups do not select tunnels, interfaces, or solve overlapping address spaces.
The customer supplies VPN, DNS, firewall and Twingate Resource access if needed.
The remote transport adapter returns unavailable and rechecks return 501.

The first failed check opens a target incident. A later failing check at/after the
confirmation window (default 90 seconds), with sufficiently continuous observed
failures, confirms it and saves one local notification in the same transaction.
Healthy/delayed responses resolve it. Unknown results or excessive gaps reset
pending confirmation; unknown readings do not resolve confirmed failures. A
restart closes pending incidents so unobserved downtime cannot confirm them.

Device availability is distinct from latency and external paths: green means all
enabled devices reachable, yellow means some reachable/some failed, red means none
reachable, and unknown covers missing/stale results. A delayed device is reachable.
The separate group diagnostic card can still warn about delay or an external
failure. Every enabled-device delayed reading is also logged with its threshold
snapshot. Logging starts after the feature is installed; earlier data is not
reconstructed.

## Database and upgrades

The current database has 13 application tables. Configuration and keys live
outside SQLite. [SCHEMA.md](SCHEMA.md) lists every table/column, retention rule,
constraint, and the distinction between the three version numbers:

- Application release: `0.2.2`.
- Database marker: legacy `schema_version=1`.
- Transfer payload: `2`, with payload `1` still readable.

Compatible missing tables/indexes are created at startup. There is no ordered
schema migration framework or future-version compatibility guard; the marker
alone does not validate the layout. There is a specific legacy provider-settings
encryption conversion. Changes to existing column layouts/data meaning require
tested conversion code before release. Users should not edit databases manually.
No database version or data was changed for this documentation review.

## Reports and notification delivery

SQLite retains raw samples (default 30 days), local notifications/delivery history
(60 days), and availability/device/status/delay events (400 days). Active incidents
remain; referenced resolved incidents can outlive raw samples. History cards start
compact (two local notifications/one delivery), with six-entry scrolling month
panels using the viewer's local calendar. Reports use UTC calendar months.

Reports calculate sampled availability intervals, confirmed per-device events,
and delayed-check counts/mean/worst with a latest-50 scrolling preview. Green plus
yellow counts as available; gaps/expired coverage are unknown. Decimal available
days are seconds divided by 86,400. These are not guarantees of continuous uptime.

Discord and Slack incoming webhooks, Telegram sendMessage, and Twilio SMS are
working optional outbound providers. All start disabled. Owner tests can send
entered draft credentials without saving them. Provider settings are encrypted in
SQLite with a separate key. A persistent queue handles deduplication, cooldowns,
bounded retries, uncertainty and SMS request caps. Monthly summaries select the
previous UTC calendar month, once per group/provider, when enabled and coverage
exists. There is no external calendar connection. See [NOTIFICATIONS.md](NOTIFICATIONS.md).

## Moving an installation

An owner explicitly downloads an encrypted `.paf` file and restores it with the
original pairing key on a fresh destination. Settings, retained histories and
provider settings transfer; installation keys do not. Destination keys remain its
own, providers start disabled and pending/interrupted messages are cancelled.
This is a one-time copy; it does not remotely stop the source or synchronize two
instances. [DISTRIBUTION.md](DISTRIBUTION.md) documents limits and private profiles.

## Proposed friend connections — not implemented

The latest discussion explores two local instances using full Discord bots to
exchange approved summaries, recheck requests and heartbeats through Discord.
Only a preview was requested; no Gateway bot, slash command, bot-to-bot protocol,
invitation, accepted friend relationship, or heartbeat watcher is implemented.
Current Discord support remains an outbound notification webhook.

Any implementation still needs installation identities, explicit selected-group
consent, scoped credentials, acceptance/revocation, expiry/replay protection,
minimized payloads and cross-instance tests. The owner pairing key must not become
a friend token. A missing heartbeat means contact unavailable, not a proven remote
network outage. A watching peer must remain online to detect missed contact.

Twingate can supply a separately configured route; there is no embedded Connector,
Twingate administration integration, n8n connector or Cloudflare relay in the app.
Cloudflare/Telegram command designs were earlier options, not current features.
Chosen personal states (Available/Busy/Do Not Disturb) also remain proposals and
must stay distinct from measured device availability.
