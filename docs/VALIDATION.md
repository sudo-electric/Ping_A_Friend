# Validation evidence

Reviewed November 4, 2026 against application 0.2.2. Dates below distinguish actual
checks from older delivery results; documentation review does not repeat or extend
runtime verification automatically.

## Current source baseline

The latest complete source test run, October 27, passed **106 Python tests** and
**15 JavaScript cases**. Coverage includes:

- ICMP parsing/permissions/timeouts and real localhost TCP success/refusal.
- Strict batch barriers for sizes 2–5, shared limits across groups, long lists,
  progress/freshness, busy rechecks, setup validation and identity/endpoint isolation.
- Failure confirmation/recovery/deduplication, restart/gap handling, owner filtering,
  authentication, cookie expiry/key reset, Host/origin checks and private-file rules.
- Availability intervals, unknown gaps, UTC month boundaries, long-term retention,
  notification queues/retries/uncertainty and provider payloads with fake senders.
- Draft-before-save tests, throttling/SMS limits, encrypted credential persistence,
  legacy plaintext conversion and missing/wrong-key rejection.
- Address masking, external-path exceptions, compact/expanded monthly history,
  rollover/scroll model, delayed-readings privacy and counts.
- Encrypted transfer round-trip, legacy payload compatibility, fresh-destination
  protection, wrong-key/tamper/incompatible-data rejection and no replay of sends.
- Delay logs retaining original names/thresholds, surviving raw pruning/restart,
  UTC/future filtering, full totals versus latest-50 preview, and older databases
  gaining tables without inventing earlier delay records.

Source compilation, JavaScript syntax and Git whitespace checks passed for that
source revision. No live provider credentials are needed by the tests.

## Build evidence

The 0.2.2 Linux x86_64/glibc 2.39 build was packaged October 27. Its privacy audit
inspected **702 decompressed members** with no private-marker findings. ZIP
membership/integrity, dashboard asset equality and executable checksum were checked.
The binary is unsigned. A prior candidate's CLI help ran; the final compiled
server was not launched by the agent because that runtime test was declined.
Do not treat package checks as an end-to-end runtime result.

## Documentation/database review — November 4

- Read-only inspection of the local SQLite table/column metadata and marker `1`
  matched a fresh temporary database initialized from the current source.
- No live history/configuration/credentials were copied into documentation and no
  live upgrade, host restart or provider send was performed.
- The schema inventory, document links, version/feature/retention claims, private
  marker exclusions and existing ZIP integrity were checked.
- GitHub security settings were read back; they are documented separately in
  [REPOSITORY_SECURITY.md](REPOSITORY_SECURITY.md).

This is a documentation-only review, not a new full test, penetration test,
dependency advisory audit or live notification/month-end delivery test.

## Earlier tests and user observations

Earlier delivery results are historical evidence, not a new test of 0.2.2. Prior
restricted-environment socket/threadpool failures were resolved for the later
authorized full runs; they are not current failing-test claims.

- October 10: the initial Docker build/startup, container loopback ICMP, persistent
  volume and desktop/mobile dashboard were exercised. The then-current Compose
  binding was loopback-only. Current Compose defaults to authenticated LAN access;
  those initial Docker checks do not validate the current container revision.
- October 17: isolated source-server LAN authentication/automatic pairing, batch
  setup and desktop/390px views were tested using temporary data. No customer
  firewall/router/Twingate changes were made.
- October 26: temporary browser previews verified monthly scrolling/compact
  notification history. Those screenshots do not validate every later UI change.
- The user reported successful real Discord/Slack test messages and confirmed that
  a Kali machine paired and displayed the original host's dashboard. This does
  not prove data migration, independent instances or out-of-home Twingate access.
- October 27: 40 direct camera TCP connection attempts outside the app all succeeded;
  three reproduced about one-second delays seen by the app. This supported a
  delay outside app timing logic, without identifying its device/network cause.

## Still unverified or unimplemented

Native Windows/macOS launching/ping output, rebuilt current Docker behavior,
customer-specific VPN/Docker Desktop routes, final compiled-server execution,
production SMS/Telegram delivery and complete real-device migration are not
claimed verified. Discord/Slack user tests do not establish delivery/read receipts.
Monthly scheduling has automated tests, not a claimed observed month-end send.

Friend identities/invitations/scoped access, full Discord bots, remote heartbeats,
remote rechecks and independent outage watching are unimplemented, rather than
untested capabilities. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Repeatable source checks

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/privacy.test.cjs tests/history.test.cjs
```

Run checks in a development environment. Tests use temporary stores and controlled
values; the real-socket case may need permission to bind localhost. Compiled runtime
checks require separate authorization under the existing recorded boundary.
