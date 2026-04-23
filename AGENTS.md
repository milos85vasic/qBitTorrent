# AGENTS.md

Compact instruction file for AI agents working in this repo.
For deeper narrative docs see `CLAUDE.md`, `docs/USER_MANUAL.md`, `docs/PLUGINS.md`.

## What This Project Is

qBittorrent enhancement: multi-tracker search, authenticated download proxy, and a Merge Search Service. **Not a Python package** -- no installable distribution. Runtime is container-based. Config is unified in `pyproject.toml`. A Go/Gin backend is available as an opt-in replacement (`--profile go`).

The project provides:
- **Merge Search Service** (FastAPI on `:7187`) -- fans out searches across 40+ public and private trackers, deduplicates and enriches results, streams real-time updates via SSE.
- **Download Proxy** (Python HTTP server on `:7186`) -- proxies qBittorrent WebUI and handles authenticated downloads for private trackers.
- **WebUI Bridge** (Python HTTP server on `:7188`) -- host process that bridges the qBittorrent WebUI with private-tracker authentication (RuTracker, Kinozal, NNM-Club, IPTorrents).
- **Angular 21 Dashboard** -- standalone SPA frontend served from the merge service, distinct from the FastAPI Jinja2 dashboard.

## Technology Stack

| Layer | Technology | Version / Notes |
|-------|-----------|-----------------|
| Python runtime | CPython | >=3.12 (target 3.12, CI also tests 3.13) |
| Python web framework | FastAPI + uvicorn | Async handlers, SSE streaming |
| Go runtime | Go | 1.26.2 |
| Go web framework | Gin | v1.12.0 |
| Frontend framework | Angular | 21.x (signals-based, standalone components) |
| Frontend test runner | Vitest | Via `@angular/build` / `ng test` |
| Frontend package manager | npm | 10.9.3 (locked in `packageManager`) |
| Container runtime | Podman (preferred) or Docker | Auto-detected in all shell scripts |
| Orchestration | docker-compose / podman compose | `network_mode: host` |
| qBittorrent image | `lscr.io/linuxserver/qbittorrent:latest` | Internal WebUI on `:7185` |

Key Python runtime dependencies (`download-proxy/requirements.txt`):
`fastapi`, `uvicorn`, `aiohttp`, `pydantic`, `Levenshtein`, `cachetools`, `filelock`, `tenacity`, `pybreaker`, `requests`, `urllib3`.

Key test dependencies (`tests/requirements.txt`):
`pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-timeout`, `pytest-randomly`, `pytest-xdist`, `pytest-docker`, `pytest-benchmark`, `hypothesis`, `responses`, `respx`, `freezegun`, `schemathesis`, `playwright`, `locust`, `ruff`, `mypy`, `bandit`, `pip-audit`, `mutmut`.

## Architecture

Two-container setup via `docker-compose.yml` (`network_mode: host`), with an optional Go backend and a host-level bridge process:

| Service | Container / Process | Image / Binary | Ports | Notes |
|---------|---------------------|----------------|-------|-------|
| qBittorrent | `qbittorrent` | `lscr.io/linuxserver/qbittorrent:latest` | 7185 | Internal WebUI; hardcoded credentials `admin`/`admin` |
| Download proxy + Merge service | `qbittorrent-proxy` | `python:3.12-alpine` | 7186, 7187 | Python multi-threaded entrypoint (`download-proxy/src/main.py`) |
| Go backend | `qbittorrent-proxy-go` | Built from `qBitTorrent-go/Dockerfile` | 7186, 7187, 7188 | Opt-in via `--profile go`; replaces Python proxy |
| WebUI bridge | Host process | `python3 webui-bridge.py` | 7188 | Not a container; bridges private-tracker auth |

Port map:
- **7185** -- qBittorrent WebUI (container-internal)
- **7186** -- Download proxy -> qBittorrent
- **7187** -- Merge Search Service (FastAPI + Angular SPA + Jinja2 dashboard)
- **7188** -- webui-bridge (private-tracker downloads)

Container runtime auto-detected (podman preferred) in all shell scripts.

### Python entrypoint (`download-proxy/src/main.py`)

Starts two daemon threads:
1. **Original proxy** -- imports and runs `download_proxy.py` (from the engines dir) for legacy proxy support on `:7186`.
2. **FastAPI server** -- runs `api:app` via uvicorn on `:7187`.

Signal handlers for `SIGTERM`/`SIGINT` trigger a graceful shutdown via `threading.Event`.

### Go backend (`qBitTorrent-go/`)

- `cmd/qbittorrent-proxy/` -- main API binary serving `:7187` (and `:7186` proxy, `:7188` bridge).
- `cmd/webui-bridge/` -- bridge binary.
- `internal/api/` -- HTTP handlers (health, search, hooks, download, scheduler, theme).
- `internal/service/` -- Merge search orchestrator + SSE broker.
- `internal/client/` -- qBittorrent Web API client (auth, search, torrents).
- `internal/models/` -- Data types (auth, hook, scheduler, search, torrent, theme).
- `internal/config/` -- Env config loading (`godotenv`).
- `internal/middleware/` -- CORS + zerolog request logging.
- `Dockerfile` -- multi-stage build.
- `scripts/build.sh` -- local build script.

### Frontend (`frontend/`)

Angular 21 standalone application. Uses signals, RxJS, Angular CDK. Vitest for unit tests. Prettier for formatting. Built with `npx ng build` and served from the merge service.

## Code Organization

```
download-proxy/src/
  main.py                # Entry: starts proxy + FastAPI in threads
  api/
    __init__.py          # FastAPI app factory + middleware + lifespan
    routes.py            # REST endpoints (search, download, auth, theme, health)
    streaming.py         # SSE result streaming
    hooks.py             # Hook registration / invocation
    auth.py              # Auth state + credential management
    scheduler.py         # Scheduled search API
    theme_state.py       # Cross-app theme injection state
  merge_service/
    __init__.py          # Package init
    search.py            # Search orchestration + tracker parsing
    deduplicator.py      # Result deduplication logic
    enricher.py          # Metadata enrichment (OMDb, TMDb, etc.)
    validator.py         # Result validation
    scheduler.py         # Scheduled search engine
    hooks.py             # Merge-service hook firing
    retry.py             # Retry helpers
  config/
    __init__.py          # EnvConfig dataclass, env loading
    log_filter.py        # CredentialScrubber for logs
  ui/
    templates/           # Jinja2 dashboard + theme.css

qBitTorrent-go/          # Go/Gin backend (opt-in replacement)
  cmd/
    qbittorrent-proxy/   # Main API binary (port 7187)
    webui-bridge/        # Bridge binary (port 7188)
  internal/
    api/                 # HTTP handlers
    service/             # Merge search orchestrator + SSE broker
    client/              # qBittorrent Web API client
    models/              # Data types
    config/              # Env config
    middleware/          # CORS + logging
  Dockerfile
  scripts/build.sh

plugins/                 # Tracker plugins + support files
  *.py                   # Core plugins (eztv, jackett, limetorrents, piratebay, ...)
  community/             # Additional community plugins
  webui_compatible/      # WebUI variants for private trackers
  helpers.py             # Shared plugin utilities
  nova2.py               # Nova search interface
  novaprinter.py         # Plugin output formatter
  socks.py               # SOCKS proxy support

tests/                   # All tests (NOT in download-proxy/tests/)
  unit/                  # Unit tests (heavily mocked)
    merge_service/       # Core logic tests
    api_layer/           # API layer tests
  contract/              # API contract tests (OpenAPI, cross-app theme)
  property/              # Hypothesis property-based tests
  concurrency/           # Semaphore / concurrency tests
  memory/                # Memory leak tests (tracemalloc)
  observability/         # Prometheus metric assertions
  benchmark/             # Performance benchmarks
  chaos/                 # Fault-injection tests
  load/                  # Load tests
  performance/           # Performance regression tests
  stress/                # High-load stress tests
  security/              # Security-focused tests
  integration/           # Integration tests (needs running containers or mocks)
  e2e/                   # End-to-end pipeline (needs running containers)
  docs/                  # Documentation integrity (broken links)
  fixtures/              # Shared live-service fixtures
  conftest.py            # Global pytest config + fixtures

scripts/                 # Build / scan / test orchestration scripts
  run-tests.sh           # Full suite with coverage (hermetic | live | all)
  scan.sh                # Security + quality scanner orchestration
  build-releases.sh      # Release artefact builder
  audit-plugins.sh       # Plugin audit
  freeze-openapi.sh      # OpenAPI spec freeze
  helixqa.sh             # HelixQA runner
  opencode-helixqa.sh    # OpenCode HelixQA runner
  add-submodules.sh      # Submodule setup

frontend/                # Angular 21 dashboard
  src/                   # TypeScript sources
  public/                # Static assets (PWA icons, manifest)
  package.json
  angular.json
  .prettierrc
```

## Critical Constraints

- **TDD mandatory**: RED -> watch fail -> GREEN -> verify -> commit
- **Never commit `.env`** -- tracker credentials live there
- **WebUI credentials `admin`/`admin` are hardcoded** -- do not change
- **IPTorrents freeleech only** -- automated tests must never download non-freeleech. Tagged `IPTorrents [free]`
- **No comments in merge service source** (`download-proxy/src/`) -- project convention
- **CI is manual via `./ci.sh`** -- the canonical local pipeline. GitHub Actions workflows exist for push/PR gates (syntax, unit, integration, nightly, security, docs), but the project's ground-truth validation script is `./ci.sh`.

## Key Commands

### Startup
```bash
./setup.sh                             # One-time: dirs, config, plugins, containers
./start.sh                             # Start containers (-p pull, -s status, -v verbose)
./start.sh -p && python3 webui-bridge.py  # Full start with bridge
./stop.sh                              # Stop (-r remove, --purge clean images)
```

### Go Backend (opt-in)
```bash
podman compose --profile go up -d      # Start Go backend instead of Python
cd qBitTorrent-go && ./scripts/build.sh   # Build Go binaries locally
cd qBitTorrent-go && go test -race ./...  # Go tests with race detection
cd qBitTorrent-go && go vet ./...         # Go static analysis
```

### Testing
```bash
./ci.sh                                # Full local CI: syntax + unit + integration + e2e + container health
./ci.sh --quick                        # Syntax + unit only
./ci.sh --tests-only                   # Skip syntax, run tests
scripts/run-tests.sh                   # Full suite with coverage (hermetic | live | all)
scripts/run-tests.sh hermetic          # Only hermetic suites (fast)
```

### Single test / subset
```bash
python3 -m pytest tests/unit/test_freeleech.py -v --import-mode=importlib
python3 -m pytest tests/unit/merge_service/ -v --import-mode=importlib
python3 -m pytest tests/unit/ -k "search" -v --import-mode=importlib
```

### Go Backend Tests
```bash
cd qBitTorrent-go && go test -race -count=1 ./...  # Full suite with race detection
cd qBitTorrent-go && go test ./internal/api/ -v     # Single package
cd qBitTorrent-go && go vet ./...                   # Static analysis
```

### Lint + Typecheck
```bash
ruff check .                           # Lint (config in pyproject.toml)
ruff check --fix .
ruff format .
mypy download-proxy/src/               # Strict mypy (config in pyproject.toml)
```

### Frontend
```bash
cd frontend && npm test                # Vitest unit tests
cd frontend && npx ng build            # Production build
cd frontend && npx vitest run          # Non-interactive Vitest
```

### Sync code to container after edits
```bash
podman exec qbittorrent-proxy find /config/download-proxy -name __pycache__ -type d -exec rm -rf {} +
podman restart qbittorrent-proxy
```

For plugin edits: `./install-plugin.sh <name>` copies `plugins/X.py` -> `config/qBittorrent/nova3/engines/X.py` (source of truth is `plugins/`). Direct edits to the engines dir get clobbered on next install.

For compose/image changes: `podman compose down && podman compose up -d` (full recreate).

**Always verify** after restart: curl the endpoint or `podman exec ... cat /config/...` to confirm running code matches committed code.

## Test Layout

Tests live in `./tests/`, NOT in `download-proxy/tests/`.

| Directory | What | Requires |
|-----------|------|----------|
| `tests/unit/` | Unit tests (heavily mocked) | Nothing |
| `tests/unit/merge_service/` | Core logic: dedup, search, hooks, validator, enricher, scheduler | Nothing |
| `tests/unit/api_layer/` | API layer unit tests | Nothing |
| `tests/contract/` | API contract tests (OpenAPI, cross-app theme) | Nothing |
| `tests/property/` | Hypothesis property-based | Nothing |
| `tests/concurrency/` | Semaphore / concurrency | Nothing |
| `tests/memory/` | Memory leak (tracemalloc) | Nothing |
| `tests/observability/` | Prometheus metric assertions | Nothing |
| `tests/benchmark/` | Performance benchmarks | Nothing |
| `tests/chaos/` | Fault-injection / chaos | Nothing |
| `tests/security/` | Security-focused tests | Running containers |
| `tests/integration/` | Integration tests | Running containers or mocks |
| `tests/e2e/` | End-to-end pipeline | Running containers |
| `tests/fixtures/` | Shared live-service fixtures (`services.py`, `live_search.py`) | -- |
| `tests/docs/` | Documentation integrity (broken links) | Nothing |

Key fixtures in `tests/conftest.py`: `mock_qbittorrent_api`, `sample_search_result`, `sample_merged_result`, `qbittorrent_host/port/url`.
Live fixtures in `tests/fixtures/services.py`: `merge_service_live`, `qbittorrent_live`, `webui_bridge_live`, `all_services_live`.

### Unit test `sys.modules` isolation

`conftest.py` has an autouse fixture `_isolate_download_proxy_modules` that isolates `sys.modules` for tests under `tests/unit/` only (stub packages for `api`/`merge_service` would pollute other tests). Integration/e2e tests are excluded because they import real modules with live async references.

### pytest markers

Defined in `pyproject.toml`:
- `requires_credentials` -- needs real tracker credentials (`.env`)
- `requires_compose` -- needs the full docker-compose stack up
- `slow` -- takes longer than 1s (opt-in)
- `stress` -- high-load stress test (opt-in)
- `security` -- security-focused test
- `contract` -- API contract test (schemathesis / openapi)
- `property` -- property-based (hypothesis) test
- `memory` -- memory-leak / tracemalloc test
- `chaos` -- chaos / fault-injection test
- `observability` -- scrapes prometheus / metrics

## Toolchain Config (all in `pyproject.toml`)

- **ruff**: target py312, line-length 120, select `E F W I UP B SIM RUF ASYNC S PT C4 TID`, ignore `E501 S101 S603 S607`
- **mypy**: strict, py312, excludes `plugins/` and `tests/` and `download-proxy/src/ui/`
- **pytest**: `--import-mode=importlib`, `--timeout=60`, `--strict-markers`, asyncio_mode=auto, asyncio_default_test_loop_scope=class
- **coverage**: sources `download-proxy/src` and `plugins`, `fail_under=49` (raised from 1% baseline, see `docs/COVERAGE_BASELINE.md`)
- **mutmut**: paths `download-proxy/src/`

### Coverage baseline

Total coverage is **49%** (5,683 statements, 2,708 missing). The `fail_under` gate in `pyproject.toml` is set to `49`. When raising the gate, update `docs/COVERAGE_BASELINE.md` simultaneously. Unit tests only are used for the baseline; integration/e2e tests require running containers and are not included.

## Quality Stack (opt-in)

`docker-compose.quality.yml` adds scanners and observability -- never started by `./start.sh`.

```bash
podman compose -f docker-compose.yml -f docker-compose.quality.yml --profile quality up -d
scripts/scan.sh --all
```

| Tool | Config File | Purpose |
|------|-------------|---------|
| SonarQube | `sonar-project.properties` | Code quality + coverage |
| Snyk | `.snyk` | Dependency vulnerability scan |
| Semgrep | `.semgrep.yml` | Static analysis rules |
| Trivy | `.trivyignore`, `.trivyignore.yaml` | Container image scanning |
| Gitleaks | `.gitleaks.toml` | Secret detection |
| Prometheus | `observability/prometheus.yml` | Metrics collection |
| Grafana | `observability/dashboards/` | Dashboard visualization |

All scanner reports land in `artifacts/scans/<timestamp>/` as SARIF. Mandatory waiver format: Finding ID / reason / expiry.

## Environment Variables

Priority: shell env -> `./.env` -> `~/.qbit.env` -> container env.

Key variables:
- `RUTRACKER_USERNAME/PASSWORD` -- RuTracker credentials
- `KINOZAL_USERNAME/PASSWORD` -- Kinozal credentials (falls back to `IPTORRENTS_*` if unset)
- `NNMCLUB_COOKIES` -- NNM-Club cookie-based auth
- `NNMCLUB_USERNAME/PASSWORD` -- NNM-Club fallback credentials
- `IPTORRENTS_USERNAME/PASSWORD` -- IPTorrents credentials
- `QBITTORRENT_DATA_DIR` -- host download path (default `/mnt/DATA`)
- `MERGE_SERVICE_PORT` -- default `7187`
- `MERGE_SERVICE_HOST` -- default `0.0.0.0`
- `PROXY_PORT` -- default `7186`
- `BRIDGE_PORT` -- default `7188`
- `ALLOWED_ORIGINS` -- CORS origins, comma-separated
- `MAX_CONCURRENT_SEARCHES` -- default `5`
- `MAX_CONCURRENT_TRACKERS` -- default `10`
- `PUBLIC_TRACKER_DEADLINE_SECONDS` -- default `15`
- `DISABLE_THEME_INJECTION` -- set to `1` to disable cross-app dark mode
- `LOG_LEVEL` -- default `INFO`
- `OMDB_API_KEY`, `TMDB_API_KEY`, `TVDB_API_KEY` -- metadata enrichment
- `ANILIST_CLIENT_ID` -- anime metadata
- `JACKETT_API_KEY` -- public tracker uplift
- `SNYK_TOKEN`, `SONAR_TOKEN` -- scanner tokens (opt-in)

## Plugin System

`plugins/` contains core tracker plugins, community plugins, and webUI-compatible variants.

Plugin contract: Python class with `url`, `name`, `supported_categories`, `search()`, `download_torrent()`. Output via `novaprinter.print()`.

Installed to `config/qBittorrent/nova3/engines/`.

```bash
./install-plugin.sh --all              # Install all
./install-plugin.sh rutracker rutor    # Install specific
./install-plugin.sh --verify           # Verify installation
```

Support files (`plugins/`):
- `helpers.py` -- shared utilities for plugins
- `nova2.py` -- nova search interface
- `novaprinter.py` -- output formatter
- `socks.py` -- SOCKS proxy support

## Gotchas

- Private tracker tests need valid `.env` credentials; RuTracker may require browser-solved CAPTCHA (cookies expire)
- Kinozal credentials fall back to IPTorrents if unset
- NNMClub needs `NNMCLUB_COOKIES` in `.env` for live testing
- IPTorrents non-freeleech results never merge with other trackers; only `[free]` tagged ones merge
- `config/download-proxy/src/` is **gitignored** -- do not commit copied source trees
- Plugin source of truth is `plugins/X.py`, not `config/qBittorrent/nova3/engines/X.py`
- `webui-bridge.py` runs on port **7188** (not 7186)
- Merge service tests live in `./tests/`, not `download-proxy/tests/`
- Proxy container runs `start-proxy.sh` which installs deps from `requirements.txt` at startup (including Levenshtein)
- Hooks file is at `/config/download-proxy/hooks.json` inside container
- Go backend is opt-in via `--profile go` -- does not replace Python by default
- Go `qbittorrent-proxy` binary serves on 7187 (same as Python merge service); both cannot run simultaneously
- The `download-proxy` container mounts `./download-proxy` to `/config/download-proxy` so live edits on the host are reflected inside the container without rebuild

## Commit Style

Format: `<type>: <subject>` where type is `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`. Branch naming: `feature/your-feature-name`.
