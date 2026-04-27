#!/usr/bin/env bash
# CONST-032 regression guard: clean-slate Jackett autoconfig flow.
#
# 1. Tear down stack
# 2. Wipe ./config/jackett
# 3. Boot stack
# 4. Wait for /health (3 min ceiling)
# 5. Poll /api/v1/jackett/autoconfig/last until populated or 60s
# 6. Validate response shape
# 7. Run a search; assert no 5xx
#
# Exit:
#   0 = pass
#   1 = fail
set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

RUNTIME="${CONTAINER_RUNTIME:-podman}"
if ! command -v "$RUNTIME" >/dev/null 2>&1; then
  RUNTIME="docker"
fi
MERGE="${MERGE_SERVICE_URL:-http://localhost:7187}"

step() { echo ">>> $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

step "1. Tear down"
"$RUNTIME" compose down --remove-orphans >/dev/null 2>&1 || true

step "2. Wipe ./config/jackett"
# Jackett-LSIO writes some files as root; podman unshare maps host
# uid 0 ↔ container root inside the user namespace so we can delete.
if ! rm -rf ./config/jackett 2>/dev/null; then
  if command -v podman >/dev/null 2>&1; then
    podman unshare rm -rf ./config/jackett || fail "could not wipe ./config/jackett"
  else
    sudo rm -rf ./config/jackett || fail "could not wipe ./config/jackett (need sudo or podman)"
  fi
fi
[ ! -e ./config/jackett ] || fail "./config/jackett still exists after wipe"

step "3. Boot stack"
"$RUNTIME" compose up -d >/dev/null

step "4. Wait for /health (3 min)"
deadline=$(( $(date +%s) + 180 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  if curl -sf "$MERGE/health" >/dev/null 2>&1; then
    echo "    healthy"
    break
  fi
  sleep 5
done
curl -sf "$MERGE/health" >/dev/null 2>&1 || fail "merge service unhealthy after 3 min"

step "5. Poll /api/v1/jackett/autoconfig/last (60s)"
deadline=$(( $(date +%s) + 60 ))
status=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  http=$(curl -s -o /tmp/autoconfig.json -w '%{http_code}' "$MERGE/api/v1/jackett/autoconfig/last" || true)
  case "$http" in
    200) status=200; break ;;
    404) status=404; break ;;
  esac
  sleep 2
done

step "6. Validate response shape"
if [ "$status" = "200" ]; then
  python3 -m json.tool /tmp/autoconfig.json >/dev/null || fail "autoconfig body is not valid JSON"
  for key in ran_at discovered configured_now already_present skipped_no_match errors; do
    if ! python3 -c "import json,sys; sys.exit(0 if '$key' in json.load(open('/tmp/autoconfig.json')) else 1)"; then
      fail "key '$key' missing from autoconfig payload"
    fi
  done
  configured_now=$(python3 -c "import json; print(len(json.load(open('/tmp/autoconfig.json')).get('configured_now',[])))")
  echo "    configured_now count: $configured_now"
elif [ "$status" = "404" ]; then
  echo "    autoconfig has no recorded run (acceptable when no creds in env)"
else
  fail "autoconfig endpoint never settled (status='$status')"
fi

step "7. Run a search; assert no 5xx"
search_code=$(curl -s -o /tmp/search.json -w '%{http_code}' \
  -X POST "$MERGE/api/v1/search" \
  -H 'Content-Type: application/json' \
  -d '{"query":"ubuntu","category":"all"}' || true)
[ "$search_code" -ge 500 ] && fail "search returned $search_code"
echo "    search returned $search_code — OK"

echo "PASS: jackett_autoconfig_clean_slate"
exit 0
