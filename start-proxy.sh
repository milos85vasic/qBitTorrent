#!/bin/sh
# Start script for download proxy

# Install packages if needed
if ! python3 -c "import requests" 2>/dev/null; then
    pip install --quiet requests urllib3
fi

# Start the proxy
exec python3 /config/qBittorrent/nova3/engines/download_proxy.py
