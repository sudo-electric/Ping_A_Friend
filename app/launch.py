"""Run with `python -m app.launch`; LAN access is protected by an owner key."""
import argparse
import os
import secrets
import subprocess
import sys
import threading
import time
import webbrowser

import uvicorn

from .access import key_path, load_access_key, local_addresses
from .paths import private_directory, external_environment
from . import __version__


def open_browser(url):
    if getattr(sys, 'frozen', False) and sys.platform.startswith('linux'):
        try:
            subprocess.Popen(['xdg-open', url], env=external_environment(),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            print('Browser could not open automatically. Use the local URL and --show-access-key to pair manually.', flush=True)
    else:
        webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="Start Ping_A_Friend with local-network dashboard access")
    parser.add_argument('--version', action='version', version=f'Ping_A_Friend {__version__}')
    parser.add_argument("--local-only", action="store_true", help="Only accept connections from this computer")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the host browser automatically")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reset-access-key", action="store_true", help="Generate a new owner access key; reconnect other browsers")
    parser.add_argument("--certfile", help="Optional HTTPS certificate file")
    parser.add_argument("--keyfile", help="Optional HTTPS private key file")
    parser.add_argument('--data-dir', help='Keep this installation’s private settings and data in a separate directory')
    parser.add_argument('--show-access-key', action='store_true', help='Explicitly print the private owner key and LAN pairing links')
    parser.add_argument('--access-log', action='store_true', help='Log request paths and client addresses for troubleshooting')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    if bool(args.certfile) != bool(args.keyfile):
        parser.error("Provide both --certfile and --keyfile for HTTPS")
    if args.local_only and args.reset_access_key:
        parser.error("Key reset is only needed for LAN mode")
    if args.data_dir:
        from pathlib import Path
        directory = Path(args.data_dir).expanduser().resolve()
        private_directory(directory)
        os.environ['PAF_DATA_DIR'] = str(directory)
        os.environ['PAF_CONFIG'] = str(directory / 'config.json')
        os.environ['PAF_DB'] = str(directory / 'ping_a_friend.sqlite3')
        os.environ['PAF_ACCESS_KEY_FILE'] = str(directory / 'access.key')
    os.environ["PAF_LAN_MODE"] = "0" if args.local_only else "1"
    scheme = "https" if args.certfile else "http"
    print(f"\nOn this computer: {scheme}://127.0.0.1:{args.port}", flush=True)
    pairing_url = f"{scheme}://127.0.0.1:{args.port}"
    if not args.local_only:
        key = load_access_key(reset=args.reset_access_key)
        if args.show_access_key:
            for address in local_addresses():
                print(f"Pair another device: {scheme}://{address}:{args.port}/login#key={key}", flush=True)
            print(f"Dashboard access key: {key}", flush=True)
        else:
            print('LAN access enabled. Reveal private pairing details in Settings when needed.', flush=True)
        print('Owner key loaded privately. Paired browsers stay signed in across restarts.', flush=True)
        if not args.no_browser:
            bootstrap = secrets.token_urlsafe(24)
            os.environ['PAF_BROWSER_TOKEN'] = bootstrap
            pairing_url += f'/login#key={bootstrap}'
    print("Ctrl+C stops the app.\n", flush=True)
    server = uvicorn.Server(uvicorn.Config("app.main:app", host="127.0.0.1" if args.local_only else "0.0.0.0",
                port=args.port, workers=1, proxy_headers=False,
                ssl_certfile=args.certfile, ssl_keyfile=args.keyfile,
                loop='asyncio', http='h11', ws='none', lifespan='on', access_log=args.access_log))
    if not args.no_browser:
        def open_when_ready():
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and not server.should_exit:
                if server.started:
                    open_browser(pairing_url)
                    return
                time.sleep(0.1)
        threading.Thread(target=open_when_ready, daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
