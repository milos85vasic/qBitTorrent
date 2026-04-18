#!/usr/bin/env bash
# Security and operations — replayable demo.
#
# Non-interactive. Walks the partial scanner run (pip-audit + ruff)
# and lists artifacts/. Does NOT run the full --all scan (slow) and
# does NOT start Grafana. No privilege escalation, no stdin reads,
# no prompts.

set -euo pipefail

say() {
    printf '\n>>> %s\n' "$*"
}

say "[00:00] Security and operations"
say "We narrate the threat model and exercise the partial scanner bundle."

say "[00:20] In-scope threats (one minute)"
printf '%s\n' \
    '  1) Tracker creds in .env (never committed)' \
    '  2) Hardcoded admin/admin WebUI login (firewall, do not change)' \
    '  3) Subprocess template injection in plugin exec path'

say "[01:30] Scanner bundle entry point"
printf '  ./scripts/scan.sh [--ruff] [--bandit] [--pip-audit] [--gitleaks] [--trivy] [--semgrep] [--sonar] [--all]\n'

say "[02:30] Partial scan (pip-audit + ruff)"
printf '  ./scripts/scan.sh --pip-audit --ruff\n'
printf '  ls artifacts/scans/\n'

say "[03:30] Reading SARIF with jq"
printf '  jq ".runs[].results | length" artifacts/scans/pip-audit.sarif\n'
printf '  jq "[.runs[].results[] | {rule: .ruleId, msg: .message.text}]" artifacts/scans/ruff.sarif | head -c 600\n'

say "[04:30] Rotate tracker credentials"
printf '%s\n' \
    '  vim .env' \
    '  ./stop.sh && ./start.sh'
printf '  tests/unit/test_dotenv_guard.py fails if .env is ever git-tracked.\n'

say "[05:30] Encryption at rest — Phase 2.3 PENDING"
printf '  chmod 700 config/   # until Fernet-at-rest ships\n'

say "[06:30] Observability quickstart"
printf '%s\n' \
    '  ./start.sh -p' \
    '  podman compose -f docker-compose.quality.yml up -d' \
    '  open http://localhost:3000   # admin/admin, pre-seeded dashboards'

say "[07:30] Operator loop"
printf '%s\n' \
    '  weekly:   ./scripts/scan.sh --all' \
    '  always:   rotate creds via .env, not by rebuilding images' \
    '  watch:    Merge Search Overview for stalled trackers (P95 > 10s)'

say "[08:30] Done. See courses/03-contributor/ for the commit workflow."
