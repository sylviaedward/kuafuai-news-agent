#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
. .venv/bin/activate
pip install -q -r requirements.txt
exec uvicorn app.main:app --host "${APP_HOST:-127.0.0.1}" --port "${APP_PORT:-8000}"

