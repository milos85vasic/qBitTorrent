#!/usr/bin/env bash
# Operator 101: Your First Search — replayable demo.
#
# Non-interactive version of the narration in script.md. Suitable for
# `asciinema rec demo.cast --command "bash demo.sh"`. No privilege
# escalation, no stdin reads, no interactive prompts.

set -euo pipefail

say() {
    printf '\n>>> %s\n' "$*"
}

say "[00:00] Operator 101: Your First Search"
say "We replay the dashboard walkthrough end-to-end. No credentials entered by hand."

say "[00:15] Clone + enter the repo"
printf '%s\n' \
    '  git clone --depth 1 https://github.com/milos85vasic/qBitTorrent.git' \
    '  cd qBitTorrent'

say "[00:30] One-time setup (idempotent)"
printf '  ./setup.sh\n'

say "[00:45] Start containers (podman preferred, docker supported)"
printf '  ./start.sh -p\n'

say "[01:15] Open the dashboard at http://localhost:7187"
printf '  curl -s http://localhost:7187/ | head -n 5\n'

say "[01:45] Run a search: Ubuntu ISO"
printf '%s\n' \
    "  curl -s 'http://localhost:7187/api/search?q=Ubuntu%%20ISO&trackers=piratebay,eztv' | head -c 400"

say "[02:30] Browse results — seeders, quality tags, dedup across trackers"
printf '  (browser: http://localhost:7187)\n'

say "[03:00] Download via magnet"
printf '%s\n' \
    '  curl -s -X POST http://localhost:7187/api/download \' \
    "      -H 'Content-Type: application/json' \\" \
    "      -d '{\"magnet\":\"magnet:?xt=urn:btih:EXAMPLEUBUNTUISO\",\"tracker\":\"piratebay\"}'"

say "[04:00] Verify in qBittorrent WebUI proxy at http://localhost:7186"
printf '  curl -s -u admin:admin http://localhost:7186/api/v2/torrents/info | head -c 300\n'

say "[05:00] Stop cleanly"
printf '  ./stop.sh\n'

say "[05:30] Done. Continue with courses/02-plugin-author/."
