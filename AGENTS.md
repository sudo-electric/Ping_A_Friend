# Ping_A_Friend project guidance

Reviewed November 4, 2026. Read [PROJECT_MEMORY.md](PROJECT_MEMORY.md) before product
or architecture changes. It records current requirements and separates working
features from proposals. Update it when a decision or verified implementation changes.

- Use **Ping_A_Friend**. Earlier names are historical only. The repository is
  intentionally public; the running installation remains private owner access.
- Ordinary setup happens after launch in the dashboard, with Set up later and
  Settings. No pre-launch text editing. Pairing/connection/transfer controls must
  remain available before monitoring setup. Do not add editor recommendations.
- Current scope: local ICMP/TCP tester/dashboard, unlimited-length groups/devices,
  strict sequential batches of 2–5 (default 2), manual rechecks and sustained-failure
  incidents. Customer routes/VPNs supply connectivity. Groups do not create routes.
- Keep the busy-check 409 protection. A delayed response is reachable and must
  not confirm an outage. Unknown/stale observations do not prove network failure.
- Keep the existing navy/ice-blue/mint layout with illuminated cards and status
  labels. Device IPs start hidden on reload/restore/backend restart. Reveal is
  temporary, never stored. Hostnames stay visible; external-path cards are exempt.
  Preserve actual settings values. Display screening is not API authorization.
- Optional Discord/Slack webhooks, Telegram sendMessage and Twilio SMS notifications
  work today. Tests can use unsaved drafts without saving/enabling. All providers
  default disabled. Preserve credential redaction, queue dedup/cooldowns/retry
  limits, uncertain-delivery semantics and SMS attempt caps. Do not send live
  messages without explicit user authorization.
- Monthly reports use UTC calendar months and the host clock, not a calendar
  service. Optional provider summaries select the previous month once per group/
  provider with coverage. Keep available time (green+yellow) separate from delays.
- Retain raw samples per configured days (default 30), notification/delivery history
  60 days, and availability/device/status/delay events 400 days. Expiring a notice
  must not resolve its active incident. Month history starts compact (two notices,
  one delivery) and expands into a six-entry scrolling box; no fixed display cap.
- Log every delayed enabled-device check with name/ID, time, method/port, latency
  and its original threshold. Exclude external/disabled checks; no invented old
  readings. Monthly totals are uncapped by the latest-50 preview. Keep logs in
  current transfer payload 2 and retain legacy payload 1 read compatibility.
- Normal native/Compose startup uses authenticated LAN access and persistent owner
  keys; --local-only remains available. All paired browsers act as the owner, not
  separate friends. Preserve same-origin/Host rules, local bootstrap expiry, scoped
  cookies and explicit secret reveal. No firewall/router/VPN changes by default.
- A browser connection opens the original host; an encrypted transfer explicitly
  copies data to a fresh host. Keep destination keys, disable restored providers
  and cancel queued/interrupted sends. Do not overwrite configured installations.
- [docs/SCHEMA.md](docs/SCHEMA.md) describes current tables. The database marker
  remains legacy 1; it is not a complete migration ledger. Compatible tables are
  created at startup and provider plaintext conversion exists. Future incompatible
  changes need tested upgrade code; do not claim an ordered framework exists.
- Each installation owns its settings/devices/history. Future friend sharing must
  be explicitly accepted, scoped, revocable and non-transitive. Local display names
  and LAN owner keys are not personal accounts. Never use an owner key as a friend
  token. Chosen presence remains distinct from measured device availability.
- The latest proposed direction is Discord bots between instances. Only a preview
  was requested; bot commands, invitations, friend consent, remote heartbeats and
  rechecks remain unimplemented. Twingate is customer infrastructure. Cloudflare,
  Telegram command, ntfy and n8n ideas are earlier unimplemented options.

Use one Uvicorn worker/profile. For code changes run `python -m pytest -q` with
requirements-dev.txt installed, plus relevant JavaScript cases. For documentation
changes verify links, factual/schema claims and the existing downloadable archive;
no new implementation tests or rebuild are required solely for prose.

Preserve live private data. Exclude config.json, data/, keys, dotenv, certificates,
.paf exports, environments and builds from Git. Use the release allowlist and
private-marker audit; never stage whole working folders. Provider keys remain
separate from the database and missing/wrong keys fail closed. Source and frozen
profiles keep their documented paths. Normal startup withholds private keys/links.
Commit/push completed verified work to the existing public repository.

The compiled-server runtime test was declined earlier. Do not repeat it without
fresh authorization or claim the final binary was run end-to-end. Source tests,
archive privacy/integrity checks and user-reported pairing are separate evidence.
