#!/usr/bin/env bash
# scripts/opencode-helixqa.sh — use OpenCode as the CLI agent that
# orchestrates HelixQA curiosity runs, following the courses/ scripts.
#
# Requires:
#   * `opencode` CLI on PATH
#   * `helixqa` CLI on PATH (see scripts/helixqa.sh)
#   * OPENCODE_API_KEY env var set

set -euo pipefail

print_info()    { printf '\033[0;34m[INFO]\033[0m %s\n' "$*"; }
print_success() { printf '\033[0;32m[ OK ]\033[0m %s\n' "$*"; }
print_error()   { printf '\033[0;31m[FAIL]\033[0m %s\n' "$*" >&2; }

if ! command -v opencode >/dev/null 2>&1; then
    print_error "opencode is not on PATH. See docs/OUT_OF_SANDBOX.md §2."
    exit 3
fi
if [[ -z "${OPENCODE_API_KEY:-}" ]]; then
    print_error "OPENCODE_API_KEY is not set"
    exit 4
fi
if ! command -v helixqa >/dev/null 2>&1; then
    print_error "helixqa is not on PATH. See docs/OUT_OF_SANDBOX.md §1."
    exit 3
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
ARTIFACTS="artifacts/opencode-helixqa/$timestamp"
mkdir -p "$ARTIFACTS"

# Feed the course scripts + explicit HelixQA objective. `opencode run`
# is assumed to take `--no-interactive`, a prompt file, and tool
# arguments — adapt to the real CLI signature when installed.
for track in 01-operator 02-plugin-author 03-contributor 04-security-ops; do
    print_info "OpenCode → HelixQA :: $track"
    opencode run \
        --no-interactive \
        --api-key "$OPENCODE_API_KEY" \
        --prompt-file "courses/$track/script.md" \
        --tool helixqa \
        --tool-args "--scenario courses/$track/script.md --mode curiosity --record --artifact-dir $ARTIFACTS/$track" \
        > "$ARTIFACTS/$track.log" 2>&1
    print_success "track $track → $ARTIFACTS/$track"
done

print_success "OpenCode + HelixQA sessions complete: $ARTIFACTS"
