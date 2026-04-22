# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

For deeper reference (technology stack, per-test-file mapping, full gotchas), see `AGENTS.md`.

## Critical Constraints

- **TDD is MANDATORY for all bug fixes and features**:
  - Write failing test first (RED)
  - Watch it fail
  - Write minimal code to pass (GREEN)
  - Verify tests pass
  - Then commit

- **Pick the right restart level** (verified 2026-04-19 against the real
  `docker-compose.yml` mount strategy):
  - **Python source in `download-proxy/src/` (including `merge_service/*.py`)**
    — bind-mounted via `./download-proxy:/config/download-proxy`. Just
    `podman exec qbittorrent-proxy find /config/download-proxy -name __pycache__ -type d -exec rm -rf {} +`
    then `podman restart qbittorrent-proxy`.
  - **Plugin files in `plugins/`** — also bind-mounted through
    `./config:/config`. After editing, `./install-plugin.sh` copies
    them into `config/qBittorrent/nova3/engines/` (that path IS the
    host side of the mount) and `podman restart qbittorrent-proxy`
    picks them up. A direct edit to `config/qBittorrent/nova3/engines/X.py`
    works for a one-shot try but will be clobbered on the next install
    — source of truth is `plugins/X.py`.
  - **`docker-compose.yml`, `start-proxy.sh`, env vars, base image** —
    `podman compose down && podman compose up -d` (full recreate). A
    `podman build` is only needed when `python:3.12-alpine` itself
    needs to change.
  - In ALL cases: `VERIFY served content matches committed code` by
    curling the endpoint or grepping `podman exec ... cat /config/...`
    — this is the cache-bust guard.
  See `docs/MERGE_SEARCH_DIAGNOSTICS.md` §"Rebuild / restart contract"
  for the full table.

- **WebUI credentials `admin`/`admin` are hardcoded** — do not change.
- **Never commit `.env`** — it contains tracker credentials.
- **Never commit `.ruff_cache/`** — add to `.gitignore`.
- **CI IS MANUAL — permanent.** `./ci.sh` is the only path. Do NOT
  add push / pull-request / schedule triggers to
  `.github/workflows/*.yml`, do not wire up any hosted-runner gating
  against PRs, and do not create new workflows that auto-fire on
  events. The owner has explicitly directed this multiple times.
  `workflow_dispatch` is the only acceptable trigger. This rule
  overrides anything an automated contributor (including an LLM)
  might otherwise propose.
- **Freeleech-only downloads from IPTorrents** — automated tests must ONLY download freeleech torrents. Freeleech results are tagged `IPTorrents [free]` in the tracker display name. Non-freeleech downloads cost ratio and must never be automated.

## Architecture

Two-container setup via `docker-compose.yml` (Python), with an optional Go backend:

- **qbittorrent** (lscr.io/linuxserver/qbittorrent:latest) — port **7185**
- **qbittorrent-proxy** (python:3.12-alpine) — ports **7186** (proxy), **7187** (merge service)
- **qbittorrent-proxy-go** (Go/Gin, opt-in via `--profile go`) — ports **7187** (merge service), **7188** (bridge)

`webui-bridge.py` is a host process on port **7188** for private tracker downloads. The Go `webui-bridge` binary replaces this when using the Go profile.

`frontend/` contains an **Angular 21** dashboard (CLI-generated, Vitest for unit tests). Separate from the FastAPI dashboard served by the merge service on port 7187.

Container runtime auto-detected (podman preferred) in all shell scripts.

### Port Map

| Port | Service | Access |
|------|---------|--------|
| 7185 | qBittorrent WebUI (container-internal) | proxied via 7186 |
| 7186 | Download proxy → qBittorrent WebUI | `http://localhost:7186` |
| 7187 | Merge Search Service (FastAPI or Go/Gin) | `http://localhost:7187/` |
| 7188 | webui-bridge (host process or Go binary) | manual start |

## Key Commands

### Startup
```bash
./setup.sh                                         # One-time setup
./start.sh                                         # Start containers (-p pull, -s status, -v verbose)
./start.sh -p && python3 webui-bridge.py           # Full start with bridge
./stop.sh                                          # Stop (-r remove, --purge clean images)
```

### Go Backend (opt-in)
```bash
podman compose --profile go up -d                  # Start Go backend instead of Python
cd qBitTorrent-go && ./scripts/build.sh            # Build Go binaries locally
cd qBitTorrent-go && go test -race ./...           # Run Go tests with race detection
```

### Testing
```bash
./ci.sh                                            # Manual CI: syntax + unit + integration + e2e + container health
./ci.sh --quick                                    # Fast check (syntax + unit only)
./run-all-tests.sh                                 # Full suite (hardcoded to podman)
./test.sh                                          # Quick validation (--all, --quick, --plugin, --full)
python3 -m py_compile plugins/*.py                 # Syntax check plugins
bash -n start.sh stop.sh test.sh install-plugin.sh # Bash syntax check
```

### Merge Service Tests (331 tests total, live in `./tests/` not `download-proxy/tests/`)
```bash
python3 -m pytest tests/unit/ -v --import-mode=importlib              # Unit tests
python3 -m pytest tests/unit/merge_service/ -v --import-mode=importlib # Merge service only
python3 -m pytest tests/integration/ -v --import-mode=importlib        # Integration tests
python3 -m pytest tests/unit/ -k "search" -v --import-mode=importlib   # Filter by keyword
```

### Linting
```bash
ruff check .                                       # Lint (config in pyproject.toml: py312, line 120, E/F/W/I/UP/B/SIM/RUF/ASYNC/S/PT/C4/TID)
ruff check --fix .                                 # Auto-fix
ruff format .                                      # Format
```

### Frontend (Angular 19)
```bash
cd frontend && ng serve                            # Dev server on :4200
cd frontend && ng build                            # Production build to dist/
cd frontend && ng test                             # Unit tests (Vitest)
```

### Sync to Container
```bash
podman cp download-proxy/src/ qbittorrent-proxy:/app/src/
```

## Merge Search Service

Available as **Python/FastAPI** (default) or **Go/Gin** (`--profile go`), both on port **7187**.

- Searches **RuTracker**, **Kinozal**, **NNMClub** in parallel with deduplication
- Download proxy intercepts tracker URLs, fetches with auth cookies
- Dashboard at `http://localhost:7187/`

### Python (FastAPI)
Key files:
- `download-proxy/src/api/__init__.py` — FastAPI app setup
- `download-proxy/src/api/routes.py` — REST endpoints
- `download-proxy/src/merge_service/search.py` — search orchestration
- `download-proxy/src/merge_service/deduplicator.py` — result dedup
- `download-proxy/src/merge_service/enricher.py` — quality detection

### Go (Gin)
Key files (in `qBitTorrent-go/`):
- `cmd/qbittorrent-proxy/main.go` — main binary entry point
- `cmd/webui-bridge/main.go` — bridge binary entry point
- `internal/api/` — all HTTP handlers
- `internal/service/merge_search.go` — search orchestrator with goroutines
- `internal/service/sse_broker.go` — SSE pub/sub broker
- `internal/client/` — qBittorrent Web API client
- `internal/models/` — data types
- `internal/config/` — env config loading
- `internal/middleware/` — CORS and logging
- Migration spec: `docs/migration/Migration_Python_Codebase_To_Go.md`

## Plugin System

`plugins/` has **42 managed plugins**. `install-plugin.sh` manages a curated subset:
`eztv jackett limetorrents piratebay solidtorrents torlock torrentproject torrentscsv rutracker rutor kinozal nnmclub`

Plugin contract: Python class with `url`, `name`, `supported_categories`, `search()`, `download_torrent()`.
Installed to `config/qBittorrent/nova3/engines/` inside container.

## Environment Variables

Priority: shell env → `./.env` → `~/.qbit.env` → container env.

Key: `RUTRACKER_USERNAME/PASSWORD`, `KINOZAL_USERNAME/PASSWORD` (falls back to `IPTORRENTS_USERNAME/PASSWORD` if unset), `NNMCLUB_COOKIES`, `IPTORRENTS_USERNAME/PASSWORD`, `QBITTORRENT_DATA_DIR` (`/mnt/DATA`), `PUID/PGID` (`1000`), `MERGE_SERVICE_PORT` (`7187`), `PROXY_PORT` (`7186`), `BRIDGE_PORT` (`7188`).

## Code Conventions

- **Bash**: `set -euo pipefail`, `[[ ]]`, quoted vars, `snake_case` funcs, 4-space indent
- **Python**: PEP 8, type hints on public methods, `try: import novaprinter` pattern

## Gotchas

- `run-all-tests.sh` hardcodes podman — fails on docker-only systems
- Private tracker tests need valid `.env` credentials + sometimes CAPTCHA (RuTracker cookies expire periodically)
- `config/download-proxy/src/` is gitignored — never commit copied source trees
- Empty root files (`CONFIG`, `SCRIPT`, `EOF`) may be referenced — don't remove
- `webui-bridge.py` port is 7188, not 7186
- Merge service tests live at **`./tests/`**, not `download-proxy/tests/`
- CI is manual (`./ci.sh`) — no auto-trigger on push/PR (`.github/workflows/test.yml` is `workflow_dispatch` only)
