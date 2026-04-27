#!/usr/bin/env bash
# env_db_drift_challenge.sh — Layer 7 .env ↔ DB consistency gate.
#
# EXPECT: After 10 sequential POST/DELETE operations through the API,
# the .env credential set and the DB credential set are equivalent in
# names. A drift means the .env mirror failed silently or the DB write
# failed without a compensating rollback.
#
# Anti-bluff: stub envfile.Upsert to no-op → after step 10, the .env
# would have N missing lines vs the DB. The challenge prints the diff
# and exits non-zero.
#
# Pass: PASS message + exit 0
# Fail: FAIL: <reason> + exit 1

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT/qBitTorrent-go"

if [ ! -x "./bin/boba-jackett" ]; then
  go build -o ./bin/boba-jackett ./cmd/boba-jackett
fi

TMPDIR_BOBA="$(mktemp -d -t boba-drift-XXXXXX)"
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

BOBA_DB_PATH="$DBPATH" BOBA_ENV_PATH="$ENVPATH" \
JACKETT_URL="http://127.0.0.1:1" JACKETT_API_KEY="" PORT="$PORT" \
./bin/boba-jackett >"$TMPDIR_BOBA/boba.log" 2>&1 &
PID=$!

deadline=$(( $(date +%s) + 5 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && break
  sleep 0.2
done
curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 || {
  echo "FAIL: boba-jackett not ready"
  cat "$TMPDIR_BOBA/boba.log"
  exit 1
}

# Step 1-5: insert 5 credentials.
for i in 1 2 3 4 5; do
  curl -sf -u admin:admin -H "Content-Type: application/json" \
    -X POST "http://127.0.0.1:$PORT/api/v1/jackett/credentials" \
    -d "{\"name\":\"DRIFT_$i\",\"username\":\"u$i\",\"password\":\"p$i\"}" \
    > /dev/null \
    || { echo "FAIL: insert $i"; exit 1; }
done

# Step 6-7: update 2 of them (PATCH semantics — only password).
for i in 1 2; do
  curl -sf -u admin:admin -H "Content-Type: application/json" \
    -X POST "http://127.0.0.1:$PORT/api/v1/jackett/credentials" \
    -d "{\"name\":\"DRIFT_$i\",\"password\":\"p${i}_v2\"}" \
    > /dev/null \
    || { echo "FAIL: update $i"; exit 1; }
done

# Step 8-10: delete 3 of them (3, 4, 5).
for i in 3 4 5; do
  curl -sf -u admin:admin -X DELETE \
    "http://127.0.0.1:$PORT/api/v1/jackett/credentials/DRIFT_$i" \
    > /dev/null \
    || { echo "FAIL: delete $i"; exit 1; }
done

# Compare .env vs DB.
# DB names (via API GET /credentials).
db_names=$(curl -sf "http://127.0.0.1:$PORT/api/v1/jackett/credentials" \
  | python3 -c "import json,sys; rows=json.load(sys.stdin); print('\n'.join(sorted([r['name'] for r in rows])))")

# .env names: derived from any *_USERNAME line whose prefix is DRIFT_.
env_names=$(grep -E "^DRIFT_[0-9]+_USERNAME=" "$ENVPATH" \
  | sed 's/_USERNAME=.*//' | sort -u)

echo "DB names:"
echo "$db_names" | sed 's/^/  /'
echo ".env names:"
echo "$env_names" | sed 's/^/  /'

# Both sets must equal {DRIFT_1, DRIFT_2}.
expected="DRIFT_1
DRIFT_2"

if [ "$db_names" != "$expected" ]; then
  echo "FAIL: DB names diverged from expected:"
  diff <(echo "$expected") <(echo "$db_names") || true
  exit 1
fi
if [ "$env_names" != "$expected" ]; then
  echo "FAIL: .env names diverged from DB:"
  diff <(echo "$db_names") <(echo "$env_names") || true
  exit 1
fi

# Update assertion: DRIFT_1's password line in .env must equal p1_v2.
if ! grep -q "^DRIFT_1_PASSWORD=p1_v2\$" "$ENVPATH"; then
  echo "FAIL: .env DRIFT_1_PASSWORD did not update to p1_v2"
  grep "^DRIFT_1" "$ENVPATH"
  exit 1
fi

echo "PASS: env_db_drift_challenge"
exit 0
