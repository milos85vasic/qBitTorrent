#!/usr/bin/env bash
# cred_roundtrip_challenge.sh — Layer 7 round-trip gate.
#
# EXPECT: After POST /api/v1/jackett/credentials with username+password:
#   1. GET /api/v1/jackett/credentials returns the row's metadata only
#      (has_username=true, has_password=true). Plaintext is NOT in the
#      response body.
#   2. .env file contains both <NAME>_USERNAME=plaintext and
#      <NAME>_PASSWORD=plaintext lines.
#   3. boba.db file exists and contains NEITHER plaintext anywhere
#      (encrypted-at-rest).
#
# Anti-bluff: any of (1)-(3) failing means the spec §7 row 1 contract
# is broken. A no-op envfile.Upsert would fail (2). A no-op Encrypt
# would fail (3) with plaintext bytes visible in the .db file.
#
# Pass: PASS message + exit 0
# Fail: FAIL: <reason> + exit 1

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT/qBitTorrent-go"

# Build if needed.
if [ ! -x "./bin/boba-jackett" ]; then
  go build -o ./bin/boba-jackett ./cmd/boba-jackett
fi

TMPDIR_BOBA="$(mktemp -d -t boba-roundtrip-XXXXXX)"
PORT=$(( ( RANDOM % 10000 ) + 30000 ))
DBPATH="$TMPDIR_BOBA/boba.db"
ENVPATH="$TMPDIR_BOBA/.env"

cleanup() {
  if [ -n "${PID:-}" ]; then
    kill -TERM "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
  rm -rf "$TMPDIR_BOBA"
}
trap cleanup EXIT

BOBA_DB_PATH="$DBPATH" \
BOBA_ENV_PATH="$ENVPATH" \
JACKETT_URL="http://127.0.0.1:1" \
JACKETT_API_KEY="" \
PORT="$PORT" \
./bin/boba-jackett >"$TMPDIR_BOBA/boba.log" 2>&1 &
PID=$!

# Wait for /healthz.
deadline=$(( $(date +%s) + 5 ))
ready=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  if curl -sf -o /dev/null "http://127.0.0.1:$PORT/healthz" 2>/dev/null; then
    ready=1
    break
  fi
  sleep 0.2
done
if [ "$ready" != "1" ]; then
  echo "FAIL: boba-jackett not ready"; cat "$TMPDIR_BOBA/boba.log"; exit 1
fi

# Sentinel plaintexts that a stub would leak.
USER="cred-roundtrip-USER-sentinel-XXXX"
PASS="cred-roundtrip-PASS-sentinel-YYYY"

# (a) POST credential.
post_status=$(curl -s -o /tmp/cred_post.json -w '%{http_code}' \
  -u admin:admin -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:$PORT/api/v1/jackett/credentials" \
  -d "{\"name\":\"ROUNDTRIP\",\"username\":\"$USER\",\"password\":\"$PASS\"}")
echo "POST /credentials: status=$post_status"
echo "  body: $(cat /tmp/cred_post.json)"
if [ "$post_status" != "200" ]; then
  echo "FAIL: POST returned $post_status"; exit 1
fi

# (1) GET response body MUST NOT contain plaintext.
get_status=$(curl -s -o /tmp/cred_get.json -w '%{http_code}' \
  "http://127.0.0.1:$PORT/api/v1/jackett/credentials")
if [ "$get_status" != "200" ]; then
  echo "FAIL: GET status=$get_status"; exit 1
fi
echo "GET /credentials body: $(cat /tmp/cred_get.json)"
if grep -q "$USER" /tmp/cred_get.json; then
  echo "FAIL: GET response leaked plaintext username"; exit 1
fi
if grep -q "$PASS" /tmp/cred_get.json; then
  echo "FAIL: GET response leaked plaintext password"; exit 1
fi
if ! grep -q '"has_username":true' /tmp/cred_get.json; then
  echo "FAIL: GET response missing has_username:true"; exit 1
fi
if ! grep -q '"has_password":true' /tmp/cred_get.json; then
  echo "FAIL: GET response missing has_password:true"; exit 1
fi
echo "  OK — GET response is metadata-only"

# (2) .env must contain both plaintext lines.
if ! grep -q "^ROUNDTRIP_USERNAME=$USER\$" "$ENVPATH"; then
  echo "FAIL: .env missing ROUNDTRIP_USERNAME=$USER line"
  echo "--- .env ---"; cat "$ENVPATH"
  exit 1
fi
if ! grep -q "^ROUNDTRIP_PASSWORD=$PASS\$" "$ENVPATH"; then
  echo "FAIL: .env missing ROUNDTRIP_PASSWORD=$PASS line"
  echo "--- .env ---"; cat "$ENVPATH"
  exit 1
fi
echo "  OK — .env contains plaintext mirror lines"

# (3) boba.db must NOT contain plaintext.
if grep -q "$USER" "$DBPATH" 2>/dev/null; then
  echo "FAIL: boba.db contains plaintext username — encryption broken"; exit 1
fi
if grep -q "$PASS" "$DBPATH" 2>/dev/null; then
  echo "FAIL: boba.db contains plaintext password — encryption broken"; exit 1
fi
echo "  OK — boba.db has no plaintext (encrypted-at-rest)"

echo "PASS: cred_roundtrip_challenge"
exit 0
