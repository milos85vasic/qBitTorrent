# AGENTS.md

## Critical Constraints

- **TDD is MANDATORY for all bug fixes and features**:
  - Write failing test first (RED)
  - Watch it fail
  - Write minimal code to pass (GREEN)
  - Verify tests pass
  - Then commit
  - See `tests/README.md` for detailed TDD workflow

- **WebUI credentials `admin`/`admin` are hardcoded** in `start.sh` config generation, `docker-compose.yml`, and multiple scripts. Do not change them.
- **Never commit `.env`** — it contains tracker credentials. `.env.example` is the template.
- **Freeleech-only downloads from IPTorrents** — all automated testing must ONLY download freeleech torrents. Freeleech results are tagged `IPTorrents [free]` in tracker display name. Non-freeleech IPTorrents downloads cost ratio and must NEVER be triggered by automation or tests.

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
| 7188 | webui-bridge | Host process (run manually) |

Users access `http://localhost:7186` (proxy → qBittorrent on 7185).
Merge Search dashboard at `http://localhost:7187/`.
`webui-bridge.py` is a **separate host process** — run manually: `python3 webui-bridge.py`.

Container runtime is **auto-detected** (podman preferred over docker) in all shell scripts.

## Merge Search Service

FastAPI application in `download-proxy/src/api/`. Runs inside the qbittorrent-proxy container on port 7187.

### Source Structure

```
download-proxy/src/
├── api/                          # FastAPI application layer
│   ├── __init__.py               # App factory, lifespan, health check, stats endpoint
│   ├── routes.py                 # Search, download, streaming endpoints
│   ├── hooks.py                  # Webhook CRUD with JSON file persistence
│   ├── streaming.py              # SSE streaming for real-time results
│   ├── auth.py                   # Tracker auth endpoints (RuTracker CAPTCHA proxy)
│   └── scheduler.py              # Scheduler CRUD endpoints
├── merge_service/                # Core business logic
│   ├── __init__.py
│   ├── search.py                 # SearchOrchestrator, data models (ContentType, QualityTier, TorrentResult)
│   ├── deduplicator.py           # Tiered dedup: exact hash → name+size → fuzzy similarity
│   ├── enricher.py               # Metadata enrichment (OMDb, TMDB, TVMaze, AniList, MusicBrainz, OpenLibrary)
│   ├── validator.py              # Tracker validation via HTTP and UDP scrape
│   ├── hooks.py                  # Hook execution engine
│   └── scheduler.py              # Scheduled search with persistence
├── config/
│   └── __init__.py               # Configuration module
└── ui/
    ├── __init__.py
    └── templates/dashboard.html  # Dark theme search dashboard
```

Plugin support files live at `plugins/env_loader.py` (shared env file loader, not inside `download-proxy/src/`).

### Key Files

| File | Purpose |
|------|---------|
| `download-proxy/src/api/__init__.py` | FastAPI app, lifespan (init SearchOrchestrator + TrackerValidator), health, stats, dashboard routes |
| `download-proxy/src/api/routes.py` | `POST /search`, `GET /search/stream/{id}`, `POST /download`, `GET /downloads/active` |
| `download-proxy/src/api/hooks.py` | `GET/POST/DELETE /hooks` — JSON file at `/config/download-proxy/hooks.json` |
| `download-proxy/src/api/auth.py` | Tracker auth endpoints: RuTracker CAPTCHA fetch/login/cookie-login, multi-tracker auth status at `/auth/status` |
| `download-proxy/src/api/scheduler.py` | Scheduler CRUD endpoints at `/api/v1/schedules` |
| `download-proxy/src/api/streaming.py` | SSE streaming via `SSEHandler` class — `search_results_stream()`, `download_progress_stream()` |
| `download-proxy/src/merge_service/search.py` | `SearchOrchestrator` class, `ContentType`/`QualityTier` enums, `TorrentResult` dataclass |
| `download-proxy/src/merge_service/deduplicator.py` | Tiered deduplication engine |
| `download-proxy/src/merge_service/enricher.py` | Multi-provider metadata enrichment |
| `download-proxy/src/merge_service/validator.py` | `TrackerValidator` — HTTP and UDP scrape |

### Syncing Code to Container

After editing `download-proxy/src/`, sync to the running container:

```bash
podman cp download-proxy/src/. qbittorrent-proxy:/config/download-proxy/src/ && podman restart qbittorrent-proxy
```

The `download-proxy` volume mount (`./download-proxy:/config/download-proxy`) should pick up changes, but a restart is needed to reload the Python modules.

### Merge Service Tests

```bash
python3 -m pytest tests/unit/merge_service/ tests/integration/test_merge_api.py -v --import-mode=importlib
```

Test files:

| Test File | What It Tests |
|-----------|---------------|
| `tests/unit/merge_service/test_html_parsers.py` | RuTracker, Kinozal, NNMClub HTML parsing |
| `tests/unit/merge_service/test_quality_detection.py` | UHD 4K, Full HD, HD, SD detection |
| `tests/unit/merge_service/test_deduplicator.py` | Hash, name+size, fuzzy dedup tiers |
| `tests/unit/merge_service/test_hooks.py` | Hook creation, persistence, execution |
| `tests/unit/merge_service/test_validator.py` | Tracker HTTP and UDP scrape validation |
| `tests/unit/merge_service/test_enricher.py` | Metadata enrichment from multiple providers |
| `tests/unit/test_auth.py` | RuTracker CAPTCHA auth endpoint tests |
| `tests/unit/test_scheduler_api.py` | Scheduler CRUD API endpoint tests |
| `tests/unit/test_streaming.py` | SSE streaming handler tests |
| `tests/unit/test_config.py` | Config env loading and fallback tests |
| `tests/integration/test_merge_api.py` | Full API endpoint integration tests |
| `tests/integration/test_button_functions.py` | UI button tests: Magnet, qBit, Download, Abort search |

## Dashboard Features

### Search/Abort Toggle
The Search button toggles to an Abort button during active searches using `AbortController`. Clicking Abort cancels the in-flight fetch request and resets the button back to Search. The button also resets on search completion, error, or CAPTCHA redirect. CSS class `.btn-abort` turns the button red during search.

### Content Type Detection
`_detect_content_type()` in `deduplicator.py` detects: movie, tv, music, game, anime, software, audiobook, ebook. TV detection covers patterns like `S01E05`, `Season 1`, `Seasons 1-6`, `Seasons 1 - 6 Complete`, `Episode 3`. No hardcoded titles — only dynamic patterns (release groups, platforms, file formats, genre markers).

## Key Commands

### Startup
```bash
./setup.sh                    # One-time: creates dirs, config, installs plugins, starts containers
./start.sh                    # Start containers (flags: -p pull, -s status, --no-plugins, -v verbose)
./setup-webui-bridge-service.sh  # One-time: install webui-bridge as systemd user service
./start.sh -p                 # Everything auto-starts (containers + bridge via systemd)
./stop.sh                     # Stop (flags: -r remove containers, --purge also clean images)
```

### Testing
```bash
./ci.sh                       # Full CI pipeline (manual only, never auto-triggered)
./ci.sh --quick               # Quick check (syntax + unit tests only)
./run-all-tests.sh            # Full suite — requires running container, uses podman specifically
./test.sh                     # Quick validation (flags: --all, --quick, --plugin, --full, --container)
python3 -m py_compile plugins/*.py   # Syntax check all plugins
bash -n start.sh stop.sh test.sh install-plugin.sh  # Bash syntax check
python3 -m pytest tests/unit/merge_service/ tests/integration/test_merge_api.py -v --import-mode=importlib
```

There is **no auto-triggered CI pipeline**. `ci.sh` is the manual CI pipeline — run it yourself before releases. No GitHub Actions, no webhooks. The only validation is `ci.sh` (which runs `bash -n`, `py_compile`, pytest, and container health checks).

### Plugin Management
```bash
./install-plugin.sh --all              # Install all 42 managed plugins
./install-plugin.sh rutracker rutor    # Install specific ones
./install-plugin.sh --verify           # Verify installation
./install-plugin.sh --local --all      # Install to local qBittorrent (~/.local/share/...)
```

## Plugin System

**`plugins/` contains 42 tracker plugins**, all managed by `install-plugin.sh`:
`academictorrents ali213 anilibra audiobookbay bitru bt4g btsow extratorrent eztv gamestorrents glotorrents iptorrents jackett kickass kinozal limetorrents linuxtracker megapeer nnmclub nyaa one337x pctorrent piratebay pirateiro rockbox rutor rutracker snowfl solidtorrents therarbg tokyotoshokan torlock torrentdownload torrentfunk torrentgalaxy torrentkitty torrentproject torrentscsv xfsub yihua yourbittorrent yts`

Plugin support files live alongside plugins: `helpers.py`, `nova2.py`, `novaprinter.py`, `socks.py`, `download_proxy.py`, `env_loader.py`.

WebUI-compatible private tracker plugins are also in `plugins/webui_compatible/` (rutracker, kinozal, nnmclub variants).

### Plugin Contract

Each plugin is a Python class with:
- Class attributes: `url`, `name`, `supported_categories` (dict mapping category name to ID string)
- `search(self, what, cat='all')` — outputs results via `novaprinter.print()`
- `download_torrent(self, url)` — returns magnet link or file path
- Output format: `novaprinter.print(name, link, size, seeds, leech, engine_url, desc_link, pub_date)`

Plugins are installed to `config/qBittorrent/nova3/engines/` inside the container.

## Environment Variables

Loaded in priority order (first wins): shell env → `./.env` → `~/.qbit.env` → container env from compose.

Key variables: `RUTRACKER_USERNAME/PASSWORD`, `KINOZAL_USERNAME/PASSWORD`, `NNMCLUB_COOKIES`, `IPTORRENTS_USERNAME/PASSWORD`, `QBITTORRENT_DATA_DIR` (default `/mnt/DATA`), `PUID/PGID` (default `1000`).

Merge service also uses: `MERGE_SERVICE_PORT` (default 7187), `PROXY_PORT` (default 7186).

### Credentials for Merge Service Trackers

`KINOZAL_USERNAME/PASSWORD` and `NNMCLUB_COOKIES` must be in `.env` for the merge service to authenticate with those trackers. These are passed through from `docker-compose.yml` to the qbittorrent-proxy container.

## Code Conventions

- **Bash**: `set -euo pipefail`, `[[ ]]` conditionals, quoted variables, `snake_case` functions, `UPPER_CASE` constants, 4-space indent. Scripts use shared color-print helpers (`print_info`, `print_success`, `print_warning`, `print_error`).
- **Python**: PEP 8, type hints on public methods, `try: import novaprinter` pattern (optional dependency). No `requirements.txt` at root — only `tests/requirements.txt` (pytest, requests, responses, pytest-cov).

## Gotchas

- `run-all-tests.sh` hardcodes **podman** commands — will fail on docker-only systems.
- Private tracker tests need valid credentials in `.env` and sometimes a browser-solved CAPTCHA (RuTracker).
- **RuTracker login may fail with CAPTCHA** — cookies expire periodically. Re-authenticate via browser if needed.
- **Kinozal credentials fall back to IPTorrents** — if `KINOZAL_USERNAME/PASSWORD` are not set, `IPTORRENTS_USERNAME/PASSWORD` are used automatically.
- **NNMClub needs cookies in `.env`** — `NNMCLUB_COOKIES` is required for live testing.
- **IPTorrents non-freeleech results never merge** with other trackers. Only `[free]` tagged IPTorrents results merge with duplicates from other trackers.
- **IPTorrents freeleech results get `[ [free]` suffix** in the name — no confusion about which are safe to download.
- `webui-bridge.py` auto-starts via systemd user service (port 7188). Install once with `./setup-webui-bridge-service.sh`.
- The proxy container runs `start-proxy.sh` which installs all deps from `requirements.txt` at startup (including Levenshtein).
- Plugin install destination: `config/qBittorrent/nova3/engines/` (not `plugins/`).
- The merge service hooks file is at `/config/download-proxy/hooks.json` inside the container.
- `start-proxy.sh` starts both the download proxy and the merge service (dual-thread via `main.py`).
- `ci.sh` is **manual only** — never auto-triggered by Git hooks or remote CI. Run it yourself before releases.

## Dashboard Features

### Theme System
All colors defined in `theme.css` using CSS custom properties (`--theme-*`). Dashboard loads theme.css and uses `var(--theme-*)` variables for visual consistency.

### Search/Abort Toggle
Search button toggles to Abort button during active searches using `AbortController`. Clicking Abort cancels the in-flight fetch request and resets button.

### Content Type Detection
`_detect_content_type()` in `deduplicator.py` detects: movie, tv, music, game, anime, software, audiobook, ebook using dynamic patterns (release groups, platforms, file formats, genre markers).

### qBittorrent Authentication
- Login modal accessible via "qBit" button click
- "Remember me" checkbox saves credentials to `/config/download-proxy/qbittorrent_creds.json`
- API routes load saved credentials first, fallback to env vars (`QBITTORRENT_USER`, `QBITTORRENT_PASS`)
- First-time setup: use `init-qbit-password.sh` to set initial password
