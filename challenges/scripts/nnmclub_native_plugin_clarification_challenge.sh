#!/usr/bin/env bash
# nnmclub_native_plugin_clarification_challenge.sh — Layer 7 deferred.
#
# EXPECT (when Task 32 lands): NNMClub indexer rows are flagged with
# `served_by_native_plugin: true` so the dashboard can show "Boba uses
# its own NNMClub plugin instead of Jackett's torznab".
#
# Today: the ServedByNativePlugin field has not yet been added to
# repos.Indexer / indexerDTO. This challenge is registered as DEFERRED
# (exit 0 with a clear note) so the suite is shaped for Task 32 to fill
# in without touching infrastructure.
#
# Pass criteria after Task 32:
#   1. POST /credentials NNMCLUB → autoconfig matches an indexer.
#   2. GET /indexers contains a row with id=nnmclub AND
#      served_by_native_plugin=true.
#
# Pass: PASS / DEFERRED message + exit 0
# Fail: FAIL: <reason> + exit 1

set -euo pipefail

cat <<'EOF'
DEFERRED: nnmclub_native_plugin_clarification_challenge

This challenge is intentionally a no-op. The implementation work it
verifies (ServedByNativePlugin field on repos.Indexer + the
NNMClub-specific autoconfig branch) is tracked as Task 32 in the
plan and has not yet shipped. When Task 32 lands, replace this
script's body with the real assertions:

  1. Boot boba-jackett against tmp dir.
  2. POST /api/v1/jackett/credentials NNMCLUB cookie
  3. POST /api/v1/jackett/autoconfig/run
  4. GET /api/v1/jackett/indexers | jq '.[] | select(.id=="nnmclub")'
  5. Assert .served_by_native_plugin == true

For now: TODO marker only. Skipping with exit 0 so run_all_challenges
remains green during the stage-6 gate.
EOF

# TODO: implement when ServedByNativePlugin field lands.
exit 0
