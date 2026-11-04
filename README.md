# Ping_A_Friend

A local network monitoring application. Documentation reviewed November 4, 2026 against version **0.2.2**. Python FastAPI, SQLite, and a responsive dashboard with a midnight blue background and softly illuminated cards: green reachability, blue latency, turquoise network status, amber warnings, red failures, and muted violet unavailable states. No frontend build tooling required.

## What works today

- Continuous ICMP/TCP checks organized into named local test groups, with no fixed device or group count cap. Optional external network-path checks.
- ICMP round-trip measurements, or optional TCP connection checks with explicitly different labels. Per-target delay thresholds.
- A manual **Recheck now** button. Failing checks open a pending incident. Continued failures for 90 seconds confirm it and save one local host notification per incident. Recovery closes it; another failure starts a new window.
- Persistent checks, incidents, availability summaries, delayed-response records, and delivery history in SQLite. Raw samples default to 30 days; local notifications/delivery history last 60 days; availability/device/status/delay events last about 400 days. Active incidents remain, and referenced resolved incidents can outlive raw samples.
- UTC monthly reports with sampled availability, confirmed device incidents, and per-device delayed-check counts/average/worst latency. Optional outbound Discord, Slack, Telegram, and Twilio notifications, with draft-before-save testing and opt-in monthly/recovery messages.
- Encrypted installation export/restore to a fresh host, or browser pairing to keep using the original host. Both controls are available before device setup.
- Private provider credential storage and temporary device-address masking. See [security](SECURITY.md) and [data handling](docs/DATA_HANDLING.md) for the protection boundaries.
- Independent peer definitions, ownership, view grants, recheck grants, and permission-filtered API responses. These are local policy rules, **not remote login or peer authorization**.
- A transport interface, working local transport, and explicit unavailable remote transport. Remote peers are never silently checked through the local adapter.
- Authenticated LAN dashboard access, automatic persistent owner-key setup and browser pairing, same-origin mutation checks, host-header restrictions, validated configuration, and subprocess execution without a shell.

## Start locally (recommended for the first LAN test)

Install Python 3.11+ (3.12 recommended). Open a terminal in the project folder containing `start.sh` (the repository root after cloning).

**macOS / Linux:**

```sh
sh start.sh
```

**Windows PowerShell:**

```powershell
.\start.ps1
```

The launcher creates a local Python environment, installs the runtime dependencies,
and starts the app with LAN access enabled. The host browser opens and signs in
automatically. The access key is generated and loaded automatically, then reused
on future starts. On macOS/Linux it uses `uv` if available; otherwise Python's
`venv` and `pip` must be installed (on Ubuntu/Debian, install `python3-venv`).

On the host, the dashboard is **http://127.0.0.1:8000**. If automatic browser
pairing did not open, stop the app and restart with
`sh start.sh --no-browser --show-access-key` to reveal a key deliberately and sign
in there. First launch shows **Set up your monitoring** after automatic pairing:

1. Choose your local display name and a batch size: **2, 3, 4, or 5** simultaneous checks.
2. Name your first group, for example **Basic tests**, and use **Add device** for
   as many devices as you want. Use **Add group** for **Extended tests**, **IoT**,
   or another network/location. Each group needs at least one device; addresses
   must be distinct within a group.
3. Enter addresses already reachable from this computer. Find them in device
   settings or your router's connected-device list. Use Ping (ICMP), or TCP with
   a known listening port. Internet path checks are optional per group and start
   disabled on a new installation.
4. Select **Save and start monitoring**. Changes apply without restarting.
   Each group has its own **Recheck now** button; **Show group** filters the view.

The default batch size is two: four devices run as **2, then 2**; two devices run
together. Each whole batch finishes before the next starts, including when one
check is slower than the others. Groups are processed in saved order, sharing the
same limit; external checks also count toward it. The dashboard shows the current
group and batch while checking. Larger lists take longer to cycle; the configured
interval is a pause after the full cycle, not a per-device polling guarantee.
Freshness and incident gap limits account for the worst-case batched cycle.

There is no fixed application cap on devices or groups; available memory, disk,
and cycle duration remain practical limits. Removing a device or group stops its
checks after saving and keeps stored history until normal retention prunes it.
Changing an address/method/port starts fresh measurements; renaming or reordering
an unchanged device preserves its history ID.

Groups are labels for local tests, not VPNs or remote agents. If a target is at
another location, the customer supplies a working VPN, route, DNS, and firewall
configuration. Every check still originates on this computer/container. The app
does not establish tunnels or change routing, and group names do not select a
network interface or resolve overlapping private address ranges.

You can choose **Set up later** and return through **Set up monitoring**. After
setup, **Settings** lets you change these values. No text editor or configuration
file preparation is required. Your display name identifies this local installation;
it is not an authenticated account. Missing/invalid input is explained in the form.

Native settings are saved to `config.json`, and history is stored in SQLite.
Existing configurations are loaded automatically. Keep the terminal running;
**Ctrl+C** stops the observer. Use one server worker. During development, `--reload`
is optional but resets pending incidents when it restarts the process.

The app uses the system `ping` command. On Linux, install `iputils-ping` if missing;
on macOS and Windows it is ordinarily provided by the OS. TCP success means that
**that port accepted a connection**, not that every service is healthy. The app
does not discover or scan your LAN.

The optional external checks are TCP connections to `1.1.1.1:443` and
`8.8.8.8:53`. These test reachability, not DNS correctness, HTTP content, throughput,
or your ISP's full health. Existing configurations retain their external-check
choices. A healthy device group without external checks does not claim that
internet access was tested. Advanced external targets and timing settings remain
available in configuration only.

## Open from another laptop, phone, or tablet

Run the normal launcher; the host browser pairs automatically with a one-use,
short-lived token. In **Settings → Pair another browser**, explicitly reveal
the private LAN pairing links or key for another device. Startup does not print
owner credentials or LAN addresses by default. For a headless source install,
use `sh start.sh --no-browser --show-access-key` to reveal them deliberately. `127.0.0.1` refers to the device you are
currently using, so it is only the correct address on the host itself.

Pairing is a one-time step per browser/address for 30 days. Sessions survive app
restarts; the host's key is loaded automatically from `data/access.key`, created
with owner-only file permissions on POSIX systems. Keep that key and pairing
links private: they grant full access to this installation's settings, status,
and rechecks. They are not separate user accounts or scoped friend invitations.
The link carries the key in a URL fragment, which is not sent in HTTP requests;
the sign-in page removes it before exchanging it for an HttpOnly session cookie.
Use **Disconnect this browser** to clear that browser's cookie. To revoke all
paired browsers and replace the key, stop the app and start with:

```sh
sh start.sh --reset-access-key
```

The host browser pairs automatically with the new key. Existing device
configuration/history are preserved. Add `--no-browser` for a headless host, or
`--port 8001` to choose another port. Windows accepts these same launcher options.

Devices need a route to the host and inbound TCP access to the chosen port through
the host firewall. The app does not change firewall rules, router forwarding,
VPNs or Twingate policies. For Twingate, define/permit the host's reachable LAN
address and port; the Connector must be able to reach that address. An existing
Connector does not make a loopback-only service reachable by itself. Customer
VPN/Twingate routes are not established or verified by the application tests. The
user has separately confirmed a Kali machine can pair and display the dashboard.

HTTP is unencrypted: use the default only on a trusted LAN. To encrypt the
application connection, supply a trusted TLS certificate and key with
`--certfile /path/to/cert.pem --keyfile /path/to/key.pem`. A Twingate connection
does not automatically encrypt an HTTP hop between its Connector and the app.
Private IP literals and the host's computer name are accepted; add exact private
DNS aliases via `PAF_ALLOWED_HOSTS` (comma-separated) if needed. Arbitrary hostnames
and cross-origin mutations remain blocked.

For host-only access without browser sign-in:

```sh
sh start.sh --local-only
```

That mode binds loopback and rejects non-loopback clients even if somebody changes
the Uvicorn bind address manually. Direct `uvicorn app.main:app` retains this
host-only mode unless `PAF_LAN_MODE=1` is explicitly supplied. Native and Compose
launchers use one worker. No public internet exposure or router port forwarding
is configured.

## Docker Compose

Install Docker Engine/Desktop with Compose v2, then run:

```sh
docker compose up --build -d
```

Open the host address on port 8000 and use the same setup form. Run
`docker compose exec ping-a-friend cat /data/access.key` to explicitly reveal
the generated key for initial browser pairing. Keep that command output private. Container startup does not open a desktop browser. No `config.json` copy or
bind mount is required. Settings, the access key, and SQLite history are saved in the `paf-data`
named volume and survive container recreation. `docker compose logs -f` shows logs.
`docker compose down` stops the app and preserves data; `docker compose down -v`
deletes settings, the access key, and history.

Existing installations should preserve the named volume and keep a private backup
before upgrading. Current Compose stores settings and history together under
`/data`; do not delete the volume to update the application. For moving between
hosts/profiles, use the dashboard transfer flow in [DISTRIBUTION.md](docs/DISTRIBUTION.md).
There is no general importer for every older manual bind-mount layout.

Compose publishes port 8000 on the host interfaces with owner-key authentication
required. Set `PAF_BIND_IP=127.0.0.1` when invoking Compose to restrict its host
publication to loopback. Authenticated browsers act as the configured local
operator; this is shared owner access, not per-person friend authorization. Docker observes from the container, which can have different routes and
firewall behavior, particularly on Docker Desktop or VPN setups. It includes
`iputils-ping` and only adds `NET_RAW`; it does not use host networking or run
privileged. Validate reachability, use a suitable TCP check, or run Python natively
if container LAN routing prevents checks.

## What the dashboard means

| State | Meaning |
|---|---|
| Responding | All devices in this group respond, along with any enabled external checks. With no external checks, internet health is explicitly untested. |
| Delayed | Checks respond, but one exceeds its configured threshold. Shown in amber, without creating a down incident. |
| Needs a look | A device fails while another responds, or an enabled external endpoint fails. |
| Group unreachable | Every device in this group fails from this observer. Power, firewall rules, a bad route, or observer isolation can also cause this. |
| Set up needed | A LAN device is disabled. The group is not presented as healthy. |
| Unknown / Stale | A measurement is missing, a probe cannot run, or the observer has not updated within two worst-case configured cycles. |
| Unavailable | Remote transport has not been implemented. |

There is a **separate incident per failing target**. The first failure starts its 90-second window. A failed manual recheck does not postpone the deadline. A successful or delayed response closes the incident, including a pending incident before notification. The confirmation is recorded on the first subsequent **failing check at or after 90 seconds**, so polling and probe duration can add a few seconds. This is not a hard realtime timer.

Unknown measurements or an excessive observation gap restart pending confirmation. A process restart closes pending incidents, since downtime is not observed. Confirmed incidents survive a restart and remain open until a successful response; unknown readings do not pretend to prove recovery. Changing targets or removing them does not erase history. Keep IDs stable for the same peer/device; use a new ID for a different device so histories do not mix.

The **Local notifications** panel saves an owner-addressed message once per confirmed target incident. It is separate from optional provider messages. Discord/Slack webhooks, Telegram, and Twilio SMS can send group alerts when configured; direct email and browser push are not implemented. Local notification/delivery history lasts 60 days, starts with two notices/one attempt, and expands by month into a six-entry scroll box. Sending a monthly report does not clear these lists.

In **Notifications & integrations**, enter a provider and use **Send test notification** before saving. A test sends one real message but does not save or enable the draft. Automatic providers start disabled. Monthly reporting uses the host clock and previous **UTC** calendar month, once per owned local group/provider with recorded coverage. No external calendar is connected. Group summaries include delayed-check totals/worst latency; the dashboard includes per-device details and the latest 50 delayed readings. See [NOTIFICATIONS.md](docs/NOTIFICATIONS.md) for exact delivery and retention behavior.

## Independent peers and permissions

Each peer owns its own targets and has direct grants. For example, Friend's peer can grant Owner view/recheck access:

```json
"owner": "friend",
"grants": [{"user": "owner", "recheck": true}]
```

For this local configuration example, Friend can have a separate `parents` peer with an empty grants list. Owner's configured local dashboard cannot view that peer or recheck it. Grants are **not transitive**: sharing Friend's network does not share his parents' network. These rules are enforced on read and recheck endpoints and tested.

`local_user` is an operator-selected identity, not authentication. It cannot be changed via an API query or request header, but someone who can edit local files can change it. LAN sign-in grants access as that configured operator; it does not turn local usernames into authenticated personal accounts. All configured **local** peers are checked from this same observer, even if hidden from the selected local dashboard. Putting a private address from another home into a local peer does not establish a route or contact your friend's network.

For a future remote peer, set `"transport": "remote"`. Its dashboard will explicitly say **Unavailable** and manual recheck will return 501. No connection is attempted. See [the current architecture and proposed friend design](docs/ARCHITECTURE.md).

## Tests and API

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests use temporary SQLite databases, a controlled clock, fake transports, and real localhost TCP sockets. They do not depend on a friend's network or public internet. They cover the 89/90-second boundary, recovery, deduplication, restart/gap handling, stale data, status classification, peer isolation, read-only grants, cross-origin protection, configuration validation, and transport behavior.

- `GET /healthz`: minimal process availability (`{"status":"ok"}`); observer errors are in authenticated `/api/status`. An available process does not imply devices are healthy.
- `GET /api/status`: permitted peers, latest observations, incident histories, and owner notifications.
- `POST /api/peers/{id}/recheck`: permitted local peer, JSON body `{}`. A running cycle returns 409; view-only returns 403; hidden peer returns 404; remote returns 501.
- `GET /api/reports/{YYYY-MM}`: UTC reports for owned local groups, including availability, incidents and delayed checks.
- `GET/POST /api/notifications/settings`: read redacted provider settings/history or save a provider.
- `POST /api/notifications/test/{provider}`: send an explicit test using draft/saved credentials.
- `GET /api/access/pairing`: reveal this installation’s key/links (LAN owner access).
- `POST /api/access/export` and `/api/access/import`: encrypted transfer, distinct from browser pairing.
- `GET /docs`: generated API explorer (its standard UI assets require internet).

`GET /api/setup` reads all owned local test groups and the batch size; `POST /api/setup` validates, saves, and applies them. Older single-network setup payloads are still accepted. Groups reuse the existing peer IDs internally, so existing status/recheck API paths remain compatible.

`PAF_CONFIG` overrides the writable config path; `PAF_DB` overrides the database path. If the settings file does not exist, startup loads safe defaults and offers setup. Configuration errors fail startup with a validation message. Numeric settings and all permitted fields are defined in `app/config.py`. Main dependency versions are pinned in `requirements.txt`; `requirements-runtime.txt` includes the exact tested runtime dependency set. Update and retest pins deliberately.

## Proposed friend connections

The latest design discussion explores full Discord bots between separately owned
instances for invitations, selected status sharing, rechecks and heartbeats through
Discord. Only a preview has been requested; none of those bot/friend features is
implemented. Current Discord integration sends outbound webhook notifications.

Embedded Twingate integration, friend accounts/consent/revocation, remote agents,
heartbeat watching and independent loss-of-contact alerts remain future work.
Twingate or another customer VPN can already supply routes to the local dashboard
or devices. That route does not add scoped friend permissions. Missing contact
must mean stale/unknown rather than a proven remote network outage. See
[ARCHITECTURE.md](docs/ARCHITECTURE.md) for the implemented/proposed boundary.

## Requirement sources

The project evolved from the original network-testing requirements and subsequent
local dashboard, notification and independent-instance sharing discussions. Today
each installation uses its own SQLite store; a shared cloud database/friend service
is not implemented.

Implementation references: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/) for observer startup/shutdown and [Docker Compose networking](https://docs.docker.com/compose/how-tos/networking/) for container networking. See [VALIDATION.md](docs/VALIDATION.md) for dated evidence and remaining verification limits.


## Single-file test build and privacy audit

See [single-file distribution](docs/DISTRIBUTION.md) and the
[security sweep report](docs/SECURITY_REVIEW.md) for the Linux test build,
private-data separation, credential migration, and remaining limitations.

## Security and data handling

See [SECURITY.md](SECURITY.md) for protections, known limits, and private vulnerability
reporting, and [data handling](docs/DATA_HANDLING.md) for what is stored and sent.

## Database reference

[SCHEMA.md](docs/SCHEMA.md) lists the current 13 application tables and explains why
the legacy database marker remains `1` while the app is `0.2.2` and transfer payload
is `2`. Compatible tables are initialized at startup; no general ordered schema
migration framework is implemented. Definitions and keys remain outside SQLite.

## Documentation map

| Reference | What it explains |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | How the current app works and which friend/bot features are only proposed. |
| [Database schema](docs/SCHEMA.md) | Current tables/columns, retention, version numbers, and upgrade limitations. |
| [Notifications and reports](docs/NOTIFICATIONS.md) | Provider setup, delivery, UTC monthly scheduling, and delayed-response logs. |
| [Data handling](docs/DATA_HANDLING.md) | Information collected, stored, logged, and transmitted. |
| [Distribution and transfers](docs/DISTRIBUTION.md) | Single-file builds, private profiles, browser pairing, and moving data. |
| [Security policy](SECURITY.md) | Protections, limits, and private vulnerability reporting. |
| [Validation](docs/VALIDATION.md) | Dated test/build evidence and what remains unverified. |
