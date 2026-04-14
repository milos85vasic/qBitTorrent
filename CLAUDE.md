# CLAUDE.md

## Critical Constraints

- **WebUI credentials `admin`/`admin` are hardcoded** — do not change.
- **Never commit `.env`** — it contains tracker credentials.
- **Never commit `.ruff_cache/`** — add to `.gitignore`.
- **Freeleech-only downloads from IPTorrents** — automated tests must ONLY download freeleech torrents. Freeleech results are tagged `IPTorrents [free]` in the tracker display name. Non-freeleech downloads cost ratio and must never be automated.

## Architecture

Two-container setup via `docker-compose.yml`:

- **qbittorrent** (lscr.io/linuxserver/qbittorrent:latest) — port **79085**
- **qbittorrent-proxy** (python:3.12-alpine) — ports **78085** (proxy), **78086** (merge service)

`webui-bridge.py` is a host process on port **78666** for private tracker downloads. Not a container.

Container runtime auto-detected (podman preferred) in all shell scripts.

### Port Map

| Port | Service | Access |
|------|---------|--------|
| 78085 | Download proxy → qBittorrent WebUI | `http://localhost:78085` |
| 78086 | Merge Search Service (FastAPI) | `http://localhost:78086/` |
| 79085 | qBittorrent WebUI (container-internal) | proxied via 78085 |
| 78666 | webui-bridge.py (host process) | manual start |

## Key Commands

### Startup
```bash
./setup.sh                                         # One-time setup
./start.sh                                         # Start containers (-p pull, -s status, -v verbose)
./start.sh -p && python3 webui-bridge.py           # Full start with bridge
./stop.sh                                          # Stop (-r remove, --purge clean images)
```

### Testing
```bash
./run-all-tests.sh                                 # Full suite (requires podman)
./test.sh                                          # Quick validation (--all, --quick, --plugin, --full)
python3 -m py_compile plugins/*.py                 # Syntax check plugins
bash -n start.sh stop.sh test.sh install-plugin.sh # Bash syntax check
```

### Merge Service
```bash
python3 -m pytest download-proxy/tests/ -v         # 119 tests
python3 -m pytest download-proxy/tests/ -k "search" -v  # Search-specific tests
```

### Sync to Container
```bash
podman cp download-proxy/src/ qbittorrent-proxy:/app/src/
```

## Merge Search Service

FastAPI app running **inside** `qbittorrent-proxy` on port **78086**.

- Searches **RuTracker**, **Kinozal**, **NNMClub** in parallel with deduplication
- Download proxy intercepts tracker URLs, fetches with auth cookies
- Dashboard at `http://localhost:78086/`

Key files:
- `download-proxy/src/api/__init__.py` — FastAPI app setup
- `download-proxy/src/api/routes.py` — REST endpoints
- `download-proxy/src/merge_service/search.py` — search orchestration
- `download-proxy/src/merge_service/deduplicator.py` — result dedup
- `download-proxy/src/merge_service/enricher.py` — quality detection

## Plugin System

`plugins/` has 35+ plugins. `install-plugin.sh` manages 12:
`eztv jackett limetorrents piratebay solidtorrents torlock torrentproject torrentscsv rutracker rutor kinozal nnmclub`

Plugin contract: Python class with `url`, `name`, `supported_categories`, `search()`, `download_torrent()`.
Installed to `config/qBittorrent/nova3/engines/` inside container.

## Environment Variables

Priority: shell env → `./.env` → `~/.qbit.env` → container env.

Key: `RUTRACKER_USERNAME/PASSWORD`, `KINOZAL_USERNAME/PASSWORD`, `NNMCLUB_COOKIES`, `QBITTORRENT_DATA_DIR` (`/mnt/DATA`), `PUID/PGID` (`1000`).

## Code Conventions

- **Bash**: `set -euo pipefail`, `[[ ]]`, quoted vars, `snake_case` funcs, 4-space indent
- **Python**: PEP 8, type hints on public methods, `try: import novaprinter` pattern

## Gotchas

- `run-all-tests.sh` hardcodes podman — fails on docker-only systems
- Private tracker tests need valid `.env` credentials + sometimes CAPTCHA
- Empty root files (`CONFIG`, `SCRIPT`, `EOF`) may be referenced — don't remove
- `webui-bridge.py` port is 78666, not 78085
- No CI pipeline, no linter config — only `bash -n` and `py_compile` validate
