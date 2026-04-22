#!/usr/bin/env bash
# scripts/scan.sh — non-automated security scanner orchestrator
# Runs scanners, writes SARIF/JSON reports to artifacts/scans/<timestamp>/.
# Exits non-zero on high/critical findings.
#
# Strictly non-automated: never prompts, never escalates privileges,
# never reads from stdin. If a required tool is missing, that scanner
# is skipped with a WARNING and the script continues.
#
# Usage:
#   ./scripts/scan.sh --full                 # run every scanner
#   ./scripts/scan.sh --quick                # bandit + pip-audit only
#   ./scripts/scan.sh --scanner bandit       # run named scanner only
#   ./scripts/scan.sh --help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

detect_container_runtime() {
    if command -v podman >/dev/null 2>&1; then
        CONTAINER_RUNTIME="podman"
    elif command -v docker >/dev/null 2>&1; then
        CONTAINER_RUNTIME="docker"
    else
        CONTAINER_RUNTIME=""
    fi

    if [[ -n "$CONTAINER_RUNTIME" ]]; then
        if $CONTAINER_RUNTIME compose version >/dev/null 2>&1; then
            COMPOSE_CMD="$CONTAINER_RUNTIME compose"
        elif command -v docker-compose >/dev/null 2>&1; then
            COMPOSE_CMD="docker-compose"
        elif command -v podman-compose >/dev/null 2>&1; then
            COMPOSE_CMD="podman-compose"
        else
            COMPOSE_CMD=""
        fi
    else
        COMPOSE_CMD=""
    fi
}

print_info()    { printf '\033[0;34m[INFO]\033[0m %s\n' "$*"; }
print_success() { printf '\033[0;32m[ OK ]\033[0m %s\n' "$*"; }
print_warning() { printf '\033[0;33m[WARN]\033[0m %s\n' "$*"; }
print_error()   { printf '\033[0;31m[FAIL]\033[0m %s\n' "$*" >&2; }

usage() {
    cat <<'USAGE'
Usage:
  ./scripts/scan.sh [OPTIONS]

Options:
  --full              Run all scanners
  --quick             Run only bandit + pip-audit (fast)
  --scanner <name>    Run a specific scanner only
  -h, --help          Show this help message

Scanners:
  bandit              Python SAST on download-proxy/src/ and plugins/
  semgrep             SAST rules (.semgrep.yml config)
  trivy               Filesystem CVE + misconfig + secret scan
  gitleaks            Secret detection via git history
  pip-audit           Python dependency CVE scan on requirements files

Environment variables:
  SCAN_ARTIFACTS_DIR  Override default output directory
                       (default: artifacts/scans/<UTC timestamp>/)

Exit codes:
  0 on full pass, non-zero if any scanner reports high/critical findings.
USAGE
}

QUICK_MODE=0
FULL_MODE=0
SPECIFIC_SCANNER=""

while (( $# )); do
    case "$1" in
        --full)       FULL_MODE=1; shift ;;
        --quick)      QUICK_MODE=1; shift ;;
        --scanner)    shift; SPECIFIC_SCANNER="${1:-}"; shift ;;
        -h|--help)    usage; exit 0 ;;
        --)           shift; break ;;
        -*)           print_error "unknown flag: $1"; usage; exit 2 ;;
        *)            print_error "unexpected argument: $1"; usage; exit 2 ;;
    esac
done

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
ARTIFACT_DIR="${SCAN_ARTIFACTS_DIR:-artifacts/scans/$timestamp}"
mkdir -p "$ARTIFACT_DIR"
print_info "reports → $ARTIFACT_DIR"

detect_container_runtime

CORE_SCANNERS=(bandit pip-audit)
ALL_SCANNERS=(bandit semgrep trivy gitleaks pip-audit)

if (( QUICK_MODE )); then
    SCANNERS=("${CORE_SCANNERS[@]}")
elif (( FULL_MODE )); then
    SCANNERS=("${ALL_SCANNERS[@]}")
elif [[ -n "$SPECIFIC_SCANNER" ]]; then
    SCANNERS=("$SPECIFIC_SCANNER")
else
    SCANNERS=("${ALL_SCANNERS[@]}")
fi

EXIT_CODE=0

run_bandit() {
    print_info "running bandit"
    if command -v bandit >/dev/null 2>&1; then
        bandit -r download-proxy/src plugins \
            -c pyproject.toml \
            -f json -o "$ARTIFACT_DIR/bandit.json" \
            || EXIT_CODE=1
        bandit -r download-proxy/src plugins \
            -c pyproject.toml \
            -f sarif -o "$ARTIFACT_DIR/bandit.sarif" \
            || EXIT_CODE=1
        print_success "bandit done"
    else
        print_warning "bandit not found — skipping (pip install 'bandit[toml]')"
    fi
}

run_semgrep() {
    print_info "running semgrep"
    if [[ -n "$COMPOSE_CMD" ]]; then
        $COMPOSE_CMD -f docker-compose.yml -f docker-compose.quality.yml \
            --profile run-once run --rm semgrep || EXIT_CODE=1
        cp -f artifacts/scans/semgrep.sarif "$ARTIFACT_DIR/" 2>/dev/null || true
        print_success "semgrep done"
    elif command -v semgrep >/dev/null 2>&1; then
        semgrep scan --config=auto --config=.semgrep.yml \
            --json -o "$ARTIFACT_DIR/semgrep.json" \
            || EXIT_CODE=1
        semgrep scan --config=auto --config=.semgrep.yml \
            --sarif -o "$ARTIFACT_DIR/semgrep.sarif" \
            || EXIT_CODE=1
        print_success "semgrep done"
    else
        print_warning "semgrep not found — skipping"
    fi
}

run_trivy() {
    print_info "running trivy"
    if [[ -n "$COMPOSE_CMD" ]]; then
        $COMPOSE_CMD -f docker-compose.yml -f docker-compose.quality.yml \
            --profile run-once run --rm trivy || EXIT_CODE=1
        cp -f artifacts/scans/trivy-fs.sarif "$ARTIFACT_DIR/" 2>/dev/null || true
        print_success "trivy done"
    elif command -v trivy >/dev/null 2>&1; then
        trivy fs --scanners vuln,secret,misconfig \
            --severity HIGH,CRITICAL \
            --format json \
            --output "$ARTIFACT_DIR/trivy.json" \
            . || EXIT_CODE=1
        trivy fs --scanners vuln,secret,misconfig \
            --severity HIGH,CRITICAL \
            --format sarif \
            --output "$ARTIFACT_DIR/trivy.sarif" \
            . || EXIT_CODE=1
        print_success "trivy done"
    else
        print_warning "trivy not found — skipping"
    fi
}

run_gitleaks() {
    print_info "running gitleaks"
    if [[ -n "$COMPOSE_CMD" ]]; then
        $COMPOSE_CMD -f docker-compose.yml -f docker-compose.quality.yml \
            --profile run-once run --rm gitleaks || EXIT_CODE=1
        cp -f artifacts/scans/gitleaks.sarif "$ARTIFACT_DIR/" 2>/dev/null || true
        print_success "gitleaks done"
    elif command -v gitleaks >/dev/null 2>&1; then
        gitleaks detect --source . \
            --report-format json \
            --report-path "$ARTIFACT_DIR/gitleaks.json" \
            --exit-code 0 \
            || EXIT_CODE=1
        gitleaks detect --source . \
            --report-format sarif \
            --report-path "$ARTIFACT_DIR/gitleaks.sarif" \
            --exit-code 0 \
            || EXIT_CODE=1
        print_success "gitleaks done"
    else
        print_warning "gitleaks not found — skipping"
    fi
}

run_pip_audit() {
    print_info "running pip-audit"
    if command -v pip-audit >/dev/null 2>&1; then
        for reqfile in download-proxy/requirements.txt tests/requirements.txt; do
            if [[ -f "$reqfile" ]]; then
                local_suffix="$(echo "$reqfile" | tr '/' '_' | sed 's/\.txt$//')"
                pip-audit -r "$reqfile" \
                    -f json -o "$ARTIFACT_DIR/pip-audit-${local_suffix}.json" \
                    || EXIT_CODE=1
                pip-audit -r "$reqfile" \
                    -f sarif -o "$ARTIFACT_DIR/pip-audit-${local_suffix}.sarif" \
                    || EXIT_CODE=1
            fi
        done
        print_success "pip-audit done"
    else
        print_warning "pip-audit not found — skipping (pip install pip-audit)"
    fi
}

for scanner in "${SCANNERS[@]}"; do
    case "$scanner" in
        bandit)     run_bandit ;;
        semgrep)    run_semgrep ;;
        trivy)      run_trivy ;;
        gitleaks)   run_gitleaks ;;
        pip-audit)  run_pip_audit ;;
        *)
            print_error "unknown scanner: $scanner"
            EXIT_CODE=2
            ;;
    esac
done

if (( EXIT_CODE != 0 )); then
    print_error "scan completed with findings. See $ARTIFACT_DIR"
else
    print_success "all scans clean"
fi
exit "$EXIT_CODE"
