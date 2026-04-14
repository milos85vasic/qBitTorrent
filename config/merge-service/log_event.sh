#!/bin/sh
# Default logging hook script for merge service events
# This script logs event data to stdout for monitoring

# Event data is passed via environment variables:
# HOOK_EVENT - Event type (search_start, search_complete, etc.)
# HOOK_DATA - JSON-encoded event data
# SEARCH_ID - Search ID (if applicable)
# DOWNLOAD_ID - Download ID (if applicable)

echo "$(date '+%Y-%m-%d %H:%M:%S') - HOOK: $HOOK_EVENT - Search: ${SEARCH_ID:-N/A} - Download: ${DOWNLOAD_ID:-N/A}"

# Echo the full event data for debugging
if [ -n "$HOOK_DATA" ]; then
    echo "$HOOK_DATA" | python3 -m json.tool 2>/dev/null || echo "$HOOK_DATA"
fi

exit 0