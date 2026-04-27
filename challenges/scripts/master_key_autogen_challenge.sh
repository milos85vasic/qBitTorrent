#!/usr/bin/env bash
# master_key_autogen_challenge.sh — Layer 7 master-key autogen gate.
#
# EXPECT:
#   1. Boot boba-jackett against an empty tmp .env → BOBA_MASTER_KEY
#      appears in .env, with the warning header sentinel block.
#   2. Restart against the SAME .env → key value unchanged.
#
# Anti-bluff: stub bootstrap.EnsureMasterKey to always-generate → step
# 2 detects key mutation. Stub it to in-memory-only → step 1 catches it
# (no key in the .env file at all).
#
# Pass: PASS message + exit 0
# Fail: FAIL: <reason> + exit 1

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT/qBitTorrent-go"

if [ ! -x "./bin/boba-jackett" ]; then
  go build -o ./bin/boba-jackett ./cmd/boba-jackett
fi

TMPDIR_BOBA="$(mktemp -d -t boba-mkey-XXXXXX)"
PORT=$(( ( RANDOM % 10000 ) + 30000 ))
ENVPATH="$TMPDIR_BOBA/.env"

cleanup() {
  if [ -n "${PID:-}" ]; then
    kill -TERM "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
  rm -rf "$TMPDIR_BOBA"
}
trap cleanup EXIT

# Step 1: fresh dir without .env (file does not exist at all).
BOBA_DB_PATH="$TMPDIR_BOBA/boba.db" BOBA_ENV_PATH="$ENVPATH" \
JACKETT_URL="http://127.0.0.1:1" JACKETT_API_KEY="" PORT="$PORT" \
./bin/boba-jackett >"$TMPDIR_BOBA/boba1.log" 2>&1 &
PID=$!

deadline=$(( $(date +%s) + 5 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && break
  sleep 0.2
done
curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 || {
  echo "FAIL: first boot failed"
  cat "$TMPDIR_BOBA/boba1.log"
  exit 1
}

# Stop run 1.
kill -TERM "$PID" 2>/dev/null || true
wait "$PID" 2>/dev/null || true
PID=""

# Assertions for run 1:
if ! grep -q '=== BOBA SYSTEM ===' "$ENVPATH"; then
  echo "FAIL: master-key header sentinel missing from .env after first boot"
  cat "$ENVPATH"
  exit 1
fi
key1=$(grep '^BOBA_MASTER_KEY=' "$ENVPATH" | head -1 | sed 's/^BOBA_MASTER_KEY=//')
if [ -z "$key1" ]; then
  echo "FAIL: BOBA_MASTER_KEY not persisted after first boot"
  cat "$ENVPATH"
  exit 1
fi
# Hex 64-char regex.
if ! [[ "$key1" =~ ^[0-9a-fA-F]{64}$ ]]; then
  echo "FAIL: BOBA_MASTER_KEY not 64-hex: $key1"
  exit 1
fi
echo "  Run 1: key generated, regex OK ($(echo -n "$key1" | wc -c) chars)"

# Step 2: restart against the SAME .env.
PORT2=$(( ( RANDOM % 10000 ) + 30000 ))
BOBA_DB_PATH="$TMPDIR_BOBA/boba.db" BOBA_ENV_PATH="$ENVPATH" \
JACKETT_URL="http://127.0.0.1:1" JACKETT_API_KEY="" PORT="$PORT2" \
./bin/boba-jackett >"$TMPDIR_BOBA/boba2.log" 2>&1 &
PID=$!

deadline=$(( $(date +%s) + 5 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  curl -sf "http://127.0.0.1:$PORT2/healthz" >/dev/null 2>&1 && break
  sleep 0.2
done
curl -sf "http://127.0.0.1:$PORT2/healthz" >/dev/null 2>&1 || {
  echo "FAIL: second boot failed"
  cat "$TMPDIR_BOBA/boba2.log"
  exit 1
}

key2=$(grep '^BOBA_MASTER_KEY=' "$ENVPATH" | head -1 | sed 's/^BOBA_MASTER_KEY=//')
if [ "$key1" != "$key2" ]; then
  echo "FAIL: master key mutated across restart"
  echo "  was: $key1"
  echo "  now: $key2"
  exit 1
fi
echo "  Run 2: key unchanged ($key2 == $key1)"

# Run 2 log should NOT print "BOBA_MASTER_KEY generated" again.
if grep -q "BOBA_MASTER_KEY generated" "$TMPDIR_BOBA/boba2.log"; then
  echo "FAIL: second boot regenerated key (per its own log)"
  grep "BOBA_MASTER_KEY" "$TMPDIR_BOBA/boba2.log"
  exit 1
fi

echo "PASS: master_key_autogen_challenge"
exit 0
