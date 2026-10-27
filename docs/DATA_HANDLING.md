# Internal data-handling reference

Reviewed October 27, 2026 against Ping_A_Friend 0.2.2 source. This describes the
current implementation, rather than a public privacy policy or a packet-capture
verification of every dependency and deployment.

## What the application collects and keeps

| Data | Purpose and storage |
| --- | --- |
| Configuration | Local display name, group/device names and IDs, configured IP addresses or hostnames, probe method/port, thresholds, timing, and local viewing/recheck rules. Saved in `config.json`. |
| Measurements | Check timestamp, reachability status, latency when available, and a short result/error description, associated with group/device IDs. Saved in SQLite. |
| Delayed-response log | Each enabled device check reported delayed: device/group IDs, device name, time, ICMP/TCP method, port, latency, and the threshold used then. No extra device address is stored in this log. |
| Incidents and summaries | Failure start/confirmation/recovery times, reasons, device incident counts, and group availability intervals/counts. Monthly reports are calculated from this history. |
| Notification records | Local alert text and recipient label; queued outbound message text, provider/group, attempts, timestamps, state, and sanitized delivery details; daily SMS API-attempt counts. |
| Provider settings | Optional webhook URLs, bot/API credentials, chat IDs or phone numbers, selected groups, and alert preferences. Encrypted in SQLite using a separate local credential key. |
| Access information | A persistent owner pairing key on the host, plus a signed browser session cookie lasting up to 30 days. Login throttling temporarily tracks client IP addresses/counters in memory, bounded to 1,024 entries. There is no persistent login audit table. |

The host also uses its hostname and local addresses for host validation and
pairing links. It does not maintain a separate hardware inventory or collect
camera video/audio, device files, browser activity, or packet captures. A TCP
check connects and closes; it does not request a web page, log in to the device,
or perform a TLS handshake merely because the selected port is 443.

## What is transmitted, and where

- **Device checks:** ICMP requests or TCP connection attempts go from the observer
  host to configured targets using existing routes/VPNs. Targets and intermediaries
  can observe network metadata such as the connection source and destination.
  Hostname targets can also cause lookups through the system DNS resolver.
- **Optional external checks:** when enabled, configured public endpoints receive
  probe traffic. Built-in examples use TCP to Cloudflare `1.1.1.1:443` and Google
  `8.8.8.8:53`; these checks do not upload the device list or database.
- **Paired browsers:** receive dashboard/configuration/history data from the host,
  including actual device addresses in API responses. Pairing gives full owner
  access. Address masking is visual only; it does not remove addresses from the
  browser's received data. Browser actions send settings, login keys, and recheck
  requests back to that host. Pairing does not synchronize two installations.
- **Optional notification providers:** explicit tests and enabled alerts send
  messages over HTTPS to Discord, Slack, Telegram, or Twilio. Normal alerts contain
  group names and reachable-device counts; monthly summaries include availability
  and incident totals, plus delayed-check counts and worst measured delay. Credentials authenticate the request; Telegram/Twilio also
  receive recipient identifiers, and Twilio receives the sending number. Local
  per-device alerts can contain device addresses in SQLite, but the current
  automatic provider messages are group summaries. User-entered names can still
  disclose personal details. Provider acceptance does not prove recipient receipt.
- **Explicit migration:** the user downloads an encrypted file containing settings,
  retained history, and provider credentials, then uploads it to the new host with
  the original pairing key. Installation key files are excluded. File plus key
  unlock the transferred contents. Restoration keeps the destination's keys,
  disables providers, and cancels queued/interrupted sends. There is no automatic
  cloud backup, remote migration fetch, or ongoing synchronization.

The application code has no configured analytics, advertising, automatic crash
upload, or developer-operated telemetry endpoint. Source launchers may contact
package registries to install/check dependencies. Twingate remains separately
configured infrastructure; there is no embedded Twingate agent or administrative
API integration in the current application. Its own data handling is outside
this source-code review, as are other services' retention policies.

## Logs and retention

Raw check samples default to **30 days** (configuration supports 1–365 days).
Local notifications and delivery history use a rolling **60 days**. Availability
intervals, device events, status events, and delayed-response records use approximately **400 days**. Delay logging starts after the upgrade; earlier raw measurements are not reconstructed. Counts represent slow checks rather than distinct outages or continuous duration.
Active incidents are retained until resolved; resolved incidents may remain while
retained notifications reference them. Current configuration, keys, provider
settings, and latest alert-state records have no scheduled expiry.

Cleanup runs while the application operates and at startup; it does not run while
the host application is stopped. Database pruning does not erase screenshots,
exports, provider copies, filesystem snapshots, or other backups.

The standard launcher disables HTTP access logging by default. `--access-log`
enables request-path/client-address/status logging. Startup and unexpected errors
still appear in terminal/server logs; traceback output can reveal file paths and
internal identifiers and should be reviewed before sharing. The app does not
manage rotation/retention of terminal, Docker, or operating-system service logs.
Normal startup withholds permanent keys and LAN addresses; `--show-access-key`
explicitly reveals them. Pairing links carry the key in a URL fragment, which is
removed by the login page before sign-in; sign-in then submits the key to the host.

## Protection boundaries

Private Linux data directories use mode 0700 and private files 0600. Device
configuration/history are not encrypted as a whole. Provider encryption protects
a database-only copy; someone with the matching credential key or access to the
running OS account can recover those credentials. Migration exports are encrypted,
but the downloaded file and its unlocking key must both be kept private.

Default dashboard HTTP is unencrypted. Login keys, cookies, settings, and data need
HTTPS or an appropriately secured network path for transport confidentiality.
A separately configured VPN does not automatically encrypt every local network hop.
Browser cookies are HttpOnly/SameSite and marked Secure when HTTPS is used.
Per-friend restricted access and individual browser-session revocation are not
implemented; resetting the owner key revokes existing paired sessions together.
