# qBitTorrent-Fixed

[![Tests](https://img.shields.io/badge/tests-331%20passing-success)](tests/)
[![Plugins](https://img.shields.io/badge/plugins-42-blue)](plugins/)
[![Merge Service](https://img.shields.io/badge/merge_service-FastAPI%20%3A7187-orange)](download-proxy/src/)
[![CI](https://img.shields.io/badge/ci-manual%20%28ci.sh%29-blueviolet)](ci.sh)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)

> **qBittorrent with unified multi-tracker search, 42 plugins, and a download proxy with authenticated tracker support.**

## Features

- **Merge Search Service** — FastAPI service (port 7187) that searches multiple trackers simultaneously, deduplicates results, and proxies authenticated downloads
- **42 Search Plugins** — Public, private, and specialized tracker plugins
- **Freeleech Protection** — IPTorrents freeleech results tagged `[free]`; non-freeleech never merges with other trackers
- **WebUI Download Fix** — Private tracker downloads work through the proxy bridge (auto-starts via systemd)
- **Dark Theme Dashboard** — Search UI at `http://localhost:7187/`
- **SSE Streaming** — Real-time search results as they arrive from each tracker
- **Hook System** — Configure webhooks triggered on search/download events
- **Manual CI Pipeline** — Secret leak detection, syntax checks, full test suite, container health (`./ci.sh`)
- **331 Tests Passing** — HTML parsers, API endpoints, quality detection, deduplication, hooks, validator, enricher, freeleech, CI infra

## Quick Start

```bash
git clone https://github.com/milos85vasic/qBitTorrent.git
cd qBitTorrent
cp .env.example .env
# Edit .env with tracker credentials
./setup.sh
./start.sh -p
./setup-webui-bridge-service.sh   # One-time: auto-start webui-bridge on boot
# Access:
#   qBittorrent WebUI:   http://localhost:7185
#   Download proxy:      http://localhost:7186
#   Merge Search + UI:   http://localhost:7187/
#   webui-bridge:        auto-started via systemd (port 7188)
# Login: admin / admin
```

## Architecture

```
                         ┌─────────────────────────┐
                         │      qbittorrent-proxy   │
                         │    (python:3.12-alpine)   │
  http://localhost:7186  │                           │
   ──────────────────────►│  Download Proxy (:7186)   │────► qBittorrent (:7185)
                          │                           │
   http://localhost:7187  │  Merge Search Service     │
   ──────────────────────►│  (FastAPI :7187)          │────► RuTracker / Kinozal / NNMClub / IPTorrents
                          │                           │
                          │  ┌─ download-proxy/src/ ─┐│
                          │  │  api/    merge_service/ ││
                          │  │  ui/     config/        ││
                          │  └────────────────────────┘│
                          └─────────────────────────┘

   systemd user service:
   webui-bridge  (:7188)  — auto-started, private tracker WebUI download support
```

Two containers via `docker-compose.yml` (both use `network_mode: host`):

| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| **qbittorrent** | `lscr.io/linuxserver/qbittorrent:latest` | 7185 | The qBittorrent app |
| **download-proxy** | `python:3.12-alpine` | 7186, 7187 | Download proxy + Merge Search API |

Container runtime is auto-detected (podman preferred over docker).

## Merge Search API

The merge service runs inside `qbittorrent-proxy` on port **7187**.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/search` | Search across multiple trackers |
| `GET` | `/api/v1/search/stream/{id}` | SSE stream of search results |
| `POST` | `/api/v1/download` | Download via authenticated proxy |
| `GET` | `/api/v1/downloads/active` | List active downloads |
| `GET` | `/api/v1/hooks` | List configured hooks |
| `POST` | `/api/v1/hooks` | Create a hook |
| `DELETE` | `/api/v1/hooks` | Delete a hook |
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/stats` | Service statistics |
| `GET` | `/` | Dashboard UI (dark theme) |

### How It Works

1. **Search** — `POST /api/v1/search` dispatches queries to enabled trackers (RuTracker, Kinozal, NNMClub, etc.)
2. **Deduplicate** — Tiered deduplication: exact hash → name+size → fuzzy similarity
3. **Enrich** — Metadata from OMDb, TMDB, TVMaze, AniList, MusicBrainz, OpenLibrary
4. **Quality Detect** — Automatically tags UHD 4K, Full HD, HD, SD
5. **Stream** — Results delivered via SSE as each tracker responds
6. **Download** — Authenticated tracker URLs intercepted, fetched with session cookies, uploaded as .torrent to qBittorrent

## Plugin System

### 35+ Plugins

**Public Trackers (19):** The Pirate Bay, EZTV, Rutor, LimeTorrents, Solid Torrents, TorrentProject, torrents-csv, TorLock, Jackett, 1337x, YTS, TorrentGalaxy, RARBG Alt, ExtraTorrent, TorrentFunk, BTSOW, TorrentKitty, GamesTorrents, RockBox

**Russian Trackers (6):** RuTracker (auth), Kinozal (auth), NNMClub (auth), MegaPeer, BitRu, PC-Torrents

**Anime Trackers (4):** Nyaa, Tokyo Toshokan, AniLibra, Xfsub

**Specialized (3):** AudioBook Bay, AcademicTorrents, LinuxTracker

**Private (1):** IPTorrents (auth)

### Managed Plugins (12)

`install-plugin.sh` manages: `eztv jackett limetorrents piratebay solidtorrents torlock torrentproject torrentscsv rutracker rutor kinozal nnmclub`

### Plugin Contract

Each plugin is a Python class with:
- Class attributes: `url`, `name`, `supported_categories`
- `search(self, what, cat='all')` — outputs via `novaprinter.print()`
- `download_torrent(self, url)` — returns magnet link or file path

## Testing

```bash
./run-all-tests.sh
./test.sh --all
python3 -m py_compile plugins/*.py
python3 -m pytest tests/unit/merge_service/ tests/integration/test_merge_api.py -v --import-mode=importlib
```

**119 tests passing** covering: HTML parsers, API endpoints, quality detection, deduplicator, hooks, validator, enricher.

## What's Included

```
plugins/                          # 35+ tracker plugins
├── eztv.py, piratebay.py, ...   # Individual tracker plugins
├── helpers.py                    # Shared utilities (build_magnet_link, etc.)
├── nova2.py                      # Search engine core
├── novaprinter.py                # Output formatting
├── socks.py                      # Proxy support
├── download_proxy.py             # Download proxy server
└── webui_compatible/             # WebUI variants for private trackers

download-proxy/src/               # Merge Search Service source
├── api/                          # FastAPI application
│   ├── __init__.py               # App factory, lifespan, health, stats
│   ├── routes.py                 # Search, download, streaming endpoints
│   ├── hooks.py                  # Webhook CRUD with JSON persistence
│   └── streaming.py              # SSE streaming support
├── merge_service/                # Core business logic
│   ├── search.py                 # SearchOrchestrator, data models
│   ├── deduplicator.py           # Tiered dedup (hash, name+size, fuzzy)
│   ├── enricher.py               # Metadata enrichment (OMDb, TMDB, etc.)
│   ├── validator.py              # Tracker HTTP/UDP scrape validation
│   ├── hooks.py                  # Hook execution engine
│   └── scheduler.py              # Scheduled search with persistence
├── config/                       # Configuration module
└── ui/templates/dashboard.html   # Dark theme dashboard

tests/
├── unit/merge_service/           # Unit tests for merge service
│   ├── test_html_parsers.py
│   ├── test_quality_detection.py
│   ├── test_deduplicator.py
│   ├── test_hooks.py
│   ├── test_validator.py
│   └── test_enricher.py
├── integration/
│   └── test_merge_api.py
└── ...                           # Plugin tests, e2e, UI automation
```

## Configuration

### Environment Variables

Edit `.env` (see `.env.example`):

```bash
RUTRACKER_USERNAME=your_username
RUTRACKER_PASSWORD=your_password
KINOZAL_USERNAME=your_username
KINOZAL_PASSWORD=your_password
NNMCLUB_COOKIES="uid=123456; pass=abc..."
IPTORRENTS_USERNAME=your_username
IPTORRENTS_PASSWORD=your_password
QBITTORRENT_DATA_DIR=/mnt/DATA
PUID=1000
PGID=1000
```

## Scripts

```bash
./setup.sh                    # One-time setup
./start.sh [-p] [-s] [-v]    # Start containers (-p pull images)
./stop.sh [-r] [--purge]      # Stop (-r remove, --purge clean images)
./install-plugin.sh --all     # Install 12 managed plugins
./run-all-tests.sh            # Full test suite
```

## Troubleshooting

```bash
# Plugin not showing in WebUI
./stop.sh -r && ./start.sh

# Private tracker download fails
python3 webui-bridge.py

# Merge service not responding
podman logs qbittorrent-proxy

# Sync updated source to container
podman cp download-proxy/src/. qbittorrent-proxy:/config/download-proxy/src/
podman restart qbittorrent-proxy
```

## Documentation

| Document | Description |
|----------|-------------|
| [User Manual](docs/USER_MANUAL.md) | Complete usage guide |
| [Plugin Status](PLUGIN_STATUS.md) | Compatibility matrix |
| [Troubleshooting](docs/PLUGIN_TROUBLESHOOTING.md) | Debug guide |
| [Fork Summary](FORK_SUMMARY.md) | Architecture & fixes |
| [Changelog](CHANGELOG.md) | Version history |

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Make changes
4. Run tests: `./run-all-tests.sh`
5. Commit and push: `git push origin feature-name`
6. Submit Pull Request

## License

Apache 2.0 — See [LICENSE](LICENSE)

---

**Version**: 3.0.0
**Last Updated**: April 2026
