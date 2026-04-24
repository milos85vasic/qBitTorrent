#!/bin/sh
set -e

# Auto-discover Jackett API key if the config dir is mounted
JACKETT_CONFIG="/jackett-config/Jackett/ServerConfig.json"
if [ -f "$JACKETT_CONFIG" ]; then
    KEY=$(python3 -c "
import json, sys
try:
    with open('$JACKETT_CONFIG') as f:
        data = json.load(f)
    key = data.get('APIKey', '')
    if key and key.strip().lower() != 'your_api_key_here':
        print(key.strip())
except Exception:
    pass
" 2>/dev/null)
    if [ -n "$KEY" ]; then
        export JACKETT_API_KEY="$KEY"
    fi
fi

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
