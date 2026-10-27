# Single-file Linux test build

The release ZIP contains one executable, `Ping_A_Friend-linux-x86_64`. Share that
ZIP or executable, rather than the working project folder. The executable bundles
Python, runtime dependencies, dashboard assets, safe disabled defaults, and
third-party license notices. It contains no installation keys, saved provider
credentials, personal configuration, database/history, development notes, or tests.

## Run it

Extract the ZIP, then run:

```sh
chmod +x Ping_A_Friend-linux-x86_64
./Ping_A_Friend-linux-x86_64
```

It opens the dashboard in your normal browser. Ordinary setup happens there.
No Python installation, virtual environment, repository clone, or text editing is
needed. A browser and system `ping` command are needed for the corresponding UI
and ICMP checks. TCP checks do not require the `ping` executable. The application
does not install system packages or request root privileges. Do not run it as root.

Close the terminal with Ctrl+C to stop monitoring. Closing the browser alone does
not stop the application. If your source instance already uses port 8000, stop it
first or use `./Ping_A_Friend-linux-x86_64 --port 8001` for the isolated test profile.

This is a Linux x86_64/glibc build, built on glibc 2.39. Similar or newer compatible
Linux systems are the target; older glibc systems, Alpine/musl, ARM, Windows, and
macOS are not covered by this file. PyInstaller does not cross-compile one binary
for every OS. This is an unsigned local test build, not a signed installer.

**Verification limit:** archive contents and host/privacy markers were checked,
and the source test suite passed. An earlier candidate's `--help` ran successfully.
Launching the compiled server for live smoke checks was not approved in this
session; the final rebuilt executable has not had end-to-end runtime verification.
`tools/smoke_release.py` documents an isolated loopback test for a later approved run.

## Where private state goes

By default the executable stores data under:

```text
${XDG_DATA_HOME:-~/.local/share}/Ping_A_Friend/
```

Its private directory uses mode 0700 and settings/database/key files use mode 0600
on POSIX. The executable ignores a neighboring `config.json`; it starts with safe
unconfigured defaults when its own profile has no settings. Moving or emailing
just the executable does not include the installation's private state.

Use `--data-dir /path/to/private-profile` to choose a separate test profile without
editing files. Source installs retain their existing `config.json` and `data/`
paths, and existing environment path overrides remain available. Source data is
not automatically imported into the executable's new profile.

Provider credentials are encrypted with a separate `ping_a_friend.secrets.key`
next to the database. Do not delete or share that key. Backups need the matching
key to restore credentials, but a person with both key and database can decrypt
them. Device addresses/history are protected by filesystem permissions, not full
SQLite encryption. See SECURITY_REVIEW.md for the threat boundary.

## Owner access

Default LAN access remains authenticated. The host browser pairs automatically
using a one-use, loopback-only token valid for 60 seconds. The permanent owner key
is not printed or passed to the browser helper. In Settings, expand **Pair another
browser** and explicitly reveal the private pairing details when needed.

For headless use, `--no-browser --show-access-key` deliberately prints the owner
key and LAN pairing links. Keep that output off streams and out of shared logs.
`--access-log` opts into request/client-address logging for troubleshooting.
`--local-only` retains host-only access. Trusted TLS certificate/key arguments
remain supported; default LAN HTTP is still unencrypted.

## Rebuild

In a separate build environment with `requirements-build.txt` installed:

```sh
python tools/build_release.py
```

The builder uses a clean temporary staging tree containing only allowlisted app
source, static assets, disabled generic defaults, and notices. Unknown/static
private files and symlinked release inputs fail the build. It does not copy the
project wholesale. It checks decompressed archive members against local private
markers before publishing a candidate to `dist/`.

Outputs include the single executable, a ZIP containing only that executable,
a SHA-256 checksum, and a privacy audit report. Checksums detect corruption; they
do not substitute for publisher signing. Email attachment size/type restrictions
vary, so a provider may still require a download link for the ZIP.
