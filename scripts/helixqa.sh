#!/usr/bin/env bash
# scripts/helixqa.sh — non-interactive driver for HelixQA curiosity testing.
#
# Requires: `helixqa` binary on PATH, a running stack, and
# (for --record) a display server that can host the headless
# browser HelixQA spawns.
#
# Usage:
#   ./scripts/helixqa.sh                 # run all four course tracks
#   ./scripts/helixqa.sh --record        # also capture video
#   ./scripts/helixqa.sh operator        # single track
#   ./scripts/helixqa.sh --help

set -euo pipefail

print_info()    { printf '\033[0;34m[INFO]\033[0m %s\n' "$*"; }
print_success() { printf '\033[0;32m[ OK ]\033[0m %s\n' "$*"; }
print_warning() { printf '\033[0;33m[WARN]\033[0m %s\n' "$*"; }
print_error()   { printf '\033[0;31m[FAIL]\033[0m %s\n' "$*" >&2; }

usage() {
    cat <<'USAGE'
Usage:
  ./scripts/helixqa.sh [TRACKS...] [--record] [--help]

Tracks (default: all four):
  operator          Course 01 — first search + download
  plugin-author     Course 02 — authoring a nova3 plugin
  contributor       Course 03 — TDD + rebuild-reboot
  security-ops      Course 04 — threat model + scanner bundle

Flags:
  --record          Capture video (requires display server)
  --artifacts DIR   Override artefact directory
  --merge-url URL   Default: http://localhost:7187
  --qbit-url URL    Default: http://localhost:7186

Environment variables:
  HELIXQA_API_KEY   required when HelixQA is in cloud mode
USAGE
}

RECORD=0
declare -a TRACKS=()
MERGE_URL="http://localhost:7187"
QBIT_URL="http://localhost:7186"
ARTIFACTS_ROOT=""

while (( $# )); do
    case "$1" in
        --record) RECORD=1; shift ;;
        --artifacts) ARTIFACTS_ROOT="$2"; shift 2 ;;
        --artifacts=*) ARTIFACTS_ROOT="${1#*=}"; shift ;;
        --merge-url) MERGE_URL="$2"; shift 2 ;;
        --qbit-url) QBIT_URL="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        -*) print_error "unknown flag: $1"; usage; exit 2 ;;
        *) TRACKS+=("$1"); shift ;;
    esac
done

if (( ${#TRACKS[@]} == 0 )); then
    TRACKS=(operator plugin-author contributor security-ops)
fi

if ! command -v helixqa >/dev/null 2>&1; then
    print_error "helixqa is not on PATH. See docs/OUT_OF_SANDBOX.md §1."
    exit 3
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
ARTIFACTS_ROOT="${ARTIFACTS_ROOT:-artifacts/helixqa/$timestamp}"
mkdir -p "$ARTIFACTS_ROOT"

if ! curl -sf "$MERGE_URL/health" >/dev/null; then
    print_error "merge service at $MERGE_URL is not healthy"
    exit 4
fi

for track in "${TRACKS[@]}"; do
    local_dir="$ARTIFACTS_ROOT/$track"
    mkdir -p "$local_dir"
    print_info "HelixQA track: $track"
    local_script="courses/01-operator/script.md"
    case "$track" in
        operator)       local_script="courses/01-operator/script.md" ;;
        plugin-author)  local_script="courses/02-plugin-author/script.md" ;;
        contributor)    local_script="courses/03-contributor/script.md" ;;
        security-ops)   local_script="courses/04-security-ops/script.md" ;;
        *) print_error "unknown track: $track"; exit 2 ;;
    esac
    args=(
        --scenario "$local_script"
        --target "$MERGE_URL"
        --qbittorrent "$QBIT_URL"
        --artifact-dir "$local_dir"
        --mode curiosity
        --no-interactive
    )
    if (( RECORD )); then
        args+=(--record --record-format mp4)
    fi
    if [[ -n "${HELIXQA_API_KEY:-}" ]]; then
        args+=(--api-key "$HELIXQA_API_KEY")
    fi
    helixqa run "${args[@]}"
    print_success "track $track → $local_dir"
done

print_success "HelixQA sessions complete. Artefacts: $ARTIFACTS_ROOT"
