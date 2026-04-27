#!/usr/bin/env bash
# run_all_challenges.sh — runs every *_challenge.sh script in this dir.
#
# Filters by the `_challenge.sh` suffix so legacy scripts that don't
# match (e.g. jackett_autoconfig_clean_slate.sh which targets the full
# stack) are NOT run by this aggregator. To run the legacy clean-slate
# script, invoke it directly.
#
# Each challenge is given a generous per-script timeout (180s default,
# overridable via CHALLENGE_TIMEOUT env). A timed-out challenge counts
# as a fail.
#
# Exit:
#   0 = all PASS / SKIP
#   1 = one or more FAIL or timeout
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMEOUT_S="${CHALLENGE_TIMEOUT:-180}"

fails=0
total=0
for script in "$HERE"/*_challenge.sh; do
  name="$(basename "$script")"
  [ "$name" = "run_all_challenges.sh" ] && continue
  total=$((total + 1))
  echo "================================================================"
  echo "=== $name (timeout ${TIMEOUT_S}s)"
  echo "================================================================"
  if ! timeout "$TIMEOUT_S" bash "$script"; then
    rc=$?
    if [ "$rc" = "124" ]; then
      echo "TIMEOUT: $name (exceeded ${TIMEOUT_S}s)"
    else
      echo "FAIL: $name (exit $rc)"
    fi
    fails=$((fails + 1))
  fi
done
echo "================================================================"
echo "Challenges total: $total | failed: $fails"
echo "================================================================"
exit $fails
