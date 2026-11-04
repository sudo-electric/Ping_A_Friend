# Address privacy

Reviewed November 4, 2026 against application 0.2.2.

IP addresses are hidden by default whenever the dashboard opens or reloads.
Device names and configured hostnames remain visible so devices can be identified.
External path cards (such as Cloudflare and Google DNS) always show their addresses,
regardless of the privacy toggle.
When a device uses a numeric address, give it a descriptive name in Settings;
the app does not guess its hostname or perform reverse-DNS discovery.

Use **Show IP addresses** near Settings to reveal addresses temporarily, then
**Hide IP addresses** to screen them again. The reveal choice is not saved. Page
restoration and an application restart also reset it for an already-open dashboard.

The screen covers IPv4/IPv6 addresses in cards, measurement details, legacy local
notifications, errors, and report labels. Literal-IP fields in Settings are masked;
hostname fields stay readable. Masking does not change the address being monitored
or overwrite saved or unsaved configuration values.

This is display privacy for screenshots/screen sharing. It does not remove
addresses from the owner-authenticated API, local configuration, browser address
bar, explicitly revealed pairing URLs, or system/server logs. Normal startup prints
only the localhost URL, with private LAN links/keys available by explicit request. Existing owner authentication
and sharing boundaries remain unchanged.

This includes device names/labels in monthly delayed-response summaries and logs.
It does not cover private transfer/provider input fields as a general-purpose data
redaction system. See [DATA_HANDLING.md](DATA_HANDLING.md) for stored and transmitted
information, and [SCHEMA.md](SCHEMA.md) for where records live.
