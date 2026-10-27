# Ping_A_Friend project memory

Updated: October 26, 2026. Scope: this project and its future development.

## Product purpose and ownership

Ping_A_Friend helps friends see selected network-health information and help
each other with alerts. Its earlier working names were FriendWatch and
Friend's Network Test. The original requirements came from the attached
the original network requirements document and the subsequent conversation.

Each person runs and owns their own local installation. Friend owns his devices,
monitoring configuration, and detailed history. Owner viewing Friend's shared
status or requesting an authorized test does not transfer ownership or grant
general access to Friend's home network. Owner's installation remains his own.

Sharing is independent and non-transitive. If Friend adds his parents, their
network is a separate relationship; Owner gains no access unless explicitly
authorized. The user wants a social-style status display shared with others,
while monitoring and detailed data stay local. Approved-friends visibility
is the proposed default; unrestricted internet visibility is not authorized.

## Current, working implementation

- Python FastAPI, SQLite, responsive HTML/CSS/JavaScript dashboard, Docker Compose.
- Midnight blue background with dark cards lit by soft gradients and glows,
  rather than pronounced box borders. Healthy reachability glows green, latency
  blue, and network summaries turquoise. Delays/degraded states glow amber,
  failures red, and unknown/stale/unavailable states muted violet. Connection
  loss to the observer changes last-known cards to the unavailable glow; labels
  and explanations remain visible so color is not the only status signal.
  Use the reference portfolio palette for visual styling: background #0b1220, surfaces #121a2b/#172133, text #e7edf7,
  muted text #9fb0c9, ice-blue #7cc7ff and mint #9cffc7 accents, plus monospace
  detail labels. Preserve Ping_A_Friend’s existing section/card arrangement.
  This is the user’s preferred visual direction, including the setup form.
- Continuous local ICMP or TCP checks for configured always-on devices,
  plus separate external network-path checks. Groups accept any number of devices (at least one per group), with no fixed
  device/group count cap. Sample addresses stay disabled until configured.
- Manual recheck, per-target incidents, 90-second sustained-failure confirmation,
  recovery handling, deduplicated local owner notifications, and history.
- Independent peer definitions and local view/recheck policy rules.
- Local transport works. Remote transport explicitly reports unavailable.
- First-launch dashboard setup with Set up later, and Settings for later edits.
  Local display name, named groups, batch size, and device lists (IP/hostname, ICMP/TCP, port,
  latency threshold) are validated, saved atomically, and applied without restart.
  No manual configuration editing is required for normal setup. Changed device
  endpoints get new target IDs so previous measurements are not reused.
- macOS/Linux `sh start.sh` and Windows `start.ps1` launchers create the environment
  and install dependencies. Native settings use config.json; Docker saves settings
  and SQLite in its persistent data volume, without a pre-created config bind mount.
- Standard launch now supports authenticated LAN access; --local-only remains
  available. No router port forwarding is configured.
- The initial delivery passed 22 tests, Docker build/startup, real container
  loopback ICMP, persistence checks, and desktop/mobile visual checks.

The user explicitly understands that today's app is local testing only.
Entering Friend's private IP does not establish remote connectivity and might
address a different device on the observer's own LAN. Friend receives no remote
status or notifications from this starter. Local usernames are editable
configuration, not authenticated accounts. Current notifications are local
dashboard records, not email/SMS/push or delivery to Friend's computer.

## Preferred next direction: Cloudflare friend sharing

The user wants to explore sharing using Cloudflare without requiring Twingate
or another VPN. Prefer this direction over the earlier optional Twingate idea.

A proposed implementation uses Cloudflare Workers and Durable Objects as an
authenticated relay, with each local observer making an outbound connection.
This is a proposed architecture, not an implemented integration, purchased
service, configured Cloudflare account, or approved deployment. A domain or
DNS record alone does not implement sharing. Do not describe relayed messages
as direct peer-to-peer connectivity.

Intended friend flow:

1. Owner sends Friend an invitation.
2. Friend accepts and chooses scoped permissions: view selected status,
   request a recheck, and/or help with notifications.
3. Those grants remain independent and revocable. Routine requests can use
   pre-granted permission; Friend need not manually approve every click.
4. An authorized recheck travels from Owner's instance through the relay to
   Friend's instance. Friend's instance validates the permission and tests its
   own devices locally, then returns only authorized results.

Monitoring, device addresses, configuration, and detailed histories should
remain local by default. Selected shared summaries and requests necessarily
leave the computer and pass through Cloudflare. Do not claim that absolutely
all data stays local while providing remote sharing.

The user suggested availability statuses such as **Available**, **Busy**,
and **Do Not Disturb**. Keep these chosen statuses separate from measured
health such as **Healthy**, **Trouble detected**, and **Last update unavailable**.
Do Not Disturb controls notification behavior; it is not an outage. A missed
heartbeat means stale/unknown with a last-seen time, not proof that Friend's LAN
is down. If Friend's observer is disconnected, an immediate remote recheck
cannot execute; report that condition honestly.

Remote authentication, invitations, owner consent, grant enforcement and
revocation, authenticated transport, heartbeat handling, and remote notification
delivery all remain future work. Notification delivery needs recipient choices,
deduplication, retry behavior, and clear delivery state before it is claimed.

## Development handoff

VS Code is the recommended general IDE for this Python/web/Docker project.
Positron is a reasonable alternative for Python/R data-science work.
The project includes VS Code settings and a local-only debugging launch.

Use `README.md` for setup, `docs/ARCHITECTURE.md` for the phase boundary, and
`docs/VALIDATION.md` for delivery checks. If older future-design text conflicts
with this memory, the current priority is local monitoring with optional Telegram phone access;
Cloudflare sharing and Twingate connectivity are earlier discussed remote options.
This memory update changes documentation only; it does not enable sharing.

## October 10 setup revision

The user requires launch-first, in-app setup and easy monitoring, including in the
prototype. Never make ordinary users edit JSON before their first launch. They may
configure immediately or choose Set up later. The current form supports the owned
local network's two devices; advanced external checks/timing and additional peer
configuration remain outside this form. Local names remain unauthenticated.

Verification of this revision: 26 automated tests passed inside the sandbox,
including six new setup tests. Two existing tests could not be completed here:
the dashboard/static-file test hangs in the sandbox threadpool and the real TCP
socket test cannot bind a socket. A full run outside the sandbox was rejected.
JavaScript/Python syntax, launcher shell syntax, and Compose configuration passed.
Browser visual checks and a rebuilt Docker runtime were not performed in this
session. Prior delivery checks above describe the earlier implementation.

## Current direction: local monitoring with optional Telegram phone access

On October 13–14, the user returned to a local use case with an optional phone
integration for status and recheck requests. The user uses an iPhone and selected
Telegram for now. Discord is being evaluated as an alternative, not selected.
Telegram phone integration is planned, not implemented or deployed. The preceding
conversation requested discussion before implementation; choosing the provider
alone does not authorize account creation, sending messages, or deployment.

The proposed integration uses outbound long polling for Telegram commands and
outbound messages for selected status summaries, confirmed incidents, and recovery.
Only explicitly paired/allowed users may read status or request scoped rechecks.
Monitoring, device configuration, and detailed history stay local by default;
authorized summaries and commands necessarily pass through Telegram. Recheck
commands need expiry, deduplication, and clear result/unavailable handling.

Cellular connectivity on the phone does not restore connectivity on a disconnected
home observer. An external heartbeat watcher was proposed for loss-of-contact
alerts; it is not selected or implemented. Missing heartbeats mean stale/unknown
with a last-seen time, not proof of a LAN outage. No fresh local result is available
while the observer cannot communicate. Phone cellular service is not guaranteed.

Discord supports an outbound Gateway bot for slash commands/button interactions;
an ordinary incoming channel webhook supports alerts but not two-way commands.
This is a possible later provider. Twingate is not required for the proposed
Telegram path; earlier Cloudflare/Twingate sharing designs remain future options.

## Current scope: local device groups and batched testing (October 17)

The user now defines the product as a local display/tester over customer-provided
network connectivity. Customers supply their own VPN/routing when testing devices
at another network/location. The app must not configure tunnels or assume that a
group establishes connectivity. Results and history stay in the dashboard/local
store. Telegram remains a selected future optional integration, not implemented;
no remote delivery or new sharing was enabled in this revision.

Implemented: add/remove named groups (Basic tests, Extended tests, IoT, locations)
and arbitrary-length device lists in Settings. Groups can contain one or more
devices; no fixed device or group count cap. Distinct hosts are required within a
group, not across independent groups. Existing peer IDs underpin groups and keep
existing configs/API paths compatible. Optional external checks start disabled in
new defaults; existing external settings are preserved. Group health without them
does not imply internet health. Group-unreachable status does not prove an outage.

Batch size defaults to 2 and can be 2, 3, 4, or 5. Each full batch completes before
the next begins; groups run in order and share the limit, including external probes.
Two devices run together, four with size 2 run as 2 then 2. The scheduler creates
only a batch of tasks at a time. Freshness/gap accounting includes the full worst-
case cycle; large lists trade sampling frequency for reduced concurrency. Dashboard
polling shows batch progress even during long manual rechecks. Hardware and cycle
duration are practical limits rather than a promise of infinite capacity.

Unchanged endpoint IDs survive renaming/reordering; changed endpoints get fresh IDs.
Removing definitions stops monitoring after save but retains stored history until
normal retention. Group-specific rechecks and dashboard filtering are available.

Verification of the October 17 revision: 42 tests passed in the complete suite,
including the former sandbox-blocked static-file and real socket tests after an
authorized outside-sandbox run. Python/JavaScript syntax checks passed. Browser
checks covered adding/saving/filtering groups, variable device lists, draft
removal/cancellation, TCP controls, console errors, and desktop/390px layouts
without horizontal overflow. UI testing used temporary files and no background
probes; no user configuration was overwritten. Customer routes and a rebuilt
Docker runtime were not retested. Restart the running app to load backend changes.

## Local network dashboard access and automatic pairing (October 17)

The user explicitly requires full dashboard access from other LAN devices for
local use/testing, including an adjacent laptop and existing customer Twingate
routes. This supersedes the earlier loopback-only launch preference. The user
also requires the access key to be applied automatically on startup.

Implemented: normal launchers bind all IPv4 interfaces with owner-key sign-in for
all browsers. Startup automatically creates/loads a persistent random key and
opens the host browser already paired. Other browsers use a generated pairing
link or key once, with 30-day HttpOnly/SameSite cookies surviving restarts. Key
reset revokes all existing signatures. Disconnect clears that browser's cookie.
This grants full installation-owner access (settings/status/rechecks); it does not
implement personal accounts, invitations, or independent friend permissions.

Native key: data/access.key, created with mode 0600 on POSIX. Docker uses
/data/access.key on the persistent volume and exposes the host port for LAN use;
its startup does not launch a browser. Pairing links use URL fragments, removed
before login; keys are not query parameters or HTTP access-log fields. Exact
private hostnames/addresses, mutation origin checks, login throttling, and an
explicit host-only mode remain supported. Local-only mode does not require a key
and rejects network clients even if Uvicorn is manually bound to all interfaces.
The new launcher disables trust in forwarded client headers.

Default LAN HTTP is not encrypted. Optional TLS certificate/key arguments are
supported. Twingate secures its tunnel, not automatically the HTTP network hop
from Connector to application. The customer still supplies routes, Twingate
Resource access, and host firewall access. No firewall/router/VPN change was made.
No actual second-device or out-of-home Twingate path is claimed verified.

Verification: 62 full-suite tests passed. A temporary server passed real HTTP
access checks via this host's LAN address: denied without a session, status/setup
available after login. Browser checks confirmed failed-key handling, automatic
pairing (including a same-page fragment change), fragment removal, dashboard
access, and disconnect; console checks were clean. Temporary isolated files and
no background probes were used. Shell/Python/JavaScript syntax and Compose config
passed. No second physical device, customer Twingate route, rebuilt Docker image,
or Windows/macOS native startup was tested. Restart the actual running app with
the updated launcher to enable LAN mode; the previous server is not replaced.

## Logo (October 17)

The user requested the existing rising-arrow tile with the exact lettering
"PaP" above the arrow, reading upward from its lower-left base toward the upper-
right tip. Keep the application name Ping_A_Friend. The user clarified this is for the browser tab only. An SVG supplies the
favicon in the existing navy/ice-blue palette; dashboard/sign-in arrow tiles
remain unchanged.
The /favicon.ico fallback redirects to that public SVG rather than returning 404.

## October 19: private presence plan and first implementation increment

The user authorized starting the new plan: both people retain the full dashboard
application, share only selected status with explicitly approved friends, and
choose whether alerts associated with a friend relationship may be sent to them.
Measured device availability is green (all reachable), yellow (some reachable),
red (none reachable), or unknown (fresh results unavailable). Chosen personal
availability remains separate. Missing remote heartbeats must not become proof of
a device/network outage. No unrestricted public visibility is authorized.

Notification providers under consideration are Twilio SMS, Telegram, Discord, and
Slack; Twilio is not mandatory. Discord incoming webhooks have the fewest steps
for an existing permitted channel; Slack needs an app/webhook authorization;
Telegram needs a bot/token and chat ID; SMS adds sender onboarding and fees.
Provider integrations are outbound alerts, not remote access or commands.

Implemented in the first increment: device-only availability summaries after group
checks; persistent availability intervals and confirmed device-event counts;
UTC monthly report cards/API; partial availability included in available time;
gaps/expired observations counted unknown; per-device failures counted once per
incident. Records survive raw-sample pruning, with 400-day summary retention.
All active incidents now remain visible, fixing the prior last-50 limit.

Optional owner notifications can be configured after launch in the dashboard for
all four providers, with selected groups, opt-in recovery/monthly summaries,
explicit test sends, credential redaction, owner-only POSIX database permissions,
a persistent background queue, cooldowns, bounded retries, and uncertain-delivery
handling. Twilio defaults to 20 API attempts per UTC day (not a dollar spending
cap). All providers start disabled. No live credentials, accounts, sends, tunnels,
firewall changes, or service deployment were performed. Existing reference README
has been preserved. See docs/NOTIFICATIONS.md for detailed setup and behavior.

Not yet implemented: shared service, personal identities, invitation acceptance,
friend grants/revocation, friend dashboard, remote heartbeat expiry/alerts,
friend-associated message consent, remote actions, and optional OS background
startup. A local development service on Owner's host is acceptable for testing;
independent hosting is needed to observe that host's own loss of contact. The
local provider implementation must not be described as completing those features.

Verification of this increment: 78 full-suite tests passed outside the sandbox,
including 16 new tests covering monthly intervals/retention, restart handling,
confirmed group transitions, incident-ID reuse after pruning, 60 active device
failures, provider payloads with fake senders, queue deduplication/retries,
uncertain delivery, monthly scheduling, SMS limits, owner authentication, and
credential redaction. Python compilation and JavaScript syntax checks passed.
An isolated browser preview verified partial availability, report cards, provider
choices, and Twilio fields; it used temporary data and fake measurements and was
stopped afterward. No live delivery, mobile layout, real second installation,
Docker rebuild, or Windows/macOS launcher test is claimed for this increment.
Restart the running application to load the backend changes. The checkout has no
usable Git repository metadata, so no commit or push was made.

## Test notifications before saving

The user found that an unsaved Discord webhook test returned HTTP 422 and requires
testing the entered connection before saving. The test button now posts the current
form values. The backend validates and sends one immediate test using those draft
credentials, even with automatic alerts disabled; blank private fields may use
saved values. It returns acceptance/failure/uncertainty directly. Testing neither
saves credentials nor enables or changes automatic notifications. Draft credentials
remain in memory only, with no automatic retry; delivery history contains no
credentials. Existing test throttling and SMS request accounting remain enforced.

Verification: 81 full-suite tests passed, including draft-before-save tests,
replacement-destination isolation, failure handling, credential non-persistence,
and rate limiting. Provider sends were mocked; no live message was sent. Python
compilation and JavaScript syntax checks passed. Restart the backend and refresh
the dashboard to load this change.

## October 26: address privacy by default

The user requires IP addresses to be privacy-screened on every start, with a
Show/Hide control and hostnames as visible identifiers. Implemented a dashboard
Show IP addresses / Hide IP addresses button; the default is always hidden and is
never saved to browser storage or configuration. Existing friendly device names
remain visible, and configured DNS hostnames remain readable; no reverse-DNS lookup
or hostname invention was added for numeric-only endpoints.

IPv4/IPv6 literals are screened on cards, measurement details, old notification
text, error messages, and report labels. Saved literal-IP fields in Settings use
password masking while hostname fields remain readable; reveal/hide preserves
unsaved form edits and original address values for configuration saves. New pages,
page restoration, and a changed backend observer-instance ID reset reveal state.
The owner API/configuration still contains actual addresses for local monitoring;
this is display privacy for screen sharing, not a new access-control boundary.

Verification: all 82 Python tests and five JavaScript privacy regression cases
passed. JavaScript tests cover IPv4/IPv6 screening, hostname preservation, old
notification text, Settings value preservation, explicit reveal, page restoration,
and backend-restart reset. Python/JavaScript syntax checks passed. No actual
configuration, provider credentials, or running user server was changed. Browser
visual verification was not repeated for this increment. Restart the app and
refresh the dashboard to load the privacy control.


The user clarified that external path addresses should remain visible. External
probe cards now bypass address screening for their labels, addresses, and details.
Monitored device cards remain private by default. The privacy hint now makes this
distinction explicit. Six JavaScript privacy cases pass, including this exception.


## October 26: monthly scroll boxes and 60-day history

The user requests six visible entries at a time for local notifications and recent
delivery attempts, with a continuous scrollbar rather than pages. Each list now
has a current-month panel and older-month selectors beside it (above on narrow
screens). Older months are collapsed until selected. At the viewer's local month
rollover, the new month opens automatically, even if empty; prior months remain
selectable within retention. Background polling preserves selected archives and
scroll anchors. The former 50-notification/30-delivery display caps are removed.

Both local histories now expire after a rolling 60 days from creation. They do
not wait for a monthly report to send successfully. Resolved incident rows are
kept while retained notifications reference them; active incidents remain tracked
even after their old notification expires. Raw-sample retention stays configurable
(default 30 days), and availability/device-event summaries stay at 400 days.
Cleanup runs at startup and during monitoring/delivery processing; API queries
exclude expired entries. Existing reference README is preserved.

The user also reports successful live Discord and Slack notification tests and
explicitly chooses to keep Telegram available for users with existing bots.
No provider messages were sent by the agent for this UI/retention change.

Verification: 85 Python tests passed, including new full-window/no-display-cap,
owner-scope, 60-day cleanup, and active-incident preservation cases. Six privacy
and four month-selection JavaScript cases passed, including local month rollover
and archive selection persistence. An isolated desktop browser preview with fake
October/September history verified exactly six fully visible entries in both
scroll boxes, archived selection, and scroll persistence across polling. No live
configuration or database was modified. Restart the app and refresh the browser
to load the new retention and history views.


## Compact history previews

The user refined the history UI: each month, including the current month, must
toggle between compact and expanded views. Local notifications now default to
the latest two entries for the selected month; recent delivery attempts default
to its latest one. Clicking the selected month expands/collapses the six-entry
scroll box; clicking a compact preview also expands. Selecting a different month
opens its history, and the selected month button can then collapse it. Polling
preserves expansion state. Page reload and month rollover start compact. The
60-day retention and all underlying incident/reporting behavior are unchanged.

Verification: 85 Python tests and 12 JavaScript cases passed. An isolated browser
preview verified initial 2/1 counts, six visible entries when expanded, month-click
collapse, and preview-click expansion. No live data/settings were altered or
messages sent. Refresh the dashboard to load this frontend-only change.


## October 26: security sweep and Linux single-file test distribution

The user authorized a security/privacy sweep and a distributable single-file build,
selecting Linux x86_64. Public defaults/docs/test examples now use generic owner
and friend identifiers; personal names and the host path were removed. Preserve
private working configuration/history rather than deleting it. The local data
directory was tightened to 0700; existing private files were already 0600.

New runtime behavior: provider settings use authenticated Fernet encryption with
a separate installation key beside the database. Existing plaintext rows migrate
on next startup, with SQLite secure-delete/vacuum/checkpoint cleanup. Missing or
wrong keys fail closed. Source installs keep their existing paths; frozen builds
use XDG per-user app data (or --data-dir), ignoring neighboring config.json files.
Source key reset does not rotate/discard the independent provider encryption key.

Owner keys and LAN addresses are no longer printed automatically. Authenticated
Settings can explicitly reveal private pairing details; --show-access-key supports
headless use. Automatic host-browser pairing uses a loopback-only, one-use token
expiring after 60 seconds. Access logs are opt-in (--access-log). Validation errors
withhold submitted values. The development-only testserver Host allowance was
removed; production Host/origin protections remain. Browser cookies are now named
per installation to avoid collisions between source and standalone test instances;
valid legacy paired cookies continue to work after upgrading.

The advisory check found issues against the old Starlette pin. Runtime pins were
updated to FastAPI 0.162.0, Starlette 1.10.0, Uvicorn 0.54.0 and their compatible
dependencies, adding cryptography 50.0.2. The updated runtime lock passed pip-audit
with no known advisories at the time checked. No telemetry exporters were added.

A PyInstaller one-file build uses a clean allowlisted temporary stage and checks
decompressed archive members against local private markers before publication.
The ZIP contains one Linux x86_64 executable, Python/runtime dependencies, static
assets, generic disabled defaults, and license notices; no private configuration,
keys, databases, test/development notes, or virtual environments. Output is under
dist/. Share only this executable/ZIP, not the working directory. The build is
unsigned and built on glibc 2.39; older/other platforms are not verified.

Verification: 98 Python tests and 12 JavaScript cases passed. The artifact privacy
audit found no private markers in 698 decompressed members, public-source marker
checks passed, ZIP membership/integrity and checksum were checked, and no owner
metadata was present in ZIP extras. An earlier candidate's CLI help ran. The user
declined the request to launch the compiled server for live smoke checks; do not
retry/circumvent that refusal or claim end-to-end runtime validation of the final
executable. A reusable isolated loopback smoke script is available for a later
authorized run. No live provider messages or automatic credential rotation were
performed. The old running source app was not restarted or its live credential
rows migrated; restart it after stopping the old process to apply the migration.

See docs/SECURITY_REVIEW.md and docs/DISTRIBUTION.md for boundaries and instructions.
Default LAN HTTP remains unencrypted; require trusted LAN or configured TLS. A
compromised OS account/root or copies of both encryption key and database can
recover credentials. Git history/remotes were not audited because this workspace
has no usable Git repository metadata. No commit/push or public deployment occurred.
