#!/bin/sh
set -eu
cd "$(dirname "$0")"
if command -v uv >/dev/null 2>&1; then
    if [ ! -x .venv/bin/python ]; then uv venv .venv; fi
    uv pip install --python .venv/bin/python -r requirements.lock
else
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.lock
fi
exec .venv/bin/python -m app.launch "$@"
