# AGENTS.md

## Critical Constraints

- **WebUI credentials `admin`/`admin` are hardcoded** in `start.sh` config generation, `docker-compose.yml`, and multiple scripts. Do not change them.
- **Never commit `.env`** — it contains tracker credentials. `.env.example` is the template.
- **Freeleech-only downloads from IPTorrents** — all automated testing must ONLY download freeleech torrents. Freeleech results are tagged `IPTorrents [free]` in tracker display name. Non-freeleech IPTorrents downloads cost ratio and must NEVER be triggered by automation or tests.

## Architecture

Two-container setup via `docker-compose.yml` (both `network_mode: host`):

| Container | Image | Ports | Purpose |
|-----------|-------|-------|---------|
| **qbittorrent** | `lscr.io/linuxserver/qbittorrent:latest` | 18085 | qBittorrent WebUI |
| **qbittorrent-proxy** | `python:3.12-alpine` | 8085, 8086 | Download proxy + Merge Search Service |

**Port map:**

| Port | Service | Where |
|------|---------|-------|
| 18085 | qBittorrent WebUI | qbittorrent container |
| 8085 | Download proxy | qbittorrent-proxy container |
| 8086 | Merge Search Service (FastAPI) | qbittorrent-proxy container |
| 8666 | webui-bridge | Host process (run manually) |

Users access `http://localhost:8085` (proxy → qBittorrent on 18085).
Merge Search dashboard at `http://localhost:8086/`.
`webui-bridge.py` is a **separate host process** — run manually: `python3 webui-bridge.py`.

Container runtime is **auto-detected** (podman preferred over docker) in all shell scripts.

## Merge Search Service

FastAPI application in `download-proxy/src/api/`. Runs inside the qbittorrent-proxy container on port 8086.

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
├── plugins/
│   └── env_loader.py             # Shared env file loader
└── ui/
    ├── __init__.py
    └── templates/dashboard.html  # Dark theme search dashboard
```

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

## Key Commands

### Startup
```bash
./setup.sh                    # One-time: creates dirs, config, installs plugins, starts containers
./start.sh                    # Start containers (flags: -p pull, -s status, --no-plugins, -v verbose)
./start.sh -p && python3 webui-bridge.py   # Full start with bridge
./stop.sh                     # Stop (flags: -r remove containers, --purge also clean images)
```

### Testing
```bash
./run-all-tests.sh            # Full suite — requires running container, uses podman specifically
./test.sh                     # Quick validation (flags: --all, --quick, --plugin, --full, --container)
python3 -m py_compile plugins/*.py   # Syntax check all plugins
bash -n start.sh stop.sh test.sh install-plugin.sh  # Bash syntax check
python3 -m pytest tests/unit/merge_service/ tests/integration/test_merge_api.py -v --import-mode=importlib
```

There is **no CI pipeline, no linter config, no type checking**. `ruff` is used informally (`.ruff_cache/` exists) but has no config file. The only validation is `bash -n` and `py_compile`.

### Plugin Management
```bash
./install-plugin.sh --all              # Install the 12 managed plugins
./install-plugin.sh rutracker rutor    # Install specific ones
./install-plugin.sh --verify           # Verify installation
./install-plugin.sh --local --all      # Install to local qBittorrent (~/.local/share/...)
```

## Plugin System

**`plugins/` contains 35+ tracker plugins**, but `install-plugin.sh` only manages these 12:
`eztv jackett limetorrents piratebay solidtorrents torlock torrentproject torrentscsv rutracker rutor kinozal nnmclub`

The remaining plugins (nyaa, yts, torrentgalaxy, etc.) exist in `plugins/` but are not in the install script's array.

Plugin support files live alongside plugins: `helpers.py`, `nova2.py`, `novaprinter.py`, `socks.py`, `download_proxy.py`.

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

Merge service also uses: `MERGE_SERVICE_PORT` (default 8086), `PROXY_PORT` (default 8085).

### Credentials for Merge Service Trackers

`KINOZAL_USERNAME/PASSWORD` and `NNMCLUB_COOKIES` must be in `.env` for the merge service to authenticate with those trackers. These are passed through from `docker-compose.yml` to the qbittorrent-proxy container.

## Code Conventions

- **Bash**: `set -euo pipefail`, `[[ ]]` conditionals, quoted variables, `snake_case` functions, `UPPER_CASE` constants, 4-space indent. Scripts use shared color-print helpers (`print_info`, `print_success`, `print_warning`, `print_error`).
- **Python**: PEP 8, type hints on public methods, `try: import novaprinter` pattern (optional dependency). No `requirements.txt` at root — only `tests/requirements.txt` (pytest, requests, responses, pytest-cov).

## Gotchas

- `run-all-tests.sh` hardcodes **podman** commands — will fail on docker-only systems.
- Private tracker tests need valid credentials in `.env` and sometimes a browser-solved CAPTCHA (RuTracker).
- **RuTracker login may fail with CAPTCHA** — cookies expire periodically. Re-authenticate via browser if needed.
- **Kinozal/NNMClub need credentials in `.env`** — `KINOZAL_USERNAME/PASSWORD` and `NNMCLUB_COOKIES` are required for live testing.
- `.ruff_cache/` is **not in `.gitignore`** — it should be.
- Several empty root files exist (`CONFIG`, `SCRIPT`, `EOF`) — do not remove, they may be referenced.
- `webui-bridge.py` default port is 8666, not 8085 or 18085.
- The proxy container runs `start-proxy.sh` which installs `requests` at startup.
- Plugin install destination: `config/qBittorrent/nova3/engines/` (not `plugins/`).
- The merge service hooks file is at `/config/download-proxy/hooks.json` inside the container.
- `start-proxy.sh` currently only starts the download proxy, not the merge service. The merge service may need a separate startup command or the start script needs updating.
