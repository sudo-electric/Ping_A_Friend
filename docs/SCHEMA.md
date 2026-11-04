# Database schema and upgrade behavior

Reviewed November 4, 2026 against application 0.2.2. The local database's table and
column metadata matches a fresh database initialized by this source. No private
records, addresses, credentials, or machine-specific paths are reproduced here.

## Three different version numbers

| Version | Current value | Meaning |
| --- | --- | --- |
| Application version | `0.2.2` | The source/build release, declared in `app/__init__.py` and `pyproject.toml`. |
| SQLite schema marker | `1` | A legacy marker inserted in `schema_version`; it does not describe every later table addition. |
| Encrypted transfer payload | `2` | The structure inside a `.paf` export. The reader also accepts payload `1` from 0.2.1. |

The export envelope still identifies itself as `Ping_A_Friend transfer v1`. That
labels the encryption/file envelope, not the application or inner payload version.

## What startup actually does

`app/store.py` creates the original tables and inserts marker `1` if absent.
`app/presence.py`, `app/delay_history.py`, and `app/notify.py` create their additional
tables/indexes with `CREATE ... IF NOT EXISTS`. Existing compatible databases gain
missing tables without losing rows. This is why the current database can have all
13 application tables while its marker still says `1`.

There is no ordered migration runner, no automatic column-renaming/conversion
system, and no startup guard that rejects an unknown future schema marker.
`IF NOT EXISTS` does not repair incompatible columns in an existing table.
Do not interpret the marker as proof that an arbitrary database is compatible.

A specific data conversion **is implemented**: the notifier encrypts legacy
plaintext provider settings on startup, using a separate local key, and performs
SQLite secure-delete/vacuum/WAL cleanup. Missing/wrong keys for already encrypted
rows fail closed. This conversion is not a general schema migration framework.

Future changes to existing columns or data meaning need explicit, tested upgrade
code before release: recognize the old layout, preserve a recoverable backup,
convert safely, verify success, and only then record the new version. Those are
release requirements, not an implemented automatic framework. Users should not
need to edit database files or run SQL manually for a normal supported upgrade.

## Storage outside SQLite

`config.json` stores display name, groups (`peers` internally), devices, addresses,
probe options, timing, and local policy grants. There are no separate `users`,
`devices`, `groups`, `friends`, or `sessions` tables. Local display names are not
personal accounts. Login throttling is in memory; session signatures are in browser
cookies. Owner and provider-encryption keys are separate files.

Source defaults: `config.json`, `data/ping_a_friend.sqlite3`, `data/access.key`, and
`data/ping_a_friend.secrets.key`. Frozen Linux builds default to
`${XDG_DATA_HOME:-~/.local/share}/Ping_A_Friend/`; Compose uses `/data/`.
Path overrides are documented in [distribution](DISTRIBUTION.md).

## Tables

All stored times are Unix timestamps in seconds; latency values are milliseconds.
`peer` and `group_id` refer to the same configured group identity. `target` and
`target_id` refer to configured endpoint identities. These identifiers generally
are not SQL foreign keys because definitions live in JSON and history survives
removal of a definition.

| Table | Purpose | Retention / behavior |
| --- | --- | --- |
| `schema_version` | Legacy database marker. | Marker `1`; no ordered migration ledger. |
| `samples` | Timestamped status, latency and explanation for each check. | Configurable 1–365 days; default 30. `result` is JSON text. |
| `incidents` | Pending/confirmed failures and resolution times per target. | Active rows remain; resolved rows expire after sample retention unless retained notifications still reference them. |
| `notifications` | Local owner alert text linked to one incident. | Rolling 60 days; expiry does not resolve an active incident. |
| `availability` | Group availability intervals and reachable/total counts. | Approximately 400 days; contiguous equivalent observations merge. |
| `device_events` | Confirmed per-device incident events for reporting. | Approximately 400 days; independent of raw samples. |
| `status_events` | Confirmed group transitions and notification message text. | Approximately 400 days. |
| `alert_state` | Latest group transition baseline. | No scheduled expiry; not a historical event list. |
| `destinations` | Provider, encrypted settings, and settings-change baseline. | Retained until changed; disabled providers retain credentials. |
| `deliveries` | Notification queue and attempt outcomes. | Rolling 60 days; in-flight rows are preserved during cleanup and become uncertain after an interrupted restart. |
| `sms_usage` | API-attempt totals by UTC day. | Pruned with the notification-history window, on day boundaries. |
| `delay_events` | Each delayed enabled-device reading, with original name/method/port/threshold. | Approximately 400 days; no pre-upgrade backfill; external checks excluded. |
| `delay_log_info` | First enabled-device check recorded by delay logging. | Single row with `id=1`; persistent coverage marker. |

Retention cleanup runs at startup and while the app operates. It does not run
while stopped, erase external backups, or shrink a downloaded export. SQL row
retention and dashboard preview limits are different: reports preview the latest
50 delay readings, and incident cards include all active plus the latest 50
resolved incidents. Monthly totals use their separate retained event tables.

## Columns

The following inventory is checked against the initialized schema. PK marks the
primary-key columns; SQL nullability/defaults/constraints are defined by the linked
source modules rather than inferred from this compact list.

### `alert_state`

`group_id` TEXT (PK), `state` TEXT.

### `availability`

`id` INTEGER (PK), `group_id` TEXT, `start` REAL, `end` REAL, `expires` REAL, `state` TEXT, `reachable` INTEGER, `total` INTEGER.

### `delay_events`

`id` INTEGER (PK), `group_id` TEXT, `target_id` TEXT, `name` TEXT, `method` TEXT, `port` INTEGER, `checked_at` REAL, `latency_ms` REAL, `threshold_ms` REAL.

### `delay_log_info`

`id` INTEGER (PK), `started` REAL.

### `deliveries`

`id` INTEGER (PK), `provider` TEXT, `event_key` TEXT, `group_id` TEXT, `message` TEXT, `created` REAL, `state` TEXT, `attempts` INTEGER, `next_attempt` REAL, `detail` TEXT.

### `destinations`

`provider` TEXT (PK), `config` TEXT, `since` REAL.

### `device_events`

`incident_id` INTEGER, `group_id` TEXT (PK), `target_id` TEXT (PK), `name` TEXT, `confirmed` REAL, `started` REAL (PK).

### `incidents`

`id` INTEGER (PK), `peer` TEXT, `target` TEXT, `started_at` REAL, `last_failure` REAL, `confirmed_at` REAL, `resolved_at` REAL, `reason` TEXT.

### `notifications`

`id` INTEGER (PK), `incident` INTEGER, `peer` TEXT, `recipient` TEXT, `created_at` REAL, `message` TEXT, `delivery` TEXT.

### `samples`

`id` INTEGER (PK), `peer` TEXT, `target` TEXT, `checked_at` REAL, `result` TEXT.

### `schema_version`

`version` INTEGER (PK).

### `sms_usage`

`day` INTEGER (PK), `attempts` INTEGER.

### `status_events`

`id` INTEGER (PK), `group_id` TEXT, `state` TEXT, `created` REAL, `message` TEXT.

## Constraints and ownership

- `incidents` has a partial unique index on `(peer,target)` while unresolved.
- `notifications.incident` is unique and references `incidents.id`; foreign-key
  enforcement is enabled, so cleanup preserves referenced resolved incidents.
- `device_events` uses `(group_id,target_id,started)` as its composite primary key.
  Its `incident_id` is a historical reference, not an SQL foreign key.
- `destinations.provider` and `alert_state.group_id` are primary keys;
  `deliveries` has a unique `(provider,event_key)` constraint to deduplicate queuing.
- `delay_log_info` restricts its primary key to `1`. `status_events` and
  `delay_events` use SQLite AUTOINCREMENT; SQLite maintains `sqlite_sequence` as an
  internal bookkeeping table, not a separate application feature.
- SQLite uses WAL journaling, foreign-key checks and secure-delete. One application
  process/worker must own monitoring for a given profile. Provider settings use
  Fernet; the whole database and device configuration are not encrypted.

Source: [Store](../app/store.py), [availability/reporting](../app/presence.py),
[delay history](../app/delay_history.py), [notifier](../app/notify.py), and
[transfer format](../app/migration.py). See [data handling](DATA_HANDLING.md) for
network traffic and protection boundaries.
