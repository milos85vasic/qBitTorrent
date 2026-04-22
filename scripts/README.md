# scripts/

Operational and CI scripts. All scripts auto-detect container runtime (podman preferred).

## Scripts

| Script | Purpose |
|--------|---------|
| `run-tests.sh` | Full test suite with coverage. Args: `hermetic` (fast, no services), `live` (needs containers), `all` |
| `scan.sh` | Security scanner orchestrator. Runs `pip-audit`, `bandit`, `ruff`, `snyk`, `semgrep`, `trivy`, `gitleaks`. Reports to `artifacts/scans/` as SARIF |
| `freeze-openapi.sh` | Exports FastAPI `/openapi.json` to `docs/api/openapi.json` for drift detection |
| `build-releases.sh` | Build release artifacts |
| `audit-plugins.sh` | Audit plugin matrix (canonical vs community) |
| `add-submodules.sh` | Add git submodules |
| `helixqa.sh` | Helix QA runner |
| `opencode-helixqa.sh` | OpenCode Helix QA runner |

## Usage

```bash
# Run full test suite
./scripts/run-tests.sh all

# Quick hermetic tests only
./scripts/run-tests.sh hermetic

# Run all security scanners
./scripts/scan.sh --all

# Freeze OpenAPI spec
./scripts/freeze-openapi.sh
```

## Conventions

- All scripts use `set -euo pipefail`.
- Non-interactive — no `sudo` or human input required.
- Container runtime auto-detected (podman > docker).
