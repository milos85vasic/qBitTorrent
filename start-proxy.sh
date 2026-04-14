#!/bin/sh
set -e

SRC_DIR="/config/download-proxy/src"
REQ_FILE="/config/download-proxy/requirements.txt"

if [ -f "$REQ_FILE" ]; then
    pip install --quiet -r "$REQ_FILE" 2>/dev/null
elif ! python3 -c "import requests" 2>/dev/null; then
    pip install --quiet requests urllib3 fastapi uvicorn
fi

exec python3 "$SRC_DIR/main.py"
