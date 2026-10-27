# Security

Ping_A_Friend is a local monitoring application in active development. Security
fixes target the current `main` branch; update older source installs and compiled
builds before relying on the protections described here. This is not a claim of
an independent penetration test or certification.

## Report a vulnerability privately

Use [GitHub's private vulnerability reporting form](https://github.com/sudo-electric/Ping_A_Friend/security/advisories/new).
Include the version, affected component, reproduction steps, and expected impact.
Use sample addresses and fake credentials. Do not post live pairing keys, provider
tokens, private device details, databases, or unlocked transfer files in issues.
If private reporting is unavailable, contact the repository owner through an
already established private channel before sharing sensitive details.

## Implemented application protections

- **Owner authentication:** normal LAN startup creates a random persistent key.
  Signed browser sessions expire after 30 days; cookies are HttpOnly/SameSite and
  Secure over HTTPS. Login attempts are throttled. Resetting the owner key revokes
  existing sessions. Cookies are scoped by installation to avoid collisions.
- **Automatic local pairing:** host-browser bootstrap tokens are loopback-only,
  single-use, and expire after 60 seconds. Permanent keys and private links are
  hidden during normal startup and revealed only through explicit owner actions.
- **Request boundaries:** owner authentication protects dashboard APIs, settings,
  reports, rechecks, provider tests, and transfers. Host validation, same-origin
  JSON mutation checks, and forwarded-header distrust limit unintended access.
  Dashboard content-security, no-referrer, no-store, and no-sniff headers are set.
- **Private storage:** on POSIX, private directories use 0700 and private files
  0600; key/database symlinks are rejected. Provider credentials are encrypted with
  authenticated Fernet encryption and a separate local key. Missing/wrong keys
  fail closed. Legacy plaintext provider settings migrate on startup.
- **Notification handling:** saved secrets are not returned by the settings API.
  Unsaved test credentials stay in memory. Provider destinations are validated,
  HTTPS is required, redirects are blocked, and errors withhold provider response
  contents. Retries, cooldowns, and SMS request limits constrain delivery attempts.
- **Input and probe handling:** settings validate bare addresses/hostnames and
  ports. Ping is launched with argument lists rather than shell interpolation.
  Checks have timeouts and run in bounded batches. Validation errors omit submitted
  private input values; monitoring failures do not establish a proven LAN outage.
- **Display privacy:** device IP literals start hidden on reload/restart and remain
  hidden until explicitly revealed. Hostnames remain readable; public external
  path cards are exempt. Names and text are escaped when rendered in the dashboard.
- **Encrypted transfers:** exports use PBKDF2-SHA256 with a random salt and 600,000
  iterations, then Fernet encryption. Restores require a file, its original key,
  confirmation, and a fresh destination. Data is validated against the local
  schema; imported files supply no SQL or executable code. Transfer requests are
  size-bounded. New installation keys remain local; providers start disabled and
  pending/interrupted messages are cancelled to prevent replay.
- **Distribution controls:** Git/Docker exclusions and an explicit build allowlist
  keep private settings, keys, history, and development environments out of release
  files. Decompressed build contents are checked for host/private markers before
  publication. Release checksums detect corruption; builds are currently unsigned.

## Important limits

- Default LAN HTTP is unencrypted. Use a trusted network or configured HTTPS;
  entering credentials over plain HTTP exposes them to observers on that path.
  Twingate/VPN routing is separately configured and does not automatically secure
  every local hop. There is no embedded Twingate integration today.
- Pairing grants full installation-owner access, including access to device
  addresses in API responses. Screen masking is not redaction or authorization.
  Per-friend grants, individual session revocation, and account roles are not
  implemented. Do not give an owner pairing key to a read-only visitor.
- Configuration and monitoring history are not fully encrypted. Provider encryption
  protects a database-only copy, not someone controlling the OS account/root or
  holding both the database and its credential key.
- A transfer file plus its original pairing key unlocks its contents, including
  provider credentials. Resetting the live owner key does not change old exports.
- Cleanup does not erase exported files, screenshots, provider copies, filesystem
  snapshots, or backups. Terminal/system logs can expose paths or identifiers.
- GitHub scanners and dependency alerts can miss vulnerabilities. A historical
  clean dependency audit is not a guarantee about the current dependency set.
  Compiled builds remain test builds; final compiled-server execution has not
  been verified by the agent in this session.

## More detail

- [Data collected, stored, transmitted, and retained](docs/DATA_HANDLING.md)
- [Security review and verification boundaries](docs/SECURITY_REVIEW.md)
- [Notification credentials and delivery behavior](docs/NOTIFICATIONS.md)
- [Distribution, private profiles, and migration](docs/DISTRIBUTION.md)

Repository-level security settings are managed on GitHub and recorded in
[the repository security configuration notes](docs/REPOSITORY_SECURITY.md).
