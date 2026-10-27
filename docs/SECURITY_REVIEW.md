# Security and privacy sweep — October 26, 2026

Scope: application source, defaults, documentation/test examples, private state
permissions, credential persistence, owner authentication, dependencies, and the
Linux single-file distribution. This is a focused code/privacy audit with tests,
not an independent penetration test or a guarantee against every vulnerability.

## Findings addressed

- Replaced personal names and a host filesystem path in public defaults, examples,
  and project notes with generic owner/friend examples. Existing private operator
  configuration and monitoring history were preserved.
- Generic first-launch defaults use documentation-only device addresses and keep
  every target disabled until setup. No builder device configuration is staged.
- Strengthened Git/Docker exclusions and added a release allowlist. Private data,
  keys, dotenv files, certificates, tests, notes, and virtual/build environments
  are not release inputs. The ZIP contains one executable.
- Private application directories are 0700 and keys/config/database files are
  0600 on POSIX. Existing loose key permissions are repaired. Secret/database
  symlinks are rejected instead of followed. The current local data directory's
  permissions were tightened without deleting or changing its records.
- Provider settings now use authenticated Fernet encryption with an installation
  key separate from the database. Old plaintext provider rows migrate on startup;
  secure-delete, vacuum, and WAL truncation remove ordinary SQLite remnants.
  Existing backups, snapshots, and SSD recovery are outside this migration.
- Missing/wrong credential keys fail closed. The owner signing key and provider
  encryption key remain separate; no encryption key is embedded in the binary.
- Startup no longer prints the permanent owner key, private LAN addresses, or
  pairing links by default. Private pairing details are explicitly revealed in
  the authenticated Settings UI, or through an opt-in CLI flag for headless use.
- Automatic host-browser sign-in uses a loopback-only, one-use token expiring in
  60 seconds, rather than passing the permanent owner key to a browser process.
- Request/client-address access logging is opt-in. Provider errors remain generic;
  API validation errors and invalid startup configuration no longer echo submitted
  private values. Pairing fragments are removed by the login page before exchange.
- Removed the development-only `testserver` Host allowance. Local/private Host
  validation, same-origin JSON mutation checks, HttpOnly/SameSite cookies, login
  throttling, signature/expiry checks, and forwarded-header distrust remain.
  CSP now also restricts base URLs and form destinations.
- Browser session cookie names are scoped to each installation, so testing a
  separate executable on another port does not overwrite the source instance’s
  session. Valid legacy cookies retain upgrade compatibility.
- Published advisories against the old Starlette pin were addressed by upgrading
  the FastAPI/Starlette/Uvicorn dependency chain and refreshing exact runtime pins.
  `pip-audit -r requirements.lock` found no known vulnerabilities in the updated
  runtime set at the time checked. This does not prove the application is flawless.

## Important remaining boundaries

- Restart the source application to load the fixes and migrate its saved provider
  credentials. The running old process/database was not silently migrated while
  it was using the old credential format. Do not run old/new versions against
  the same data simultaneously.
- Default LAN HTTP is unencrypted. Use it on a trusted LAN or supply trusted TLS
  certificates. No firewall/router/VPN settings were changed, and no public
  internet deployment was performed.
- Filesystem permissions and the separate key protect against other OS users and
  database-only copies. A compromised same-user account, root, or someone with
  both the database and encryption key can recover credentials. This is not an
  OS keychain, hardware-backed key, or full-disk/database encryption solution.
- Existing logs/backups outside the project were not erased. Credentials were
  not rotated automatically. If a key/webhook was exposed publicly, rotate it at
  its source; `--reset-access-key` revokes existing dashboard sessions.
- IP screening is display privacy. The owner-authenticated API and local data
  still contain addresses needed for monitoring. External path cards stay visible.
- Friend identities, grants, remote heartbeat watching, and remote commands remain
  unimplemented; LAN pairing still grants full owner access.
- The source checkout contains private working state under excluded paths.
  Share only the checked executable/ZIP, not the complete working directory.
- No live notification messages were sent by this audit. The compiled server's
  live runtime test was declined, so it remains a test build pending that check.

See DISTRIBUTION.md for supported platforms, private profile paths, and rebuild
instructions. Source-level tests cover permissions, symlink rejection, encrypted
storage/migration, missing/wrong keys, temporary unsaved credentials, validation
redaction, one-use browser tokens, owner-only pairing, and release staging.

Verification: 98 Python tests and 12 JavaScript checks passed. The final archive
privacy check inspected 698 decompressed members with no detected private
markers. The ZIP contains one executable, passed its integrity check, and its
checksum matches the release audit. No usable Git metadata was available here,
so historical commits/remotes were not audited.
