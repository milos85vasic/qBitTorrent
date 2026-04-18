#!/usr/bin/env bash
# Contributor deep-dive: TDD + rebuild-reboot — replayable demo.
#
# Walks: RED test -> watch fail -> GREEN implementation ->
# rebuild-reboot sanity -> scanner dry-run. All work happens in a
# tempdir so the real tree is not mutated. No privilege escalation,
# no stdin reads, no interactive prompts.

set -euo pipefail

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

say() {
    printf '\n>>> %s\n' "$*"
}

say "[00:00] Contributor deep-dive: TDD + rebuild-reboot"
say "All scratch files live under $WORK; no real sources are touched."

say "[00:30] The five-step cadence"
printf '  RED -> watch fail -> GREEN -> rebuild-reboot -> commit\n'

say "[01:15] Service fixtures replace runtime skips"
printf '  tests/fixtures/services.py -> merge_service_up, qbit_webui_up\n'

say "[02:00] Writing a RED test"
mkdir -p "$WORK/tests/unit" "$WORK/src"
cat >"$WORK/tests/unit/test_dedup_invariant.py" <<'TEST_EOF'
from src.dedup import dedup_titles


def test_collapses_identical_case_insensitive():
    rows = [
        {"name": "Ubuntu 24.04 ISO", "size": 1_000_000, "seeds": 10},
        {"name": "ubuntu 24.04 iso", "size": 1_000_000, "seeds":  7},
    ]
    out = dedup_titles(rows)
    assert len(out) == 1
    assert out[0]["seeds"] == 10
TEST_EOF

say "[02:45] Watching the RED (expected: ImportError from the missing src/dedup.py)"
cat >"$WORK/src/__init__.py" <<'INIT_EOF'
INIT_EOF

pushd "$WORK" >/dev/null
set +e
python3 -m pytest tests/unit/test_dedup_invariant.py --no-header -q 2>&1 | tail -n 5
RED_STATUS=$?
set -e
popd >/dev/null

if [ "$RED_STATUS" -eq 0 ]; then
    echo "!!! RED expected, got GREEN; something is wrong with the test."
    exit 1
fi
echo "  OK: RED observed (exit status $RED_STATUS)."

say "[03:30] Writing the GREEN implementation"
cat >"$WORK/src/dedup.py" <<'IMPL_EOF'
def dedup_titles(rows):
    seen = {}
    for row in rows:
        key = row["name"].strip().lower()
        existing = seen.get(key)
        if existing is None or row["seeds"] > existing["seeds"]:
            seen[key] = row
    return list(seen.values())
IMPL_EOF

say "[04:15] Re-run: expect GREEN"
pushd "$WORK" >/dev/null
python3 -m pytest tests/unit/test_dedup_invariant.py --no-header -q 2>&1 | tail -n 5
popd >/dev/null

say "[05:00] The mandatory rebuild-reboot (commands only; no real restart here)"
printf '%s\n' \
    '  ./stop.sh' \
    "  podman exec qbittorrent-proxy sh -lc 'find /app -name __pycache__ -exec rm -rf {} +' || true" \
    '  ./start.sh -p' \
    "  curl -s http://localhost:7187/ | grep -q 'merge-service'"

say "[06:00] Coverage ratchet reads from pyproject.toml"
printf '  python3 -m pytest --cov=download_proxy --cov-fail-under=<floor>\n'

say "[07:00] Local scanner dry-run"
printf '  ./scripts/scan.sh --all\n'
printf '  ls artifacts/scans/\n'

say "[07:45] Opening the PR"
printf '%s\n' \
    '  git push -u origin feature/dedup-invariant' \
    '  gh pr create --fill'

say "[09:15] Done. Next: courses/04-security-ops/."
