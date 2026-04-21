# AGENTS.md

Compact instruction file for AI agents working in this repo.
For deeper narrative docs see `CLAUDE.md`, `docs/USER_MANUAL.md`, `docs/PLUGINS.md`.

## What This Project Is

qBittorrent enhancement: multi-tracker search, authenticated download proxy, and a Merge Search Service (FastAPI). **Not a Python package** — no installable distribution. Runtime is container-based. Config is unified in `pyproject.toml`.

## Critical Constraints

- **TDD mandatory**: RED → watch fail → GREEN → verify → commit
- **CI is manual — permanently**: `./ci.sh` only. Never add push/PR/schedule triggers to `.github/workflows/*.yml`. Only `workflow_dispatch` is acceptable.
- **Never commit `.env`** — tracker credentials live there
- **WebUI credentials `admin`/`admin` are hardcoded** — do not change
- **IPTorrents freeleech only** — automated tests must never download non-freeleech. Tagged `IPTorrents [free]`
- **No comments in merge service source** (`download-proxy/src/`) — project convention

## Architecture

Two-container setup via `docker-compose.yml` (`network_mode: host`):

| Container | Image | Ports |
|-----------|-------|-------|
| qbittorrent | `lscr.io/linuxserver/qbittorrent:latest` | 7185 |
| qbittorrent-proxy | `python:3.12-alpine` | 7186, 7187 |

- **7185** qBittorrent WebUI (container-internal)
- **7186** Download proxy → qBittorrent
- **7187** Merge Search Service (FastAPI + dashboard)
- **7188** webui-bridge (host process, not a container)

Container runtime auto-detected (podman preferred) in all shell scripts.

### Frontend (Angular 21)

`frontend/` is a separate Angular 21 dashboard (Vitest for unit tests). Distinct from the FastAPI Jinja2 dashboard on port 7187.

```bash
cd frontend && npm test               # Vitest unit tests
cd frontend && npx ng build            # Production build
```

## Key Commands

### Startup
```bash
./setup.sh                             # One-time: dirs, config, plugins, containers
./start.sh                             # Start containers (-p pull, -s status, -v verbose)
./start.sh -p && python3 webui-bridge.py  # Full start with bridge
./stop.sh                              # Stop (-r remove, --purge clean images)
```

### Testing
```bash
./ci.sh                                # Full CI: syntax + unit + integration + e2e + container health
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

### Lint + Typecheck
```bash
ruff check .                           # Lint (config in pyproject.toml)
ruff check --fix .
ruff format .
mypy download-proxy/src/               # Strict mypy (config in pyproject.toml)
```

### Sync code to container after edits
```bash
podman exec qbittorrent-proxy find /config/download-proxy -name __pycache__ -type d -exec rm -rf {} +
podman restart qbittorrent-proxy
```

For plugin edits: `./install-plugin.sh <name>` copies `plugins/X.py` → `config/qBittorrent/nova3/engines/X.py` (source of truth is `plugins/`). Direct edits to the engines dir get clobbered on next install.

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
| `tests/concurrency/` | Semaphore/concurrency | Nothing |
| `tests/memory/` | Memory leak (tracemalloc) | Nothing |
| `tests/observability/` | Prometheus metric assertions | Nothing |
| `tests/integration/` | Integration tests | Running containers or mocks |
| `tests/e2e/` | End-to-end pipeline | Running containers |
| `tests/fixtures/` | Shared live-service fixtures (`services.py`, `live_search.py`) | — |

Key fixtures in `tests/conftest.py`: `mock_qbittorrent_api`, `sample_search_result`, `sample_merged_result`, `qbittorrent_host/port/url`.
Live fixtures in `tests/fixtures/services.py`: `merge_service_live`, `qbittorrent_live`, `webui_bridge_live`, `all_services_live`.

### Unit test `sys.modules` isolation

`conftest.py` has an autouse fixture `_isolate_download_proxy_modules` that isolates `sys.modules` for tests under `tests/unit/` only (stub packages for `api`/`merge_service` would pollute other tests). Integration/e2e tests are excluded because they import real modules with live async references.

### pytest markers

Defined in `pyproject.toml`: `requires_credentials`, `requires_compose`, `slow`, `stress`, `security`, `contract`, `property`, `memory`, `chaos`, `observability`.

## Code Organization (high-signal only)

```
download-proxy/src/
  main.py                # Entry: starts proxy + FastAPI in threads
  api/                   # FastAPI app (routes, hooks, streaming, auth, scheduler)
  merge_service/         # Core: search orchestration, dedup, enrichment, validation
  config/__init__.py     # EnvConfig dataclass, env loading
  ui/templates/          # Jinja2 dashboard + theme.css

plugins/                 # 42 tracker plugins + support files (helpers.py, nova2.py, novaprinter.py)
  webui_compatible/      # WebUI variants for private trackers

frontend/                # Angular 21 dashboard (separate from FastAPI Jinja2 dashboard)
tests/                   # All tests (unit, contract, property, concurrency, memory, observability, integration, e2e)
scripts/                 # run-tests.sh, scan.sh, build-releases.sh, etc.
```

## Toolchain Config (all in `pyproject.toml`)

- **ruff**: target py312, line-length 120, select `E F W I UP B SIM RUF ASYNC S PT C4 TID`, ignore `E501 S101 S603 S607`
- **mypy**: strict, py312, excludes `plugins/` and `tests/`
- **pytest**: `--import-mode=importlib`, `--timeout=60`, `--strict-markers`, asyncio_mode=auto
- **coverage**: sources `download-proxy/src` and `plugins`, `fail_under=1` (baseline)
- **mutmut**: paths `download-proxy/src/`

## Environment Variables

Priority: shell env → `./.env` → `~/.qbit.env` → container env.

Key: `RUTRACKER_USERNAME/PASSWORD`, `KINOZAL_USERNAME/PASSWORD` (falls back to `IPTORRENTS_*`), `NNMCLUB_COOKIES`, `IPTORRENTS_USERNAME/PASSWORD`, `QBITTORRENT_DATA_DIR` (default `/mnt/DATA`), `MERGE_SERVICE_PORT` (7187), `PROXY_PORT` (7186), `BRIDGE_PORT` (7188).

## Plugin System

`plugins/` has 42 managed tracker plugins. Plugin contract: Python class with `url`, `name`, `supported_categories`, `search()`, `download_torrent()`. Output via `novaprinter.print()`. Installed to `config/qBittorrent/nova3/engines/`.

```bash
./install-plugin.sh --all              # Install all
./install-plugin.sh rutracker rutor    # Install specific
./install-plugin.sh --verify           # Verify
```

## Gotchas

- `run-all-tests.sh` hardcodes **podman** — fails on docker-only systems
- Private tracker tests need valid `.env` credentials; RuTracker may require browser-solved CAPTCHA (cookies expire)
- Kinozal credentials fall back to IPTorrents if unset
- NNMClub needs `NNMCLUB_COOKIES` in `.env` for live testing
- IPTorrents non-freeleech results never merge with other trackers; only `[free]` tagged ones merge
- `config/download-proxy/src/` is **gitignored** — do not commit copied source trees
- Plugin source of truth is `plugins/X.py`, not `config/qBittorrent/nova3/engines/X.py`
- `webui-bridge.py` runs on port **7188** (not 7186)
- Merge service tests live in `./tests/`, not `download-proxy/tests/`
- Proxy container runs `start-proxy.sh` which installs deps from `requirements.txt` at startup (including Levenshtein)
- Hooks file is at `/config/download-proxy/hooks.json` inside container

## Commit Style

Format: `<type>: <subject>` where type is `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`. Branch naming: `feature/your-feature-name`.
