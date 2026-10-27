# Notifications and availability reports

This increment adds owner notifications and monthly reporting to the local app.
It does not yet connect installations, create friend accounts, or provide an
independent heartbeat watcher. Closing the browser does not stop the running
server; stopping the server stops checks and notification delivery.

## Setup in the dashboard

Restart with the normal launcher, then expand **Notifications & integrations**.
Each provider is independent and disabled by default. Choose a provider and enter
its credentials and destination. Use **Send test notification** to verify those
entered values before saving or enabling alerts. Testing sends one real message
and reports provider acceptance/failure immediately; unsaved credentials stay in
memory only, with no automatic retries. Blank private fields use previously saved
values. Testing never saves settings or enables alerts. Tests are limited to one
per provider per minute and still count toward the SMS request limit.

Once satisfied, select groups, enable the provider, and save to start automatic
alerts. Leave all groups unchecked to include every owned local group, including
future groups. Recent delivery attempts show test and automatic delivery results.

Secrets and recipient fields are write-only: leaving them blank preserves saved
values. To replace a value, enter its replacement. Disabling a provider retains
its credentials and cancels pending messages. Changing settings also cancels
pending messages so they cannot be redirected to a new recipient.

Use the host browser or HTTPS when entering secrets. The existing default LAN
HTTP mode does not encrypt browser traffic. The SQLite file is restricted to
owner read/write on POSIX. Provider settings are encrypted with a separate
installation key (`ping_a_friend.secrets.key` beside the database); existing
plaintext provider settings migrate on the next startup. Device configuration
and monitoring history remain local plaintext protected by filesystem permissions.
Keep the key and database private: a copy of both, or a compromised OS account,
can unlock provider credentials. Paired browsers still have full owner access.

## Scrollable monthly history

Local notifications start with the latest **two** entries; recent delivery attempts
start with the latest **one**. Click the selected month to expand or collapse its
history. Clicking a compact preview also expands it. Expanded lists show a
six-entry scroll box. All retained entries for the selected month are available by continuous scrolling;
there are no page controls or fixed 50/30-entry display limits. Wrapped messages
remain readable, and the box height follows the first six entries as its width
changes. Background refreshes preserve the selected month and scroll position.

The current calendar month is selected with a compact preview by default. Earlier months are collapsed into
selectors alongside the list (above it on narrow screens). When November begins,
November becomes the selected month with a compact preview and October remains selectable. This happens at
the viewer's local month boundary, matching the dates displayed in these lists;
the separate monthly availability reports still use UTC.

Both histories now use a **rolling 60-day retention window**, based on the entry's
creation time. A partly expired month contains only its retained entries. Sending
a monthly report does not clear either list. Cleanup happens at startup and while
the application runs, and API reads exclude expired entries. Cleanup affects local
records; messages already posted to providers remain subject to their own history.

Old notification entries expire even if their incident is still active. The active
incident itself remains tracked; removing its old notification does not resolve it.
Resolved incident rows remain while retained notifications reference them. Raw
samples retain their existing configurable retention, and availability summaries
and device-event counts retain their separate 400-day retention.

## Provider choices

| Provider | Setup | Intended use |
| --- | --- | --- |
| Discord | With channel permission, create a webhook under Edit Channel → Integrations → Webhooks; paste the URL. | Simplest existing-channel option for a home lab or small team. |
| Slack | Create a Slack app, enable Incoming Webhooks, and authorize a channel; paste its URL. Workspace approval may be necessary. | Existing workspaces; commercial distribution would need a proper installation/OAuth flow. |
| Telegram | Create a bot with @BotFather, start a conversation with it, and supply its token and your numeric chat ID. The Bot API getUpdates response can identify the chat after an initial message, provided no other consumer/webhook is handling updates. | Personal phone alerts without joining a workspace/server. |
| Twilio SMS | Supply account SID, auth token, SMS-capable sending number, and recipient number, including country codes. | Recipients who want ordinary text messages without another app. |

Official setup references:

- Discord: https://docs.discord.com/developers/resources/webhook
- Slack: https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/
- Telegram: https://core.telegram.org/bots/tutorial and https://core.telegram.org/bots/api#getupdates
- Twilio: https://www.twilio.com/docs/messaging/api/message-resource
- Twilio trial: https://www.twilio.com/docs/usage/tutorials/how-to-use-your-free-trial-account
- US sender registration: https://www.twilio.com/docs/messaging/compliance/a2p-10dlc

These are outbound alerts. Telegram commands, Discord interactions, Slack slash
commands, OAuth installation, and friend-triggered actions are not implemented.
Discord mentions are disabled. No account, webhook, bot, or phone number is
created automatically. No provider credentials or live destinations were supplied
or used during implementation tests.

## Alert behavior

Device availability is separate from latency and optional external-path checks:

- Green: all enabled devices reachable, including delayed responses.
- Yellow: at least one reachable and at least one unreachable.
- Red: all enabled devices unreachable from this observer.
- Unknown: no enabled devices, or any required device result is unavailable/stale.

Dashboard availability reflects observations; external alerts wait for confirmed
device failures using the existing confirmation window (normally 90 seconds).
Unknown measurements do not confirm failure or manufacture a recovery. A confirmed
group transition produces one event. If several transitions happen before queue
collection, only the latest is considered. Repeated collection/restarts do not
create duplicate deliveries for that event. A five-minute cooldown applies per
status, group, and provider, allowing yellow-to-red escalation. Suppressed events
remain recorded locally. Green notifications require recovery opt-in.

Delivery uses a separate worker with at most four queued requests per pass and a
10-second timeout per request. HTTP 429/5xx failures get at most three attempts,
with increasing delays. Connection timeouts are uncertain and are not retried:
the provider may already have accepted the message. Interrupted in-flight requests
are also marked uncertain on restart. Non-monthly queued messages expire after
15 minutes. This is best-effort delivery, not an exactly-once guarantee.

**Accepted** means the provider accepted the request, not that a person read or
received it. Twilio delivery callbacks are not implemented. Twilio defaults to
20 API attempts per UTC day, including tests/retries, adjustable in the form.
This is not a dollar cap: message segmentation, number charges, carrier fees,
and other account usage may affect the bill. Configure account spending controls
with the provider as appropriate. Only notify recipients who consented.

A local app cannot send when its host/internet connection fails. Provider outages
also do not change measured device health. Independent loss-of-contact alerts
belong to the future shared service.

## Monthly reporting

The dashboard has a UTC month selector, elapsed availability totals, and confirmed
incident counts per device. Optional monthly messages summarize the previous UTC
calendar month once per group/provider. On startup, a missed prior-month summary
can be queued when that month has recorded coverage; earlier missed months are
not automatically backfilled.

Available time = green time + yellow time. Partial time remains separately visible.
Red time is zero reachable devices; unknown includes expired samples, observer
gaps, and time before monitoring started. Future time is excluded. Decimal days
are elapsed seconds divided by 86,400, not days with at least one successful ping.
This is sampled availability, not proof of uninterrupted connectivity between
checks. Device percentages use the configured enabled-device count at that time.

A continuing confirmed device incident counts once, including across midnight or
application restarts. New failures after recovery count again. Changing an endpoint
creates a new target ID, preserving separation from old measurements. Historical
device labels may differ from current names.

Availability intervals and confirmed device-event records survive the configurable
raw-sample retention (30 days by default). They are retained for approximately
400 days and are merged when consecutive observations have identical availability
and device counts. No historical uptime is invented for the period before this
version began collecting summaries. No graph or automatic OS startup service has
been added in this increment.

## Next implementation boundary

Both people will keep the full application. A separate service still needs:

1. Authenticated user/installation identities, enrollment and credential rotation.
2. Expiring invitations, explicit selected-group grants, acceptance and revocation.
3. Outbound authenticated summary/heartbeat synchronization with sequence numbers
   and expiry, plus honest stale/unknown status when contact is lost.
4. A Friends dashboard and notification consent associated with each relationship.
5. Service-side provider delivery and quotas so alerts work when the reporting
   installation is offline; the local owner key must never become a friend token.
6. Cross-instance tests, deployment/TLS, backups, and opt-in background startup.

These are remaining implementation steps, not deployed or enabled capabilities.
The user has authorized development; actual provider account setup, credential
entry, message destinations, and service deployment still need concrete choices.
