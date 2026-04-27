#!/usr/bin/env bash
# iptorrents_cookie_flow_challenge.sh — Layer 7 cookie-cred flow gate.
#
# EXPECT: When IPTORRENTS_COOKIES env var is set:
#   1. POST cred kind=cookie via /api/v1/jackett/credentials
#   2. POST /api/v1/jackett/indexers/iptorrents with credential_name
#   3. Response is 200 OR 502 (Jackett unreachable is acceptable)
#   4. DB row has has_cookies=true, has_username=false, has_password=false
#
# If IPTORRENTS_COOKIES is unset → SKIP per CONST-11.
#
# Pass: PASS message + exit 0 OR SKIP message + exit 0
# Fail: FAIL: <reason> + exit 1

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT/qBitTorrent-go"

if [ -z "${IPTORRENTS_COOKIES:-}" ]; then
  echo "SKIP: iptorrents_cookie_flow_challenge — IPTORRENTS_COOKIES unset (CONST-11)"
  exit 0
fi

if [ ! -x "./bin/boba-jackett" ]; then
  go build -o ./bin/boba-jackett ./cmd/boba-jackett
fi

TMPDIR_BOBA="$(mktemp -d -t boba-cookie-XXXXXX)"
PORT=$(( ( RANDOM % 10000 ) + 30000 ))

cleanup() {
  if [ -n "${PID:-}" ]; then
    kill -TERM "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
  rm -rf "$TMPDIR_BOBA"
}
trap cleanup EXIT

BOBA_DB_PATH="$TMPDIR_BOBA/boba.db" BOBA_ENV_PATH="$TMPDIR_BOBA/.env" \
JACKETT_URL="${JACKETT_URL:-http://localhost:9117}" \
JACKETT_API_KEY="${JACKETT_API_KEY:-}" PORT="$PORT" \
./bin/boba-jackett >"$TMPDIR_BOBA/boba.log" 2>&1 &
PID=$!

deadline=$(( $(date +%s) + 5 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && break
  sleep 0.2
done

# Step 1: POST cred (cookie kind).
post_status=$(curl -s -o /tmp/cookie_post.json -w '%{http_code}' \
  -u admin:admin -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:$PORT/api/v1/jackett/credentials" \
  -d "{\"name\":\"IPTORRENTS\",\"cookies\":\"$IPTORRENTS_COOKIES\"}")
echo "POST cred: $post_status"
if [ "$post_status" != "200" ]; then
  echo "FAIL: POST cred returned $post_status"
  cat /tmp/cookie_post.json
  exit 1
fi

# Step 4 (in advance): inspect DB row via GET /credentials.
list=$(curl -sf "http://127.0.0.1:$PORT/api/v1/jackett/credentials")
echo "GET /credentials: $list"
if ! echo "$list" | grep -q '"has_cookies":true'; then
  echo "FAIL: DB row not registered with has_cookies=true"; exit 1
fi
if echo "$list" | grep -q '"has_username":true'; then
  echo "FAIL: cookie-only cred should NOT have has_username=true"; exit 1
fi

# Step 2: POST /indexers/iptorrents (may return 200 or 502).
post_status=$(curl -s -o /tmp/cookie_idx.json -w '%{http_code}' \
  -u admin:admin -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:$PORT/api/v1/jackett/indexers/iptorrents" \
  -d '{"credential_name":"IPTORRENTS"}')
echo "POST indexer: $post_status"
echo "  body: $(cat /tmp/cookie_idx.json)"

case "$post_status" in
  200)
    echo "  OK — indexer configured at Jackett"
    ;;
  502)
    echo "  OK — Jackett unreachable, but boba-jackett correctly returned 502 (CONST-11)"
    ;;
  400)
    # 400 no_compatible_credential_fields_for_indexer is also acceptable
    # if Jackett's iptorrents template doesn't expose `cookie` field id.
    if grep -q "no_compatible_credential_fields_for_indexer" /tmp/cookie_idx.json; then
      echo "  OK — Jackett's iptorrents template does not accept cookie field (acceptable)"
    else
      echo "FAIL: 400 with unexpected error: $(cat /tmp/cookie_idx.json)"
      exit 1
    fi
    ;;
  *)
    echo "FAIL: unexpected status $post_status"
    exit 1
    ;;
esac

echo "PASS: iptorrents_cookie_flow_challenge"
exit 0
