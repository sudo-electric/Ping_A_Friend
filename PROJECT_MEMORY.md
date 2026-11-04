# Ping_A_Friend project memory

Current-state reference reviewed November 4, 2026 against source 0.2.2 and local
SQLite schema metadata. This replaces the earlier cumulative delivery notes so
superseded plans do not read as current features. Git history retains prior notes.

## Purpose and scope

Ping_A_Friend is a local network tester/dashboard. Each installation owns its
configuration, monitoring data and detailed history. Customer-supplied LAN/VPN/DNS
routes provide connectivity. The app does not configure networking or discover
remote homes. Group names organize tests; they do not create tunnels or select a
network interface. A private address from another network may refer to a different
local device unless a correct route already exists.

The repository is intentionally public, confirmed by the user October 27. This
does not authorize exposing the running dashboard to the public internet. Keep
personal settings, device addresses/history, keys, provider credentials, migration
exports and local environments out of Git. Share checked dist artifacts for a
single-file test build. Preserve live operator settings/data during development.

## Working features

- FastAPI, SQLite, responsive HTML/CSS/JavaScript, native launchers and Compose.
  Source/build version is 0.2.2. One process/worker owns monitoring for a profile.
- Launch-first setup with deferral, then Settings. Users do not edit JSON for normal
  setup. Arbitrary-length groups/device lists, one or more devices per group,
  distinct enabled hosts within each group, optional external TCP paths.
- Strict sequential batches of 2–5 checks (default 2); groups run in order and share
  the limit. The default 15-second interval is a pause after a completed cycle.
  Hardware, disk and cycle duration are practical limits rather than infinite capacity.
- ICMP round-trip or TCP connection time, per-device thresholds, manual rechecks,
  a 90-second default sustained-failure confirmation, incident recovery and local
  owner notifications. Busy rechecks return 409; keep this protection.
- Endpoint changes get new IDs; rename/reorder preserves IDs. Removed definitions
  stop checks but retain history until normal cleanup.
- Device availability: green all reachable (including delayed); yellow some failed;
  red none reachable; unknown missing/stale/unavailable. Latency and external paths
  remain separate. A group diagnostic can warn while availability stays green.
- Every delayed enabled-device check records ID/name, time, method/port, latency
  and the threshold used then. External/disabled targets are excluded. Counts are
  slow observations rather than outage episodes/duration; no pre-upgrade backfill.
- UTC monthly reports: sampled availability, partial/unreachable/unknown time,
  confirmed per-device incidents, delayed-check counts/mean/worst and latest-50 log
  preview. Decimal available days are (green+yellow seconds)/86,400.
- Optional outbound Discord/Slack incoming webhooks, Telegram sendMessage, and
  Twilio SMS. All disabled by default. Tests can use unsaved draft credentials;
  they send a real test without saving/enabling. Actual implementation tests use
  fake senders. The user reported successful live Discord and Slack tests.
- Persistent delivery queue, event deduplication, five-minute state/group/provider
  cooldown, bounded retries, uncertain delivery handling, provider/group choices,
  opt-in recovery/monthly summaries and Twilio default 20 API attempts per UTC day.
  Acceptance is not verified recipient receipt. No new immediate alert for delays.
- Monthly messages use the host clock and previous UTC month once per owned local
  group/provider, when enabled and coverage exists. No external calendar service;
  no automatic backlog beyond the previous month. Reports do not clear histories.

## Owner access and privacy

Normal native/Compose launch enables authenticated LAN access. The persistent
owner key loads automatically. Host-browser bootstrap is loopback-only, one-use,
60 seconds; signed browser cookies last 30 days across restarts. Keys/LAN pairing
links are hidden on ordinary startup, explicitly revealed in owner Settings or
--show-access-key. Resetting the owner key revokes every paired session. All paired
browsers have full configured-operator access, not individual friend accounts.
The user confirmed a Kali machine can pair and view the original host dashboard.

Pairing controls work before monitoring setup. Settings can reveal this host's
link or accept another host's complete /login#key link. The latter navigates the
browser to the original host; no data is copied or synchronized. Host-only mode
remains available. Host validation, same-origin JSON mutations, throttling,
HttpOnly/SameSite cookies, CSP/no-store/no-referrer/no-sniff and forwarded-header
distrust remain. Default HTTP is unencrypted; TLS launch options exist.

Device IP literals start hidden on reload/page restore/backend restart. Reveal is
explicit and temporary, never persisted; hostnames and friendly names remain
readable. External public-path cards are exempt. Settings values remain intact.
Masking is display-only: authenticated APIs/configuration contain real addresses.
No reverse DNS is performed. The tab favicon is an SVG PaP/ascending arrow; main
branding/layout is unchanged.

UI preference: midnight navy background #0b1220, surfaces #121a2b/#172133, text
#e7edf7, muted #9fb0c9, ice blue #7cc7ff and mint #9cffc7. Cards use soft lighting,
amber delays/degradation, red failure and violet unknown/unavailable. Preserve the
existing arrangement; status labels accompany colors. No editor recommendations
are needed in user documentation.

## Database, retention and migration

[docs/SCHEMA.md](docs/SCHEMA.md) is the current table/column reference. The database
has 13 application tables. JSON holds groups/devices/local identity; keys are
separate files. The legacy schema_version marker remains 1 despite compatible
additive tables. Startup creates missing tables/indexes; there is no ordered
schema-upgrade runner or unknown-future-version guard. A specific plaintext-provider
conversion to Fernet is implemented. Do not claim a complete migration framework.

Raw samples default to 30 days (configurable 1–365). Local notifications/deliveries
last 60 days. Availability/device/status/delay events last about 400 days. Active
incidents stay open; resolved incidents survive while retained notifications
reference them. Latest alert-state and delay logging-start markers persist.
Cleanup runs on startup/while running, not while stopped. Notification panels use
local-calendar months, default previews of two local messages/one delivery, and
six-entry scrolling expanded boxes. Month/preview clicks toggle/expand and polling
preserves selection/scroll. There is no fixed notification/delivery display cap.
All active plus the latest 50 resolved incidents are returned separately.

Encrypted .paf export/restore is a separate device-move feature. Current inner
payload is 2; legacy payload 1 is accepted, while the envelope label remains v1.
The owner downloads an encrypted file, retains the original pairing key, stops the
source, and confirms restore on a fresh destination. File plus key unlocks settings,
retained history and provider credentials. Installation keys do not transfer;
destination keys stay its own, providers start disabled and queued/interrupted
sends are cancelled. No remote fetch/stop/erase or ongoing synchronization exists.
Limits: 16 MiB serialized plaintext export; 32 MiB archive input; 500,000 rows per
imported table. Wrong keys, incompatible shapes and configured destinations fail.
Future incompatible schema changes require tested upgrades before release; users
should not manually edit SQL or files for a supported upgrade.

## Security and distribution

Provider settings encrypt with a separate local key; missing/wrong keys fail closed.
POSIX private directories/files use 0700/0600 and key/database symlinks are rejected.
This is not whole-database encryption or protection from a compromised OS account.
Source retains config.json/data paths; frozen Linux defaults to the XDG app-data
profile; Compose persists /data. --data-dir and PAF_* overrides exist.

Release staging allowlists app code/static assets/generic disabled defaults and
license notices. It excludes real settings, data, keys, notes, tests and environments,
then scans decompressed members for private host markers. The Linux x86_64 test
binary is unsigned and built on glibc 2.39. Browser and system ping are needed for
those UI/ICMP features. Only compatible Linux systems are targeted by that binary.

The compiled-server live test was declined earlier. Do not repeat/circumvent that
refusal without fresh authorization or claim end-to-end validation of the final
executable. Source tests and package checks are separate evidence.

GitHub protections were enabled October 27 and settings rechecked November 4:
Dependabot alerts/security-update PRs, weekly pip/Docker updates, secret scanning
and push protection, private vulnerability reporting, CodeQL default setup, and
rules against default-branch force pushes/deletion. Ordinary pushes remain allowed.
Initial CodeQL findings were individually reviewed/dismissed as intentional local
path inputs and fixed-file VM test execution; scanning was not disabled. See
[docs/REPOSITORY_SECURITY.md](docs/REPOSITORY_SECURITY.md) for dated evidence.
Commit/push completed work to the existing public repository after verification;
never include private state. Keep the user's useful README setup reference intact
while correcting stale statements. Do not perform live provider sends without
explicit user authorization.

## Future friend connectivity — discussion only

Latest discussion (October 30): two independently owned instances, each with a
Discord bot, exchange authorized summaries/rechecks/heartbeats through Discord.
The user requested a preview before integration. No bot/Gateway/command processing,
invitation acceptance, friend identities/grants/revocation, heartbeat exchange,
remote rechecks or independent watcher is implemented. Existing Discord support
is outbound webhook delivery. Never treat a webhook as a watchdog or bot receiver.

Proposed relationships need explicit owner acceptance, scoped credentials, selected
shared groups, expiry/replay/deduplication, revocation and honest last-seen status.
Sharing must stay non-transitive. Device addresses/details stay local unless
explicitly shared. The owner pairing key must never be used as a friend token.
Chosen Available/Busy/Do Not Disturb states are also proposals, separate from
measured health. Missing heartbeats do not prove the remote LAN is offline.

Twingate is separately installed/configured customer infrastructure, not an embedded
agent. Earlier Cloudflare relay, Telegram commands, n8n and ntfy ideas remain
unimplemented options. A phone's cellular link does not restore the host's uplink.
Discord as transport would itself be the relay; a watching peer must remain online.

## Validation reference

The latest full source run (November 4) passed 106 Python tests and 15 JavaScript
cases after updating the development pytest pin to patched 9.0.3 for
GHSA-6w46-j5rx-g56g. A fresh runtime/development/build requirements audit found no
known vulnerabilities or skipped dependencies on this platform. The 0.2.2 build audit checked 702 members with no private-marker findings;
ZIP integrity/assets/checksum matched. The initial November 4 documentation review used:
read-only local schema comparison, fresh temporary schema initialization, Markdown
links/inventory/claim checks and existing archive verification. No live database
migration, host restart, network reconfiguration or provider send is authorized
by this documentation cleanup. See [docs/VALIDATION.md](docs/VALIDATION.md).


## November 4 security follow-up

The user requested security/safety checks during the documentation refresh. Fixed
the real development-only pytest advisory by pinning 9.0.3, verified its advisory
range, reran 106 Python/15 JavaScript cases, and audited runtime/development/build
requirements successfully. Rechecked existing GitHub controls and open CodeQL/secret
alerts (zero); preserve real dependency alerts until manifest processing resolves
them rather than dismissing affected pins. No runtime dependency, live database,
credential, provider send, host network or compiled-server execution was changed.
