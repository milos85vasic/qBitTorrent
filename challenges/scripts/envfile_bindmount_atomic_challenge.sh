#!/usr/bin/env bash
# envfile_bindmount_atomic_challenge.sh
#
# CONST-XII regression guard for the bind-mount EBUSY fix.
#
# WHAT IT VALIDATES:
#   The boba-jackett container's BOBA_ENV_PATH is bind-mounted as a
#   single file (`./.env:/host-env/.env`). Before the fix in
#   internal/envfile/write.go, EnsureMasterKey crash-looped because
#   `os.Rename(.env.tmp, .env)` returned EBUSY on bind-mount targets.
#   The fix added an EBUSY fallback that does in-place truncate+write.
#
# THIS CHALLENGE:
#   1. Builds the boba-jackett image fresh.
#   2. Creates a tmp host directory containing a SINGLE .env file (no
#      pre-existing master key) — emulates the production deploy state.
#   3. Runs the container with bind-mount of just that single file
#      (matching the docker-compose.yml semantics).
#   4. Waits up to 10s for /healthz to return 200.
#   5. Confirms the master key actually appears in the bind-mounted .env
#      AFTER the container starts — proving the in-place write worked.
#
# Anti-bluff: a stub that always returned "ok" from /healthz without
# writing the key would FAIL step 5 (grep for BOBA_MASTER_KEY=… in the
# host-side .env file).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"; podman rm -f boba-jackett-bindmount-challenge 2>/dev/null || true' EXIT

# 1) Pre-built image must exist OR build now (idempotent).
if ! podman image exists localhost/boba-jackett:dev 2>/dev/null; then
    echo "[1/5] Building boba-jackett image..."
    podman build -q -f "$REPO_ROOT/qBitTorrent-go/Dockerfile.jackett" -t localhost/boba-jackett:dev "$REPO_ROOT/qBitTorrent-go" >/dev/null
fi
echo "[1/5] image present: $(podman images --format '{{.ID}}' localhost/boba-jackett:dev)"

# 2) Set up tmp .env (single file, no master key)
mkdir -p "$WORK/cfg"
echo "FOO=bar" > "$WORK/.env"
chmod 0600 "$WORK/.env"
echo "[2/5] tmp .env seeded (no BOBA_MASTER_KEY): $(cat "$WORK/.env")"

# 3) Run container with single-file bind-mount (mimics compose)
echo "[3/5] starting boba-jackett with single-file .env bind-mount..."
podman run -d --rm \
    --name boba-jackett-bindmount-challenge \
    -p 17189:7189 \
    -v "$WORK/cfg:/config" \
    -v "$WORK/.env:/host-env/.env" \
    -e BOBA_DB_PATH=/config/boba.db \
    -e BOBA_ENV_PATH=/host-env/.env \
    -e JACKETT_URL=http://does-not-exist:9117 \
    -e JACKETT_API_KEY=x \
    -e PORT=7189 \
    localhost/boba-jackett:dev >/dev/null

# 4) Wait up to 10s for /healthz
echo "[4/5] waiting for /healthz..."
ok=0
for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    if curl -sf -m 2 http://localhost:17189/healthz >/dev/null 2>&1; then
        ok=1
        echo "    ready after ${i}s"
        break
    fi
done
if [[ $ok -ne 1 ]]; then
    echo "FAIL: container never became healthy in 10s"
    echo "--- container logs ---"
    podman logs --tail 30 boba-jackett-bindmount-challenge 2>&1 | sed 's/^/    /'
    exit 1
fi

# 5) Confirm BOBA_MASTER_KEY actually landed in the host-side .env
key_line="$(grep -E '^BOBA_MASTER_KEY=[0-9a-fA-F]{64}$' "$WORK/.env" || true)"
if [[ -z "$key_line" ]]; then
    echo "FAIL: BOBA_MASTER_KEY did not appear in host-mounted .env"
    echo "--- .env content ---"
    cat "$WORK/.env" | sed 's/^/    /'
    exit 1
fi
echo "[5/5] BOBA_MASTER_KEY persisted to host-mounted .env via in-place fallback ✓"
echo "    key length: $(echo -n "${key_line#BOBA_MASTER_KEY=}" | wc -c) chars (must be 64)"
echo "    FOO=bar still preserved: $(grep -c '^FOO=bar$' "$WORK/.env")"

echo "PASS: envfile_bindmount_atomic_challenge"
