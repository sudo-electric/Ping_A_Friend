# Ping_A_Friend project guidance

Read `PROJECT_MEMORY.md` before changing the product or its architecture.
It records the user's requirements and distinguishes shipped functionality
from the preferred future sharing design. Update it when the user changes
these decisions or a planned feature becomes implemented and verified.

- Use the app name **Ping_A_Friend**. FriendWatch and Friend's Network Test are earlier names.
- Ordinary setup happens after launch in the dashboard; users may defer it and
  return via Settings. Do not require a text editor or a pre-created configuration.
- The existing app performs local ICMP/TCP checks, external path checks,
  90-second incident confirmation, manual rechecks, and local notifications.
- Current priority: a local tester/dashboard with unlimited-length device/group
  lists and strict sequential batches of 2–5 checks (default 2). Customer-provided
  VPNs/routes supply connectivity; the app does not configure networking.
- Optional future Telegram phone access for an
  iPhone is planned, not implemented. Discord is an evaluated alternative.
  Cloudflare/Twingate sharing are earlier future options. Do not require inbound
  router port forwarding for the proposed outbound Telegram integration.
- Each user owns their installation, devices, configuration, and detailed
  history. Sharing grants access to selected status/actions, not device ownership.
- Friend access requires owner consent and independent, revocable grants.
  Adding Friend's parents must not implicitly share them with Owner.
- Keep chosen availability (Available/Busy/Do Not Disturb) separate from
  measured network health. Missing remote updates mean stale/unknown,
  not a proven network outage.
- Cloudflare sharing, authenticated accounts, friend invitations, remote
  rechecks, and remote notifications are planned, not working features.
  Never claim editable local usernames are authenticated accounts.
- Standard native/Compose startup supports LAN access with an automatically
  generated persistent owner key and 30-day browser pairing. All paired browsers
  act as the configured owner; this is not per-person friend authorization.
  Keep --local-only as an option, retain same-origin/host protections, and never
  publish an unauthenticated LAN dashboard. Do not alter customer firewall/VPN
  settings or configure public router forwarding without authorization.

Use one Uvicorn worker. For code changes, run `python -m pytest -q` with
`requirements-dev.txt` installed. For documentation-only updates, verify
the files and downloadable archive; no new tests are needed.

October 19 implementation direction: the user has authorized development of
private friend presence/sharing, monthly availability reporting, and optional
Twilio, Telegram, Discord, and Slack notifications. Prefer provider-independent
interfaces. The first new increment implements local owner notifications and
reports only; see docs/NOTIFICATIONS.md for exact semantics and remaining shared
service work. Earlier Telegram-only priorities do not exclude the other providers.
Do not mistake local display names or the LAN owner key for friend authentication.

Address privacy: monitored device IP literals are hidden on every dashboard start/reload and backend
restart, including Settings and legacy notification/error text. Hostnames and device
names remain identifiers. Revealing addresses is an explicit, temporary browser
choice and must never be persisted. Preserve actual addresses for monitoring/saves;
this display feature is not an authorization boundary or DNS discovery feature.

External path cards are exempt from address screening; their addresses and probe
details remain visible even when device-address privacy is enabled.

Notification and delivery history: keep a rolling 60 days, independent of raw
sample retention and the 400-day availability summaries. Start compact with two local notifications or one delivery attempt; clicking a
month toggles a six-entry scroll box, and clicking a preview expands it. Use
local-calendar month selectors; current month starts compact on rollover,
older months stay collapsed/selectable. No fixed 50/30-entry history display cap.
Expire old notification entries without resolving/removing active incidents.


Security/distribution: share only checked dist/ artifacts. Never stage data/, live
config.json, keys, dotenv files, certificates, project memory, tests, or virtual
environments into a binary. Keep generic disabled defaults and preserve existing
private operator data. Provider rows encrypt on startup with a separate private
installation key; do not silently replace a missing/wrong key or migrate a live
old-version database behind its running process. Normal startup hides credentials;
Settings reveal and --show-access-key are explicit. Browser bootstrap is one-use,
loopback-only, 60 seconds; installation-specific cookies preserve legacy support.
Use private per-user data paths for frozen builds and retain source path support.
The Linux one-file runtime test was declined in this session; do not repeat it
without fresh authorization or claim the final binary was run end-to-end.

Delayed-response history: log each enabled device check reported delayed, including
name/ID, time, ICMP/TCP method/port, measured latency and the then-current threshold.
Retain 400 days separately from raw samples. Keep delayed checks reachable and do
not treat them as confirmed outages or trigger immediate provider alerts for them.
Monthly reports show per-device counts/mean/worst and a bounded scrolling preview;
full-month totals must not be capped by that preview. Do not invent pre-upgrade
records. Preserve logs in v2 migration exports and accept legacy v1 exports.
