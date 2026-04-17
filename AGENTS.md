# AGENTS.md

> **Project**: qBitTorrent-Fixed (v3.0.0)
> **Language**: English (all code, docs, and comments)
> **License**: Apache 2.0

## Project Overview

This is a **qBittorrent enhancement project** that adds unified multi-tracker search, a download proxy with authenticated tracker support, and a Merge Search Service built with FastAPI. It consists of:

- **42 tracker plugins** (public, private, Russian, anime, specialized)
- **Merge Search Service** — FastAPI app that searches multiple trackers simultaneously, deduplicates results, enriches metadata, and streams results in real-time via SSE
- **Download proxy** — bridges qBittorrent WebUI with private trackers that require authentication
- **WebUI bridge** — host process that intercepts private tracker download requests and handles them with proper cookies/session auth

The project is **not a Python package** — there is no `pyproject.toml`, `setup.py`, or `setup.cfg`. Dependencies are managed via `requirements.txt` files, and the runtime is container-based.

---

## Critical Constraints

- **TDD is MANDATORY for all bug fixes and features**:
  1. Write failing test first (**RED**)
  2. Watch it fail
  3. Write minimal code to pass (**GREEN**)
  4. Verify tests pass
  5. Then commit
  6. See `tests/README.md` for detailed TDD workflow

- **WebUI credentials `admin`/`admin` are hardcoded** in `start.sh` config generation, `docker-compose.yml`, and multiple scripts. **Do not change them.**
- **Never commit `.env`** — it contains tracker credentials. `.env.example` is the template.
- **Freeleech-only downloads from IPTorrents** — all automated testing must ONLY download freeleech torrents. Freeleech results are tagged `IPTorrents [free]` in tracker display name. Non-freeleech IPTorrents downloads cost ratio and must NEVER be triggered by automation or tests.
- **No CI pipeline is auto-triggered**. `ci.sh` is manual-only. GitHub Actions workflow (`.github/workflows/test.yml`) is `workflow_dispatch` only — never runs on push/PR.

---

## Technology Stack

| Layer | Technology | Version/Notes |
|-------|-----------|---------------|
| Runtime | Python | 3.12 (container and host) |
| Web Framework | FastAPI | ≥0.110.0 |
| ASGI Server | uvicorn | ≥0.29.0 |
| HTTP Client | aiohttp, requests | ≥3.9.0, ≥2.31.0 |
| Validation | pydantic | ≥2.0.0 |
| String Similarity | Levenshtein | ≥0.21.0 |
| Containers | Docker or Podman | Auto-detected, Podman preferred |
| Compose | docker-compose or podman-compose | Auto-detected |
| qBittorrent | linuxserver/qbittorrent:latest | Port 7185 |
| Linter | ruff | Config in `ruff.toml` |
| Testing | pytest | With `responses`, `pytest-cov` |

### Key Configuration Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Two-service compose: qbittorrent + qbittorrent-proxy |
| `download-proxy/requirements.txt` | Runtime deps for proxy container |
| `tests/requirements.txt` | Test deps: pytest, requests, responses, pytest-cov |
| `ruff.toml` | Linter config: target py312, line-length 120, select E/F/W/I/UP/B/SIM/RUF |
| `.env.example` | Template for all environment variables (293 lines, extensively documented) |
| `.gitignore` | Excludes `.env`, `config/download-proxy/`, `tmp/`, `downloads/`, `__pycache__/`, `.ruff_cache/` |
| `webui-bridge.service` | systemd user service unit for webui-bridge.py |

---

## Architecture

Two-container setup via `docker-compose.yml` (both `network_mode: host`):

| Container | Image | Ports | Purpose |
|-----------|-------|-------|---------|
| **qbittorrent** | `lscr.io/linuxserver/qbittorrent:latest` | 7185 | qBittorrent WebUI |
| **qbittorrent-proxy** | `python:3.12-alpine` | 7186, 7187 | Download proxy + Merge Search Service |

**Port map:**

| Port | Service | Where |
|------|---------|-------|
| 7185 | qBittorrent WebUI | qbittorrent container |
| 7186 | Download proxy | qbittorrent-proxy container |
| 7187 | Merge Search Service (FastAPI) | qbittorrent-proxy container |
| 7188 | webui-bridge | Host process (run manually or via systemd) |

Users access `http://localhost:7186` (proxy → qBittorrent on 7185).
Merge Search dashboard at `http://localhost:7187/`.
`webui-bridge.py` is a **separate host process** — run manually: `python3 webui-bridge.py`, or install as systemd service with `./setup-webui-bridge-service.sh`.

Container runtime is **auto-detected** (podman preferred over docker) in all shell scripts.

---

## Code Organization

```
project-root/
├── plugins/                          # 42+ tracker plugins + support files
│   ├── *.py                          # Individual tracker plugins (rutracker, iptorrents, etc.)
│   ├── helpers.py                    # Shared utilities (build_magnet_link, etc.)
│   ├── nova2.py                      # Search engine core
│   ├── novaprinter.py                # Output formatting for plugins
│   ├── socks.py                      # Proxy support
│   ├── download_proxy.py             # Original download proxy server
│   ├── env_loader.py                 # Shared env file loader
│   └── webui_compatible/             # WebUI variants for private trackers (rutracker, kinozal, nnmclub)
│
├── download-proxy/src/               # Merge Search Service source (16 Python files)
│   ├── main.py                       # Entry point: starts both proxy + FastAPI in threads
│   ├── api/                          # FastAPI application layer
│   │   ├── __init__.py               # App factory, lifespan, health, stats, dashboard routes
│   │   ├── routes.py                 # Search, download, streaming endpoints (612 lines)
│   │   ├── hooks.py                  # Webhook CRUD with JSON file persistence
│   │   ├── streaming.py              # SSE streaming for real-time results
│   │   ├── auth.py                   # Tracker auth endpoints (RuTracker CAPTCHA proxy)
│   │   └── scheduler.py              # Scheduler CRUD endpoints
│   ├── merge_service/                # Core business logic
│   │   ├── search.py                 # SearchOrchestrator, data models (976 lines)
│   │   ├── deduplicator.py           # Tiered dedup: exact hash → name+size → fuzzy similarity
│   │   ├── enricher.py               # Metadata enrichment (OMDb, TMDB, TVMaze, AniList, MusicBrainz, OpenLibrary)
│   │   ├── validator.py              # Tracker validation via HTTP and UDP scrape
│   │   ├── hooks.py                  # Hook execution engine
│   │   └── scheduler.py              # Scheduled search with persistence
│   ├── config/
│   │   └── __init__.py               # EnvConfig dataclass, load_env(), get_config()
│   └── ui/
│       └── templates/
│           ├── dashboard.html        # Dark theme search dashboard
│           └── theme.css             # CSS custom properties (--theme-*)
│
├── tests/                            # 31 test files
│   ├── conftest.py                   # pytest fixtures (mock_qbittorrent_api, sample_search_result, etc.)
│   ├── unit/                         # Unit tests (no containers required)
│   │   ├── merge_service/            # test_html_parsers, test_quality_detection, test_deduplicator, test_hooks, test_validator, test_enricher, test_scheduler
│   │   ├── test_auth.py              # RuTracker CAPTCHA auth endpoint tests
│   │   ├── test_ci_infra.py          # CI pipeline infrastructure tests
│   │   ├── test_config.py            # Config env loading and fallback tests
│   │   ├── test_dashboard.py         # Dashboard UI tests
│   │   ├── test_freeleech.py         # IPTorrents freeleech logic tests
│   │   ├── test_merge_trackers.py    # Tracker merge logic tests
│   │   ├── test_routes.py            # API route tests
│   │   ├── test_scheduler_api.py     # Scheduler CRUD API endpoint tests
│   │   ├── test_streaming.py         # SSE streaming handler tests
│   │   ├── test_ui_sorting.py        # Dashboard sorting tests
│   │   └── test_webui_bridge.py      # WebUI bridge tests
│   ├── integration/                  # Integration tests (may require mocks or running containers)
│   │   ├── test_merge_api.py         # Full API endpoint integration tests
│   │   ├── test_button_functions.py  # UI button tests: Magnet, qBit, Download, Abort search
│   │   ├── test_buttons_api.py       # Button API integration tests
│   │   ├── test_auth_state_ui.py     # Auth state UI tests
│   │   ├── test_iptorrents.py        # IPTorrents-specific integration tests
│   │   ├── test_live_containers.py   # Live container health tests
│   │   ├── test_login_actions.py     # Login action tests
│   │   ├── test_magnet_dialog.py     # Magnet dialog UI tests
│   │   ├── test_realtime_streaming.py # Real-time SSE streaming tests
│   │   ├── test_streaming_browser.py # Browser-side streaming tests
│   │   ├── test_ui_comprehensive.py  # Comprehensive UI tests
│   │   └── test_ui_quick.py          # Quick UI smoke tests
│   └── e2e/
│       └── test_full_pipeline.py     # End-to-end full pipeline test
│
├── config/                           # Runtime config (partially gitignored)
│   ├── qBittorrent/                  # qBittorrent config + plugins
│   │   ├── config/qBittorrent.conf   # Default config template (WebUI port 7185, admin/admin)
│   │   └── nova3/engines/            # Plugin install destination inside container
│   ├── download-proxy/               # Proxy runtime config
│   │   ├── requirements.txt          # Copied from download-proxy/requirements.txt
│   │   ├── qbittorrent_creds.json    # Saved qBittorrent credentials (gitignored)
│   │   └── hooks.json                # Runtime hooks (gitignored)
│   └── merge-service/                # Scheduler runtime data (gitignored)
│       ├── scheduling.json
│       ├── data-model.yaml
│       └── hooks.yaml
│
├── docs/                             # Project documentation
│   ├── USER_MANUAL.md                # Complete usage guide
│   ├── PLUGINS.md                    # Plugin documentation
│   ├── PLUGIN_TROUBLESHOOTING.md     # Debug guide
│   ├── DOWNLOAD_FIX.md               # Download fix documentation
│   ├── MAGNET_LINKS.md               # Magnet link handling
│   ├── RELEASE_TORRENT_UPLOAD_FIX.md # Release fix notes
│   └── TEST_RESULTS.md               # Test result documentation
│
├── tools/                            # Utility scripts
│   └── plugin_update_automation.py   # Plugin update automation
│
├── *.sh                              # Shell scripts (see Key Commands below)
├── webui-bridge.py                   # Host process bridge (port 7188)
├── webui-bridge.service              # systemd unit file
└── .env.example                      # Environment variable template
```

---

## Merge Search Service

FastAPI application in `download-proxy/src/api/`. Runs inside the qbittorrent-proxy container on port 7187.

### Key Files

| File | Purpose |
|------|---------|
| `download-proxy/src/api/__init__.py` | FastAPI app, lifespan (init SearchOrchestrator + TrackerValidator + MetadataEnricher + Scheduler), health, stats, dashboard routes |
| `download-proxy/src/api/routes.py` | `POST /search`, `GET /search/stream/{id}`, `POST /download`, `GET /downloads/active` |
| `download-proxy/src/api/hooks.py` | `GET/POST/DELETE /hooks` — JSON file at `/config/download-proxy/hooks.json` |
| `download-proxy/src/api/auth.py` | Tracker auth endpoints: RuTracker CAPTCHA fetch/login/cookie-login, multi-tracker auth status at `/auth/status` |
| `download-proxy/src/api/scheduler.py` | Scheduler CRUD endpoints at `/api/v1/schedules` |
| `download-proxy/src/api/streaming.py` | SSE streaming via `SSEHandler` class — `search_results_stream()`, `download_progress_stream()` |
| `download-proxy/src/merge_service/search.py` | `SearchOrchestrator` class, `ContentType`/`QualityTier` enums, `TorrentResult` dataclass, `TrackerSource`, `CanonicalIdentity` |
| `download-proxy/src/merge_service/deduplicator.py` | Tiered deduplication engine (hash → name+size → fuzzy similarity) |
| `download-proxy/src/merge_service/enricher.py` | Multi-provider metadata enrichment |
| `download-proxy/src/merge_service/validator.py` | `TrackerValidator` — HTTP and UDP scrape validation |
| `download-proxy/src/merge_service/scheduler.py` | Scheduled search with JSON persistence |
| `download-proxy/src/merge_service/hooks.py` | Hook execution engine |
| `download-proxy/src/config/__init__.py` | `EnvConfig` dataclass, env loading with fallback chains |
| `download-proxy/src/main.py` | Dual-thread entry point: original proxy + FastAPI server |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/search` | Search across multiple trackers |
| `GET` | `/api/v1/search/stream/{id}` | SSE stream of real-time search results |
| `POST` | `/api/v1/download` | Download via authenticated proxy |
| `GET` | `/api/v1/downloads/active` | List active downloads |
| `GET` | `/api/v1/hooks` | List configured hooks |
| `POST` | `/api/v1/hooks` | Create a hook |
| `DELETE` | `/api/v1/hooks` | Delete a hook |
| `GET` | `/api/v1/schedules` | List scheduled searches |
| `POST` | `/api/v1/schedules` | Create scheduled search |
| `DELETE` | `/api/v1/schedules/{id}` | Delete scheduled search |
| `GET` | `/api/v1/auth/status` | Multi-tracker auth status |
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/stats` | Service statistics |
| `GET` | `/api/v1/config` | qBittorrent connection config |
| `GET` | `/` | Dashboard UI (dark theme) |
| `GET` | `/theme.css` | Dashboard theme stylesheet |

### Syncing Code to Container

After editing `download-proxy/src/`, sync to the running container:

```bash
podman cp download-proxy/src/. qbittorrent-proxy:/config/download-proxy/src/ && podman restart qbittorrent-proxy
```

The `download-proxy` volume mount (`./download-proxy:/config/download-proxy`) should pick up changes, but a restart is needed to reload the Python modules.

---

## Plugin System

**`plugins/` contains 48 Python files**, including 42 managed tracker plugins:

`academictorrents`, `ali213`, `anilibra`, `audiobookbay`, `bitru`, `bt4g`, `btsow`, `extratorrent`, `eztv`, `gamestorrents`, `glotorrents`, `iptorrents`, `jackett`, `kickass`, `kinozal`, `limetorrents`, `linuxtracker`, `megapeer`, `nnmclub`, `nyaa`, `one337x`, `pctorrent`, `piratebay`, `pirateiro`, `rockbox`, `rutor`, `rutracker`, `snowfl`, `solidtorrents`, `therarbg`, `tokyotoshokan`, `torlock`, `torrentdownload`, `torrentfunk`, `torrentgalaxy`, `torrentkitty`, `torrentproject`, `torrentscsv`, `xfsub`, `yihua`, `yourbittorrent`, `yts`

Plugin support files live alongside plugins: `helpers.py`, `nova2.py`, `novaprinter.py`, `socks.py`, `download_proxy.py`, `env_loader.py`.

WebUI-compatible private tracker plugins are also in `plugins/webui_compatible/` (`rutracker.py`, `kinozal.py`, `nnmclub.py`).

### Plugin Contract

Each plugin is a Python class with:
- Class attributes: `url`, `name`, `supported_categories` (dict mapping category name to ID string)
- `search(self, what, cat='all')` — outputs results via `novaprinter.print()`
- `download_torrent(self, url)` — returns magnet link or file path
- Output format: `novaprinter.print(name, link, size, seeds, leech, engine_url, desc_link, pub_date)`

Plugins are installed to `config/qBittorrent/nova3/engines/` inside the container.

---

## Environment Variables

Loaded in priority order (first wins): **shell env → `./.env` → `~/.qbit.env` → container env from compose**.

Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `RUTRACKER_USERNAME/PASSWORD` | — | RuTracker login |
| `KINOZAL_USERNAME/PASSWORD` | falls back to IPTORRENTS | Kinozal login |
| `NNMCLUB_COOKIES` | — | NNMClub session cookies |
| `IPTORRENTS_USERNAME/PASSWORD` | — | IPTorrents login |
| `QBITTORRENT_DATA_DIR` | `/mnt/DATA` | Download directory |
| `PUID/PGID` | `1000` | Container user/group IDs |
| `MERGE_SERVICE_PORT` | `7187` | FastAPI port |
| `PROXY_PORT` | `7186` | Download proxy port |
| `BRIDGE_PORT` | `7188` | webui-bridge port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `OMDB_API_KEY` | — | OMDb metadata enrichment |
| `TMDB_API_KEY` | — | TMDB metadata enrichment |
| `ANILIST_CLIENT_ID` | — | AniList metadata enrichment |

`KINOZAL_USERNAME/PASSWORD` and `NNMCLUB_COOKIES` must be in `.env` for the merge service to authenticate with those trackers. These are passed through from `docker-compose.yml` to the qbittorrent-proxy container.

---

## Key Commands

### Startup
```bash
./setup.sh                    # One-time: creates dirs, config, installs plugins, starts containers
./start.sh                    # Start containers (flags: -p pull, -s status, --no-plugins, -v verbose)
./start.sh -p                 # Pull latest images and start
./setup-webui-bridge-service.sh  # One-time: install webui-bridge as systemd user service
./stop.sh                     # Stop (flags: -r remove containers, --purge also clean images)
python3 webui-bridge.py       # Manual start of WebUI bridge (port 7188)
```

### Testing
```bash
./ci.sh                       # Full manual CI pipeline (syntax + unit + integration + e2e + container health)
./ci.sh --quick               # Quick check (syntax + unit tests only)
./ci.sh --tests-only          # Skip syntax checks, run tests only
./ci.sh --verbose             # Verbose output
./run-all-tests.sh            # Full suite — requires running container, uses podman specifically
./test.sh                     # Quick validation (flags: --all, --quick, --plugin, --full, --container)
python3 -m py_compile plugins/*.py        # Syntax check all plugins
bash -n start.sh stop.sh test.sh install-plugin.sh  # Bash syntax check
python3 -m pytest tests/unit/merge_service/ tests/integration/test_merge_api.py -v --import-mode=importlib
```

### Plugin Management
```bash
./install-plugin.sh --all              # Install all managed plugins to container engines dir
./install-plugin.sh rutracker rutor    # Install specific ones
./install-plugin.sh --verify           # Verify installation
./install-plugin.sh --local --all      # Install to local qBittorrent (~/.local/share/...)
```

### Linting
```bash
ruff check .                  # Lint all Python files
ruff check --fix .            # Lint and auto-fix issues
ruff format .                 # Format all Python files
```

---

## Testing Strategy

### Test Structure
- **31 test files** across `tests/unit/`, `tests/integration/`, `tests/e2e/`
- **Unit tests**: Fast, no external dependencies, heavily mocked
- **Integration tests**: May require running containers or mock servers
- **E2E tests**: Full pipeline tests

### Running Specific Test Suites
```bash
# Unit tests only
python3 -m pytest tests/unit/ -v --import-mode=importlib

# Merge service unit tests
python3 -m pytest tests/unit/merge_service/ -v --import-mode=importlib

# Integration tests
python3 -m pytest tests/integration/ -v --import-mode=importlib

# Specific test file
python3 -m pytest tests/unit/test_freeleech.py -v --import-mode=importlib
```

### Test Files Reference

| Test File | What It Tests |
|-----------|---------------|
| `tests/unit/merge_service/test_html_parsers.py` | RuTracker, Kinozal, NNMClub HTML parsing |
| `tests/unit/merge_service/test_quality_detection.py` | UHD 4K, Full HD, HD, SD detection |
| `tests/unit/merge_service/test_deduplicator.py` | Hash, name+size, fuzzy dedup tiers |
| `tests/unit/merge_service/test_hooks.py` | Hook creation, persistence, execution |
| `tests/unit/merge_service/test_validator.py` | Tracker HTTP and UDP scrape validation |
| `tests/unit/merge_service/test_enricher.py` | Metadata enrichment from multiple providers |
| `tests/unit/merge_service/test_scheduler.py` | Scheduled search persistence and execution |
| `tests/unit/test_auth.py` | RuTracker CAPTCHA auth endpoint tests |
| `tests/unit/test_scheduler_api.py` | Scheduler CRUD API endpoint tests |
| `tests/unit/test_streaming.py` | SSE streaming handler tests |
| `tests/unit/test_config.py` | Config env loading and fallback tests |
| `tests/unit/test_ci_infra.py` | CI pipeline infrastructure tests |
| `tests/unit/test_dashboard.py` | Dashboard rendering and UI tests |
| `tests/unit/test_freeleech.py` | IPTorrents freeleech logic and tags |
| `tests/unit/test_merge_trackers.py` | Tracker merge and dedup logic |
| `tests/unit/test_routes.py` | FastAPI route handler tests |
| `tests/unit/test_ui_sorting.py` | Dashboard result sorting tests |
| `tests/unit/test_webui_bridge.py` | WebUI bridge request handling |
| `tests/integration/test_merge_api.py` | Full API endpoint integration tests |
| `tests/integration/test_button_functions.py` | UI button tests: Magnet, qBit, Download, Abort search |
| `tests/integration/test_buttons_api.py` | Button API integration tests |
| `tests/integration/test_auth_state_ui.py` | Auth state UI tests |
| `tests/integration/test_iptorrents.py` | IPTorrents-specific integration tests |
| `tests/integration/test_live_containers.py` | Live container health tests |
| `tests/integration/test_login_actions.py` | Login action tests |
| `tests/integration/test_magnet_dialog.py` | Magnet dialog UI tests |
| `tests/integration/test_realtime_streaming.py` | Real-time SSE streaming tests |
| `tests/integration/test_streaming_browser.py` | Browser-side streaming tests |
| `tests/integration/test_ui_comprehensive.py` | Comprehensive UI tests |
| `tests/integration/test_ui_quick.py` | Quick UI smoke tests |
| `tests/e2e/test_full_pipeline.py` | End-to-end search→download pipeline |

### Fixtures (conftest.py)
- `qbittorrent_host`, `qbittorrent_port`, `qbittorrent_url`
- `mock_qbittorrent_api` — Mocked API client with `get_torrents`, `add_torrent`, `get_torrent_files`
- `sample_search_result`, `sample_merged_result`

---

## Code Style Guidelines

### Bash
- `set -euo pipefail` in every script
- `[[ ]]` conditionals, quoted variables
- `snake_case` functions, `UPPER_CASE` constants
- 4-space indent
- Shared color-print helpers: `print_info`, `print_success`, `print_warning`, `print_error`
- Auto-detect container runtime (podman preferred)
- Always provide `-h/--help` flags

### Python
- **PEP 8** compliant
- **Type hints** on public methods
- `try: import novaprinter` pattern for optional dependencies in plugins
- No `requirements.txt` at root — only `download-proxy/requirements.txt` and `tests/requirements.txt`
- **ruff** for linting and formatting (`ruff.toml`):
  - Target Python 3.12
  - Line length: 120
  - Enabled: E, F, W, I, UP, B, SIM, RUF
  - Ignored: E501 (line too long — handled by 120 char limit)
  - Known first-party: `api`, `merge_service`, `config`, `plugins`
  - Quote style: double, indent: space

### Merge Service Python
- FastAPI with async handlers
- `aiohttp` for outbound HTTP requests
- `sys.path` manipulation for imports in container environment
- No comments in merge service source (project convention per CONTRIBUTING.md)

---

## Security Considerations

- `.env` is **gitignored** — never commit it
- `ci.sh` Phase 1 scans for hardcoded secrets in tracked files
- `*.key`, `*.pem`, `*credentials*`, `*secrets*` are gitignored
- RuTracker CAPTCHA handling via browser-solved challenge, not credential bypass
- Private tracker downloads authenticated via session cookies, not URL tokens
- `webui-bridge.py` runs locally only (binds to all interfaces but intended for localhost)
- qBittorrent WebUI auth subnet whitelist is `0.0.0.0/0` (development convenience)

---

## Gotchas

- `run-all-tests.sh` hardcodes **podman** commands — will fail on docker-only systems.
- Private tracker tests need valid credentials in `.env` and sometimes a browser-solved CAPTCHA (RuTracker).
- **RuTracker login may fail with CAPTCHA** — cookies expire periodically. Re-authenticate via browser if needed.
- **Kinozal credentials fall back to IPTorrents** — if `KINOZAL_USERNAME/PASSWORD` are not set, `IPTORRENTS_USERNAME/PASSWORD` are used automatically.
- **NNMClub needs cookies in `.env`** — `NNMCLUB_COOKIES` is required for live testing.
- **IPTorrents non-freeleech results never merge** with other trackers. Only `[free]` tagged IPTorrents results merge with duplicates from other trackers.
- **IPTorrents freeleech results get ` [free]` suffix** in the name — no confusion about which are safe to download.
- `webui-bridge.py` auto-starts via systemd user service (port 7188). Install once with `./setup-webui-bridge-service.sh`.
- The proxy container runs `start-proxy.sh` which installs all deps from `requirements.txt` at startup (including Levenshtein).
- Plugin install destination: `config/qBittorrent/nova3/engines/` (not `plugins/`).
- The merge service hooks file is at `/config/download-proxy/hooks.json` inside the container.
- `start-proxy.sh` starts both the download proxy and the merge service (dual-thread via `main.py`).
- `ci.sh` is **manual only** — never auto-triggered by Git hooks or remote CI. Run it yourself before releases.
- GitHub Actions workflow (`.github/workflows/test.yml`) is `workflow_dispatch` only — no automatic CI.
- `config/download-proxy/src/` is **gitignored** — do not commit copied source trees.

---

## Dashboard Features

### Theme System
All colors defined in `theme.css` using CSS custom properties (`--theme-*`). Dashboard loads theme.css and uses `var(--theme-*)` variables for visual consistency.

### Search/Abort Toggle
The Search button toggles to an Abort button during active searches using `AbortController`. Clicking Abort cancels the in-flight fetch request and resets the button back to Search. The button also resets on search completion, error, or CAPTCHA redirect. CSS class `.btn-abort` turns the button red during search.

### Content Type Detection
`_detect_content_type()` in `deduplicator.py` detects: movie, tv, music, game, anime, software, audiobook, ebook. TV detection covers patterns like `S01E05`, `Season 1`, `Seasons 1-6`, `Seasons 1 - 6 Complete`, `Episode 3`. No hardcoded titles — only dynamic patterns (release groups, platforms, file formats, genre markers).

### qBittorrent Authentication
- Login modal accessible via "qBit" button click
- "Remember me" checkbox saves credentials to `/config/download-proxy/qbittorrent_creds.json`
- API routes load saved credentials first, fallback to env vars (`QBITTORRENT_USER`, `QBITTORRENT_PASS`)
- First-time setup: use `init-qbit-password.sh` to set initial password

### Magnet Dialog
Click "Magnet" button to open a dialog with:
- **Text area** showing the magnet link (click to select all)
- **Copy button** — copies magnet link to clipboard using fallback method (works in Yandex browser)
- **Open button** — triggers mobile torrent app via `href="magnet:..."` — works on mobile devices to open default torrent client
- Uses `execCommand('copy')` fallback instead of `navigator.clipboard` for browser compatibility

---

## Contributing & Commit Style

- Branch naming: `feature/your-feature-name`
- Commit format: `<type>: <subject>` where type is one of `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Always run tests before committing: `./test.sh --full` or `./ci.sh`
- Update `README.md`, `USER_MANUAL.md`, and `AGENTS.md` for user/dev-facing changes
- See `CONTRIBUTING.md` for full guidelines
