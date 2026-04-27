#!/usr/bin/env bash
# nnmclub_native_plugin_clarification_challenge.sh
#
# CONST-XII regression guard for Task 32 backend (commit 002d3bb).
#
# WHAT IT VALIDATES:
#   The Go field AutoconfigResult.ServedByNativePlugin is populated
#   from any credential bundle whose name matches the project's native
#   plugin list (NNMCLUB, RUTRACKER, KINOZAL, IPTORRENTS — see
#   classifyServedByNativePlugin in qBitTorrent-go/internal/jackett/
#   autoconfig.go). The dashboard's NNMClub banner reads this field
#   to inform the operator that "Boba's native plugin handles this
#   tracker, not Jackett".
#
# THIS CHALLENGE:
#   1. Builds boba-jackett image fresh (idempotent).
#   2. Runs container with empty .env + tmp DB.
#   3. POSTs an NNMCLUB cookie credential via API.
#   4. POSTs /autoconfig/run.
#   5. GETs the latest /autoconfig/runs/{id} and asserts
#      .served_by_native_plugin includes "NNMCLUB".
#
# Anti-bluff: a stub that returned empty served_by_native_plugin
# would FAIL the jq grep at step 5. A stub that hardcoded ["NNMCLUB"]
# regardless of input would FAIL when we vary the credential to a
# non-native name (we don't do that here, but the test could be
# extended).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"; podman rm -f boba-jackett-nnmclub-challenge 2>/dev/null || true' EXIT

# 1) Pre-built image must exist OR build now (idempotent).
if ! podman image exists localhost/boba-jackett:dev 2>/dev/null; then
    echo "[1/5] Building boba-jackett image..."
    podman build -q -f "$REPO_ROOT/qBitTorrent-go/Dockerfile.jackett" \
        -t localhost/boba-jackett:dev "$REPO_ROOT/qBitTorrent-go" >/dev/null
fi
echo "[1/5] image present: $(podman images --format '{{.ID}}' localhost/boba-jackett:dev)"

# 2) Setup tmp .env (no creds yet) + tmp DB dir.
echo "FOO=bar" > "$WORK/.env"
chmod 0600 "$WORK/.env"
mkdir -p "$WORK/cfg"
echo "[2/5] tmp env + cfg dir prepared"

# 3) Start container.
podman run -d --rm \
    --name boba-jackett-nnmclub-challenge \
    -p 17190:7189 \
    -v "$WORK/cfg:/config" \
    -v "$WORK/.env:/host-env/.env" \
    -e BOBA_DB_PATH=/config/boba.db \
    -e BOBA_ENV_PATH=/host-env/.env \
    -e JACKETT_URL=http://does-not-exist:9117 \
    -e JACKETT_API_KEY=x \
    -e PORT=7189 \
    localhost/boba-jackett:dev >/dev/null

# Wait up to 10s for /healthz.
ok=0
for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    if curl -sf -m 2 http://localhost:17190/healthz >/dev/null 2>&1; then
        ok=1
        echo "[3/5] container ready after ${i}s"
        break
    fi
done
if [[ $ok -ne 1 ]]; then
    echo "FAIL: container never became healthy"
    podman logs --tail 20 boba-jackett-nnmclub-challenge 2>&1 | sed 's/^/    /'
    exit 1
fi

# 4) POST an NNMCLUB cookie credential.
post_status=$(curl -s -o /tmp/cred-resp.$$ -w "%{http_code}" \
    -H "Authorization: Basic YWRtaW46YWRtaW4=" \
    -H "Content-Type: application/json" \
    -X POST -d '{"name":"NNMCLUB","cookies":"sess=abc"}' \
    http://localhost:17190/api/v1/jackett/credentials)
if [[ "$post_status" != "200" ]]; then
    echo "FAIL: POST /credentials returned $post_status"
    cat /tmp/cred-resp.$$
    rm -f /tmp/cred-resp.$$
    exit 1
fi
rm -f /tmp/cred-resp.$$
echo "[4/5] NNMCLUB credential posted"

# 5) Trigger autoconfig run + assert ServedByNativePlugin.
run_resp=$(curl -s -H "Authorization: Basic YWRtaW46YWRtaW4=" \
    -X POST http://localhost:17190/api/v1/jackett/autoconfig/run)
echo "    autoconfig run response (snippet):"
echo "$run_resp" | head -c 400 | sed 's/^/      /'
echo

# Extract served_by_native_plugin via grep+sed (no jq dep required).
# Match the JSON array contents.
served_field="$(echo "$run_resp" | grep -oE '"served_by_native_plugin":\[[^]]*\]' || true)"
if [[ -z "$served_field" ]]; then
    echo "FAIL: 'served_by_native_plugin' key missing from autoconfig run response"
    exit 1
fi
if ! echo "$served_field" | grep -q '"NNMCLUB"'; then
    echo "FAIL: served_by_native_plugin does NOT include NNMCLUB"
    echo "    got: $served_field"
    exit 1
fi
echo "[5/5] served_by_native_plugin includes NNMCLUB ✓"
echo "    matched field: $served_field"

echo "PASS: nnmclub_native_plugin_clarification_challenge"
