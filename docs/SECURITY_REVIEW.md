# Security and privacy review status

Reviewed November 4, 2026 against application 0.2.2. The original focused sweep
was October 26, followed by transfer/delay-history and repository security changes
on October 27. This is a source/documentation review with dated tests, not an
independent penetration test or a guarantee against every vulnerability.

## Current protections

- Public defaults/examples use generic owner/friend identifiers and disabled
  documentation-only device endpoints. Live configuration/history stays excluded.
- Git/Docker exclusions cover private configuration, databases, keys, environments,
  build outputs and encrypted `.paf` exports. Builds use an allowlisted temporary
  stage rather than copying the working folder; decompressed artifacts are checked
  for private host/data markers before publication.
- POSIX private data directories/files use 0700/0600. Private key/database symlinks
  are rejected. Source profiles keep legacy config.json/data paths; frozen builds
  use a separate private per-user profile and ignore neighboring config.json files.
- Provider settings use authenticated Fernet encryption with a key separate from
  SQLite and the owner key. Missing/wrong keys fail closed. Legacy plaintext rows
  convert on startup, with secure-delete/vacuum/WAL cleanup of ordinary remnants.
- Normal startup withholds permanent owner keys and LAN pairing links. Explicit
  owner Settings/CLI reveal exists. Automatic host pairing uses a loopback-only,
  one-use bootstrap token expiring after 60 seconds. Signed sessions expire after
  30 days, survive restarts, and use installation-specific cookie names.
- Host validation, same-origin JSON mutation checks, HttpOnly/SameSite cookies,
  HTTPS Secure-cookie flag, login throttling, security headers and forwarded-header
  distrust constrain access. API validation omits submitted secret values.
- Provider endpoint validation/HTTPS and blocked redirects limit notification
  destinations. Error responses withhold raw provider bodies and credentials.
  Draft test credentials stay in memory and do not change saved settings.
- Owner-only export/restore uses salted PBKDF2-SHA256/Fernet, bounded input sizes,
  validated table/column shapes and a fresh destination. Installation keys do not
  transfer; provider credentials are re-encrypted locally, providers start disabled
  and pending/interrupted sends are cancelled.
- Device IP display screening resets on reload/restore/backend restart and is
  explicitly distinct from API/data redaction. Delay logs add no separate device
  address column; normal records still need identifiers/configured addresses.
- Exact runtime pins, developer tests, release audits and GitHub dependency/secret/
  code scanning support ongoing review. The historical Starlette advisories were
  addressed in October. On November 4 the development pytest pin was updated to
  9.0.3 for GHSA-6w46-j5rx-g56g, and a fresh audit of runtime/development/build
  requirements reported no known vulnerabilities or skipped dependencies on this
  platform.

See [SECURITY.md](../SECURITY.md) for the public policy, private reporting and
boundaries; [REPOSITORY_SECURITY.md](REPOSITORY_SECURITY.md) records GitHub settings.

## Remaining boundaries

Default LAN HTTP is unencrypted. Use a trusted network or configure HTTPS for
credentials and private data. Twingate/VPN routing is separate infrastructure and
does not automatically protect every Connector-to-app network hop. No firewall,
router forwarding or public application hosting is configured by this project.

All paired browsers act as the configured owner, with settings/recheck/data access.
IP masking only changes display. There are no individual friend accounts, scoped
accepted invitations, independent session revocation or embedded Twingate agents.
Full Discord bots/heartbeats are proposed; current Discord support is outbound
webhooks. The public repository does not make a deployed dashboard public.

Fernet protects a database-only copy of provider settings. The matching key plus
database, or a compromised same-user/root account, can recover them. Monitoring
history and device configuration are not fully encrypted or OS-keychain protected.
A `.paf` file plus its original pairing key unlocks provider credentials/history;
resetting the live key does not re-encrypt earlier downloaded files.

Logs, snapshots, old backups, screenshots and provider copies are not erased by
SQLite cleanup. Keys/webhooks are not automatically rotated; exposed credentials
must be revoked at their issuer. Unexpected server tracebacks may include local
paths/identifiers; request access logs remain opt-in under the standard launcher.

The database's marker is still legacy `1`; there is no general schema migration
runner or future-version guard. Compatible additions and a specific credential
conversion exist. Stop the old process before updating a profile; do not run old
and new application versions against the same database. See [SCHEMA.md](SCHEMA.md).

## Evidence and limits

The November 4 security follow-up passed **106 Python tests and 15 JavaScript cases**
with pytest 9.0.3.
The 0.2.2 Linux artifact privacy check inspected **702 members** with no detected
private markers; final assets, ZIP integrity and checksum were verified. Its
compiled-server runtime test remains unperformed under the earlier declined test
boundary. The build is unsigned and targets compatible Linux x86_64/glibc 2.39.

The November 4 documentation review compared local database table/column metadata
read-only with a fresh temporary current-source database; they match. It did not
migrate live data, restart the host or send provider messages. The existing archive
was checked, not rebuilt for prose changes. The subsequent test/dependency follow-up is recorded above; no packet capture,
full-history privacy audit or penetration test is implied.

Source is version-controlled in the intentionally public GitHub repository.
Initial CodeQL findings were reviewed individually; scanner settings and dated
triage are documented separately. [VALIDATION.md](VALIDATION.md) distinguishes
source tests, package checks, user observations and unverified deployments.
