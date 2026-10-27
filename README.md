# Ping_A_Friend

A working, local-first starter for the FriendWatch / **Friend's Network Test** idea. Python FastAPI, SQLite, and a responsive dashboard with a midnight blue background and softly illuminated cards: green reachability, blue latency, turquoise network status, amber warnings, red failures, and muted violet unavailable states. No frontend build tooling required.

## What works today

- Continuous ICMP/TCP checks organized into named local test groups, with no fixed device or group count cap. Optional external network-path checks.
- ICMP round-trip measurements, or optional TCP connection checks with explicitly different labels. Per-target delay thresholds.
- A manual **Recheck now** button. Failing checks open a pending incident. Continued failures for 90 seconds confirm it and save one local host notification per incident. Recovery closes it; another failure starts a new window.
- Persistent samples, incidents, and local notifications in SQLite; configurable 30-day retention of old samples and resolved incidents.
- Independent peer definitions, ownership, view grants, recheck grants, and permission-filtered API responses. These are local policy rules, **not remote login or peer authorization**.
- A transport interface, working local transport, and explicit unavailable remote transport. Remote peers are never silently checked through the local adapter.
- Authenticated LAN dashboard access, automatic persistent owner-key setup and browser pairing, same-origin mutation checks, host-header restrictions, validated configuration, and subprocess execution without a shell.

## Start locally (recommended for the first LAN test)

Install Python 3.11+ (3.12 recommended). Open a terminal in the extracted `ping_a_friend` folder.

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

On the host, open **http://127.0.0.1:8000** if the browser did not open. First
launch shows **Set up your monitoring** after automatic pairing:

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
VPN/Twingate access and an actual second physical laptop were not verified by
the application tests.

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

**Upgrading from the earlier Compose version:** an old host `config.json` bind mount
is no longer used. Re-enter your devices through setup, or migrate the existing
configuration to `/data/config.json` in the volume before starting the new version.
Existing SQLite history stays in the same volume.

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

The **Local notifications** panel is the initial host notification mechanism. It saves a message addressed to the configured peer owner and shows it only to that local user. It does **not** send email, SMS, browser push, or messages to someone else's computer. Duplicate failures in the same incident do not create duplicate notifications. History remains visible in the peer's incident section after recovery.

## Independent peers and permissions

Each peer owns its own targets and has direct grants. For example, Friend's peer can grant Owner view/recheck access:

```json
"owner": "friend",
"grants": [{"user": "owner", "recheck": true}]
```

Then Friend can have a separate `parents` peer with an empty grants list. Owner's configured local dashboard cannot view that peer or recheck it. Grants are **not transitive**: sharing Friend's network does not share his parents' network. These rules are enforced on read and recheck endpoints and tested.

`local_user` is an operator-selected identity, not authentication. It cannot be changed via an API query or request header, but someone who can edit local files can change it. LAN sign-in grants access as that configured operator; it does not turn local usernames into authenticated personal accounts. All configured **local** peers are checked from this same observer, even if hidden from the selected local dashboard. Putting a private address from another home into a local peer does not establish a route or contact your friend's network.

For a future remote peer, set `"transport": "remote"`. Its dashboard will explicitly say **Unavailable** and manual recheck will return 501. No connection is attempted. See [the architecture and phase plan](docs/ARCHITECTURE.md).

## Tests and API

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests use temporary SQLite databases, a controlled clock, fake transports, and real localhost TCP sockets. They do not depend on a friend's network or public internet. They cover the 89/90-second boundary, recovery, deduplication, restart/gap handling, stale data, status classification, peer isolation, read-only grants, cross-origin protection, configuration validation, and transport behavior.

- `GET /healthz`: process availability and observer error. An available process does not imply devices are healthy.
- `GET /api/status`: permitted peers, latest observations, incident histories, and owner notifications.
- `POST /api/peers/{id}/recheck`: permitted local peer, JSON body `{}`. A running cycle returns 409; view-only returns 403; hidden peer returns 404; remote returns 501.
- `GET /docs`: generated API explorer (its standard UI assets require internet).

`GET /api/setup` reads all owned local test groups and the batch size; `POST /api/setup` validates, saves, and applies them. Older single-network setup payloads are still accepted. Groups reuse the existing peer IDs internally, so existing status/recheck API paths remain compatible.

`PAF_CONFIG` overrides the writable config path; `PAF_DB` overrides the database path. If the settings file does not exist, startup loads safe defaults and offers setup. Configuration errors fail startup with a validation message. Numeric settings and all permitted fields are defined in `app/config.py`. Main dependency versions are pinned in `requirements.txt`; `requirements.lock` includes the exact tested runtime dependency set. Update and retest pins deliberately.

## Later phase: remote observation and Twingate

**Not implemented:** Twingate integration, remote peer discovery, authenticated agents, approval/revocation of remote sharing, encrypted transport, heartbeat exchange, remote notification delivery, or true peer-to-peer connectivity. No Tailscale dependency, domain, Cloudflare tunnel, or inbound port forwarding is required now.

A realistic next step is one local observer at each home, with explicitly authorized and authenticated exchange of **health summaries** over an agreed private/outbound transport. Twingate may help provide a private route, but a route alone does not implement application permissions or monitor two remote devices. Before enabling remote use, add authenticated users/agents, owner-controlled scoped grants, revocation, replay protection, stale-heartbeat handling, and TLS. Remote observations must retain their origin; a missing heartbeat must not be labeled a proven remote LAN outage.

## Editor choice

**VS Code is the best general choice for this app**: it fits Python, web UI, tests, and Docker in one workspace. Positron is a good alternative when your work centers on Python/R data science and interactive analysis. This project uses ordinary files and works in either editor.

Open the extracted `ping_a_friend` folder as your workspace. Included VS Code settings select `.venv`, enable pytest discovery, and provide a loopback-only debugger launch. Install the suggested Python extensions and the development requirements before running tests in the editor. You can initialize version control with `git init`; the archive excludes live configuration, databases, and environment folders.

## Requirement sources

Based on the attached the original network requirements document, with the subsequent independent-dashboard sharing requirement and the requested name **Ping_A_Friend**. The PDF's global database idea is implemented as one local SQLite store for this installation; no global cross-user cloud database or implicit sharing is claimed.

Implementation references: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/) for observer startup/shutdown and [Docker Compose networking](https://docs.docker.com/compose/how-tos/networking/) for container networking. See `docs/VALIDATION.md` for the checks actually run on this delivery.


## Single-file test build and privacy audit

See [single-file distribution](docs/DISTRIBUTION.md) and the
[security sweep report](docs/SECURITY_REVIEW.md) for the Linux test build,
private-data separation, credential migration, and remaining limitations.
