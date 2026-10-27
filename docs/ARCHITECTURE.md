# Architecture and phase boundary

## Phase 1: working local observer

```text
Browser on this computer
  ├── GET status (local identity, filtered direct grants)
  └── POST manual recheck (direct recheck permission)
        ↓
FastAPI / single process and worker
  └── Monitor (serial groups/cycles, strict batches of 2–5 probes)
        ├── LocalTransport → ICMP or TCP → configured LAN devices / external paths
        ├── UnavailableRemoteTransport → explicit unavailable, no network action
        └── SQLite → samples / incidents / local-dashboard notifications
```

Configuration loads on startup; the trusted local operator can configure their owned local network through GET/POST /api/setup. The form accepts any number of named groups and devices, validates distinct addresses within each group and probe settings, saves configuration atomically, and applies it while holding the monitor lock. Changes to device endpoints create new target IDs to avoid reusing old measurements. The existing peer IDs represent groups internally and remain stable for existing installations. Setup cannot edit another owner’s devices or switch to an existing configured identity. Native settings are stored in config.json; Compose uses /data/config.json on its persistent volume. The first launch offers setup or deferral. All peers have an owner and independent direct grants. The selected local identity is configuration, not a credential. A hidden peer is omitted from API responses and manual action returns 404. The observer may still measure that peer if it is configured as local.

Every probe's result belongs to `(peer_id, target_id)` and records its check timestamp, status, measured latency, and explanation. ICMP is OS-provided; TCP is connection establishment only. Errors running a probe are unknown rather than proof of failure. Probe processes are killed/reaped on timeout or cancellation. Disabled devices remain unconfigured. Transport implementations must return a `Result` within the configured timeout and distinguish failure from measurement unavailability. The monitor enforces an additional outer time budget.

Incidents are persisted per target. A partial unique SQLite index allows only one open incident per peer/target. Confirmation and its single notification are written in the same database transaction. Results must continue to be failures across the confirmation window, with no excessive gap or unknown reading. Process restart resolves pending incidents rather than counting downtime. Recovery resolves confirmed incidents but keeps history. Notifications are owner-addressed local records; no transport delivery is claimed.

The observer catches cycle errors and retries. API snapshots mark old readings stale. Monitoring and manual cycles use one asynchronous lock; a busy manual request gets 409. One process must own the database observer. Schema version 1 is recorded; there is no migration framework yet. Future schema changes require an explicit migration before releasing an upgrade.

## Phase 2: remote agents and consent (planned)

Each installation should retain its own local user/database and locally measured devices. Export the minimum authorized summary instead of granting broad access to another LAN or sharing every user's history. Pairing must be explicit, with an owner-approved recipient, scope, expiry if desired, revocation, and audit history. Owner and Friend share only their own chosen peers. Friend adding his parents is an independent relationship and creates no grant to Owner.

Possible adapters:

- An outbound authenticated agent/reporting channel to a privately accessible broker.
- A private routed channel using Twingate, with application authentication and scoped permissions above that channel.

These are design options, not working integrations. The current `Transport` protocol is an extension point. A remote adapter would need to retrieve authenticated, timestamped, replay-resistant remote observations and distinguish observer heartbeat failure from device failure. Authentication cannot come from the editable local username or an arbitrary peer ID. Notification delivery needs a durable outbox, recipient verification, retry/backoff, and idempotence separately from the current local notification records.

## Local boundary

The standard launcher binds 0.0.0.0 with owner-key authentication required for
all clients, including the host. It generates/loads a persistent random key and
opens the host browser with an automatic pairing link. Other browsers pair once.
Signed, HttpOnly, SameSite=Strict cookies last 30 days across restarts; resetting
the key invalidates them. Disconnect clears the current browser cookie. This is
shared full owner access, not individual authenticated users or scoped grants.
Keys live in a separate data/access.key file, not device configuration. POSIX
creation uses mode 0600. Compose persists the key in its data volume.

Only the sign-in page/API, static assets and minimal health status are public.
All monitoring/configuration/recheck APIs require a valid session in LAN mode.
Login attempts are throttled. Private IP literals, local computer hostnames and
explicit PAF_ALLOWED_HOSTS aliases are allowed, without wildcard DNS acceptance.
Same-origin JSON mutation requirements and CSP remain in place. Forwarded client
headers are not trusted by the launcher. HTTP remains unencrypted unless TLS is
configured with a certificate/key. A VPN does not encrypt the Connector-to-app
HTTP hop automatically; use a trusted LAN or TLS for that segment.

The --local-only launcher binds loopback without sign-in and rejects non-loopback
clients at the application layer. Direct Uvicorn startup defaults to this mode.
The local SQLite store contains target addresses/history; exclude it and access
keys/configuration from version control and keep backups private.

No NAT traversal, peer handshake, inbound port forwarding, VPN setup, remote consent, or cloud deployment is performed. Container routing can differ from host routing; test from the actual intended observer.

## Local groups and bounded batch scheduling (October 17)

There is no fixed configuration cap on groups or targets. A group has at least one
device and optional external checks; the previous two-device setup shape is still
accepted. The dashboard can add/remove groups and devices, filter by group, select
batch sizes 2–5 (default 2), and recheck one group. Existing configs default to two
checks at once without a migration. Group IDs and unchanged endpoint target IDs
survive saves and reordering. Stored history remains after removing definitions.

One monitor lock covers all groups and manual cycles. For each group, only one
batch of tasks is created, and all its probes finish before the next batch starts.
Groups run sequentially. External checks use the same batch budget. The worst-case
freshness/gap window includes the sum of each group's batch count. Browser polling
continues during long manual rechecks to show progress, without a fixed 45-second
request cutoff for that action. Memory, disk and duration are practical limits.

All probes use this observer's routes. The customer supplies any VPN, inter-site
routing, DNS, and firewall rules. No tunnel or sharing service is introduced.
Device results and incidents remain on the local dashboard/SQLite. Telegram,
Discord, n8n, Twingate and Cloudflare integrations are still unimplemented options.


## Security and distribution revision

See SECURITY_REVIEW.md and DISTRIBUTION.md for the current security/distribution
boundary. Private state is excluded from release staging. Frozen applications use
a per-user data directory, while source installs retain their current paths.
Saved provider settings are authenticated-encrypted with a separate installation
key. Owner keys and pairing links are shown only on explicit request; automatic
host-browser pairing uses a one-use token valid for 60 seconds on loopback.
Request access logging is opt-in. Local provider delivery is implemented separately
from the still-unimplemented friend/agent transport described above.
