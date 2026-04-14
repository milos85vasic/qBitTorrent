#!/bin/sh
set -e

SRC_DIR="/config/download-proxy/src"
REQ_FILE="/config/download-proxy/requirements.txt"

if [ -f "$REQ_FILE" ]; then
    pip install --quiet --no-cache-dir -r "$REQ_FILE" 2>/dev/null || \
        pip install --quiet -r "$REQ_FILE" 2>/dev/null
else
    for pkg in requests urllib3 fastapi uvicorn aiohttp pydantic Levenshtein; do
        python3 -c "import $pkg" 2>/dev/null || pip install --quiet "$pkg" 2>/dev/null
    done
fi

exec python3 "$SRC_DIR/main.py"
