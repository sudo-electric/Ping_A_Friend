# Delivery validation

Validated on October 10, 2026, with Python 3.12 on Linux.

- **22 automated tests passed** in the final test run. They cover incident confirmation, recovery, deduplication, pending restart/gap behavior, retention, permission filtering, hidden peers, read-only peers, remote unavailability, status classification, stale data, busy-cycle rejection, cross-origin/host protections, safe target validation, ICMP parsing/error cleanup, owner-addressed notifications, and real localhost TCP acceptance/refusal.
- Python source compilation and JavaScript syntax checks passed.
- Docker Compose built and started the actual supplied Dockerfile/configuration. The container became healthy, published only `127.0.0.1:8000`, and wrote observations to the named SQLite volume as UID 10001. Real ICMP ping to container loopback succeeded. The final rebuilt container retained existing volume observations.
- The live dashboard loaded without browser console errors. Manual recheck updated measurements in the browser. Desktop layout and 390/320-pixel phone layouts were visually checked without horizontal overflow. Green reachability and blue latency cards rendered correctly; unavailable device placeholders stayed unconfigured.
- Both default external TCP paths responded in this test environment. This is a local observation at validation time, not a guarantee of future availability or confirmation of your home network's condition.

The test suite uses controlled time rather than sleeping 90 seconds, and verifies the exact 89/90-second boundary. A single dependency deprecation warning from Starlette's test client / AnyIO appeared; it did not affect test results.

**Not tested or implemented:** your actual two LAN devices, Windows/macOS native ping output, Docker Desktop LAN/VPN routing, remote homes, remote authentication/sharing, Twingate, and external notification delivery. Validate device reachability on the intended observer after completing dashboard setup. Native Python 3.11 support is declared; the delivery runtime and container were exercised with Python 3.12.

## In-app setup revision, October 10, 2026

- 26 tests passed in the restricted environment, including six setup tests covering
  first launch, deferral without file writes, saving/restart persistence, live
  application, changed endpoint history isolation, invalid input, failed writes,
  busy cycles, ownership/name collisions, and browser mutation protections.
- Two existing tests were excluded from the successful run: dashboard/static file
  serving hangs in this sandbox's threadpool, and real TCP checks cannot bind a
  local socket. A full test run outside the sandbox was rejected.
- Python compilation, JavaScript syntax, `sh -n start.sh`, and `docker compose config`
  passed. There is no connected browser for visual verification. A new Docker build
  and native Windows/macOS launch were not exercised.
- API tests now use an asynchronous in-process ASGI client with application lifespan
  rather than a threaded TestClient. This exercises the existing middleware without
  a network port.

The earlier 22-test/container/browser results describe the initial delivery and
should not be read as fresh validation of this revision.

## Portfolio theme revision, October 10, 2026

Matched the local Sudo Electric portfolio's navy surfaces, ice-blue/mint accents,
text colors, and monospace labels while preserving the monitoring layout. Cards
use soft lighting, with amber warnings, red failures, and muted violet unknown,
stale, or unavailable readings. Observer connection loss changes last-known card
lighting and keeps the existing explanatory banner.

JavaScript syntax and palette checks passed; 26 available tests passed. The full
suite again timed out at the existing sandbox-blocked dashboard test. The two
previously documented test restrictions and lack of browser visual verification
still apply.

## Local groups and batching revision, October 17, 2026

- **42 automated tests passed** in the final full run (Python 3.12). The full run
  was authorized outside the restricted sandbox, including the dashboard/static
  file and real localhost TCP tests previously blocked there.
- New tests verify strict batch barriers for sizes 2, 3, 4, and 5; concurrency
  shared across groups; two-device simultaneous checks; progress/gap accounting;
  cleanup of sibling probes before unlocking on storage failure; 250 devices and
  more than 100 groups without the previous caps; invalid batch/list validation;
  save/reload; reordering and changed endpoint history; scoped manual rechecks;
  group/device removal retaining stored history; and owner isolation.
- Python compilation and dashboard JavaScript syntax passed.
- In-app browser checks used a temporary database/configuration and disabled the
  background observer. Added two more devices to a group, created a second group,
  saved through the form, verified both groups on the dashboard, and filtered to
  one group. Verified draft device/group removal and cancelling changes, plus the
  TCP port control. The browser reported no console warnings or errors.
- Desktop and 390-pixel phone viewport checks showed the retained midnight theme;
  both dashboard and setup editor had no horizontal overflow. Preview values were
  synthetic hostnames; the user's installed configuration was not overwritten.
- Customer LAN/VPN reachability, Docker rebuild, and native macOS/Windows startup
  were not retested. No Telegram/Discord/n8n integration or remote delivery was
  added. The temporary preview server was stopped after checks.

## Authenticated LAN access and automatic pairing revision (October 17)

- **62 tests passed** in the complete final suite. New coverage includes private
  LAN address acceptance; unauthenticated status/setup/docs/recheck rejection;
  loopback requests also requiring sign-in in LAN mode; valid login, owner
  rechecks, disconnect-cookie clearing, HttpOnly/SameSite flags; session persistence
  across app instances; key reset invalidating sessions; expiry/tampering and
  wrong-installation rejection; throttling; same-origin/host enforcement; private
  key generation/reuse/reset; host-only access restrictions; and automatic startup
  browser pairing without manual key entry.
- An isolated Uvicorn instance bound all IPv4 interfaces on an ephemeral port.
  An actual HTTP request to this host's LAN address was denied before sign-in,
  then status/setup succeeded after authentication. Temporary key/database files
  were used, background monitoring was disabled, and the instance was stopped.
- In-app browser checks confirmed the sign-in page, incorrect-key message,
  pairing-link automatic sign-in, removal of the fragment from the address,
  protected dashboard access, disconnect, and pairing while already on the sign-in
  page. No browser console warnings/errors were recorded. UI preview used a
  separate localhost-only server and synthetic configuration, not customer data.
- Python compilation, JavaScript syntax, shell syntax, and Compose configuration
  passed. Docker startup/build and native Windows/macOS launching were not run.
- No host firewall, router, Twingate Resource, or VPN setting was changed. A real
  second laptop/iPhone and an out-of-home Twingate route were not tested. LAN HTTP
  is not encrypted; optional certificate/key launch arguments enable HTTPS.
