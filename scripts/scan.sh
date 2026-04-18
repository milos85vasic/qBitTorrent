#!/usr/bin/env bash
# scripts/scan.sh — non-interactive wrapper around the quality compose
# stack (docker-compose.quality.yml). Runs scanners, writes SARIF/JSON
# reports to artifacts/scans/<timestamp>/, exits non-zero on failure.
#
# Strictly non-interactive: never prompts, never escalates privileges,
# never reads from stdin. If a required secret (SNYK_TOKEN, SONAR_TOKEN)
# is missing, that scanner is skipped with a WARNING and the script
# continues.
#
# Usage:
#   ./scripts/scan.sh --all                # run every scanner
#   ./scripts/scan.sh pip-audit bandit     # run named scanners only
#   ./scripts/scan.sh --help

set -euo pipefail

# ---------------------------------------------------------------------------
# Runtime detection (constitution IV — podman preferred over docker)
# ---------------------------------------------------------------------------
detect_container_runtime() {
    if command -v podman >/dev/null 2>&1; then
        CONTAINER_RUNTIME="podman"
    elif command -v docker >/dev/null 2>&1; then
        CONTAINER_RUNTIME="docker"
    else
        echo "ERROR: neither podman nor docker is installed" >&2
        exit 2
    fi

    if command -v podman-compose >/dev/null 2>&1 && [[ "$CONTAINER_RUNTIME" == "podman" ]]; then
        COMPOSE_CMD="podman-compose"
    elif $CONTAINER_RUNTIME compose version >/dev/null 2>&1; then
        COMPOSE_CMD="$CONTAINER_RUNTIME compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    else
        echo "ERROR: no compose command available" >&2
        exit 2
    fi
}

# ---------------------------------------------------------------------------
# Colour-print helpers (constitution VII — operational simplicity)
# ---------------------------------------------------------------------------
print_info()    { printf '\033[0;34m[INFO]\033[0m %s\n' "$*"; }
print_success() { printf '\033[0;32m[ OK ]\033[0m %s\n' "$*"; }
print_warning() { printf '\033[0;33m[WARN]\033[0m %s\n' "$*"; }
print_error()   { printf '\033[0;31m[FAIL]\033[0m %s\n' "$*" >&2; }

usage() {
    cat <<'USAGE'
Usage:
  ./scripts/scan.sh [--all] [--help] [SCANNER ...]

Scanners (invoked in the listed order when --all):
  pip-audit     Python runtime-dep CVE scan (host)
  bandit        Python SAST (host)
  ruff          Ruff lint + new ASYNC/S rules (host)
  semgrep       SAST rules (compose; also uses local .semgrep.yml)
  trivy         Filesystem CVE + misconfig + secret scan (compose)
  gitleaks      Secret scan via git history (compose)
  snyk          Dep + SAST (compose; needs SNYK_TOKEN)
  sonarqube     Quality gate upload (compose; needs SONAR_TOKEN + SONAR_HOST_URL)

Environment variables:
  SNYK_TOKEN             skipped if unset
  SONAR_TOKEN            skipped if unset
  SONAR_HOST_URL         default: http://localhost:9000 (if sonarqube profile up)
  SCAN_ARTIFACTS_DIR     default: artifacts/scans/<UTC timestamp>/

Exit codes:
  0 on full pass, non-zero if any scanner reports high/critical findings.
USAGE
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
RUN_ALL=0
REQUESTED=()
while (( $# )); do
    case "$1" in
        --all) RUN_ALL=1; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; break ;;
        -*) print_error "unknown flag: $1"; usage; exit 2 ;;
        *)  REQUESTED+=("$1"); shift ;;
    esac
done

ALL_SCANNERS=(pip-audit bandit ruff semgrep trivy gitleaks snyk sonarqube)
if (( RUN_ALL )) || (( ${#REQUESTED[@]} == 0 )); then
    REQUESTED=("${ALL_SCANNERS[@]}")
fi

# ---------------------------------------------------------------------------
# Artefact directory
# ---------------------------------------------------------------------------
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
ARTIFACT_DIR="${SCAN_ARTIFACTS_DIR:-artifacts/scans/$timestamp}"
mkdir -p "$ARTIFACT_DIR"
print_info "writing reports to $ARTIFACT_DIR"

detect_container_runtime
print_info "container runtime: $CONTAINER_RUNTIME  ($COMPOSE_CMD)"

exit_code=0

run_scanner() {
    local name="$1"
    print_info "running $name"
    case "$name" in
        pip-audit)
            if command -v pip-audit >/dev/null 2>&1; then
                pip-audit -r download-proxy/requirements.txt \
                    -f sarif -o "$ARTIFACT_DIR/pip-audit.sarif" || exit_code=1
                pip-audit -r tests/requirements.txt \
                    -f sarif -o "$ARTIFACT_DIR/pip-audit-tests.sarif" || exit_code=1
                print_success "pip-audit done"
            else
                print_warning "pip-audit not on PATH — skipping (install: pip install pip-audit)"
            fi
            ;;
        bandit)
            if command -v bandit >/dev/null 2>&1; then
                bandit -r download-proxy/src plugins \
                    -c pyproject.toml -f sarif -o "$ARTIFACT_DIR/bandit.sarif" \
                    || exit_code=1
                print_success "bandit done"
            else
                print_warning "bandit not on PATH — skipping (install: pip install 'bandit[toml]')"
            fi
            ;;
        ruff)
            if command -v ruff >/dev/null 2>&1; then
                ruff check . --output-format=json > "$ARTIFACT_DIR/ruff.json" || exit_code=1
                print_success "ruff done"
            else
                print_warning "ruff not on PATH — skipping"
            fi
            ;;
        semgrep)
            $COMPOSE_CMD -f docker-compose.yml -f docker-compose.quality.yml \
                --profile run-once run --rm semgrep || exit_code=1
            cp -f artifacts/scans/semgrep.sarif "$ARTIFACT_DIR/" 2>/dev/null || true
            print_success "semgrep done"
            ;;
        trivy)
            $COMPOSE_CMD -f docker-compose.yml -f docker-compose.quality.yml \
                --profile run-once run --rm trivy || exit_code=1
            cp -f artifacts/scans/trivy-fs.sarif "$ARTIFACT_DIR/" 2>/dev/null || true
            print_success "trivy done"
            ;;
        gitleaks)
            $COMPOSE_CMD -f docker-compose.yml -f docker-compose.quality.yml \
                --profile run-once run --rm gitleaks || exit_code=1
            cp -f artifacts/scans/gitleaks.sarif "$ARTIFACT_DIR/" 2>/dev/null || true
            print_success "gitleaks done"
            ;;
        snyk)
            if [[ -z "${SNYK_TOKEN:-}" ]]; then
                print_warning "SNYK_TOKEN unset — skipping snyk"
                return 0
            fi
            SNYK_TOKEN="$SNYK_TOKEN" $COMPOSE_CMD -f docker-compose.yml -f docker-compose.quality.yml \
                --profile run-once run --rm snyk || exit_code=1
            cp -f artifacts/scans/snyk*.sarif "$ARTIFACT_DIR/" 2>/dev/null || true
            print_success "snyk done"
            ;;
        sonarqube)
            if [[ -z "${SONAR_TOKEN:-}" ]]; then
                print_warning "SONAR_TOKEN unset — skipping sonarqube upload"
                return 0
            fi
            if command -v sonar-scanner >/dev/null 2>&1; then
                sonar-scanner \
                    -Dsonar.login="$SONAR_TOKEN" \
                    -Dsonar.host.url="${SONAR_HOST_URL:-http://localhost:9000}" \
                    || exit_code=1
                print_success "sonarqube upload done"
            else
                print_warning "sonar-scanner binary not installed (https://docs.sonarsource.com/sonarqube/latest/analyzing-source-code/scanners/sonarscanner/)"
            fi
            ;;
        *)
            print_error "unknown scanner: $name"
            exit_code=2
            ;;
    esac
}

for s in "${REQUESTED[@]}"; do
    run_scanner "$s"
done

if (( exit_code != 0 )); then
    print_error "scan completed with findings (exit $exit_code). See $ARTIFACT_DIR"
else
    print_success "all scans clean"
fi
exit "$exit_code"
