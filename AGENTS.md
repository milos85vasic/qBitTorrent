# AGENTS.md

## Critical Constraints

- **WebUI credentials `admin`/`admin` are hardcoded** in `start.sh` config generation, `docker-compose.yml`, and multiple scripts. Do not change them.
- **Never commit `.env`** — it contains tracker credentials. `.env.example` is the template.

## Architecture

Two-container setup via `docker-compose.yml`:

- **qbittorrent** (`lscr.io/linuxserver/qbittorrent:latest`) — the app, WebUI on port **18085**
- **download-proxy** (`python:3.12-alpine`) — proxies downloads, exposes port **8085** to the host

Users access `http://localhost:8085` (proxy), which forwards to qBittorrent on 18085.

`webui-bridge.py` is a **separate host process** (port **8666**) that enables private tracker downloads in WebUI. It is NOT one of the containers — run it manually: `python3 webui-bridge.py`.

Container runtime is **auto-detected** (podman preferred over docker) in all shell scripts.

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

## Code Conventions

- **Bash**: `set -euo pipefail`, `[[ ]]` conditionals, quoted variables, `snake_case` functions, `UPPER_CASE` constants, 4-space indent. Scripts use shared color-print helpers (`print_info`, `print_success`, `print_warning`, `print_error`).
- **Python**: PEP 8, type hints on public methods, `try: import novaprinter` pattern (optional dependency). No `requirements.txt` at root — only `tests/requirements.txt` (pytest, requests, responses, pytest-cov).

## Gotchas

- `run-all-tests.sh` hardcodes **podman** commands — will fail on docker-only systems.
- Private tracker tests need valid credentials in `.env` and sometimes a browser-solved CAPTCHA (RuTracker).
- `.ruff_cache/` is **not in `.gitignore`** — it should be.
- Several empty root files exist (`CONFIG`, `SCRIPT`, `EOF`) — do not remove, they may be referenced.
- `webui-bridge.py` default port is 8666, not 8085 or 18085.
- The proxy container runs `start-proxy.sh` which installs `requests` at startup.
- Plugin install destination: `config/qBittorrent/nova3/engines/` (not `plugins/`).
