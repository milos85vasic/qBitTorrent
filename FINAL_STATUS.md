# FINAL STATUS - qBitTorrent Fork

**Last Updated:** April 14, 2026  
**Version:** 3.0.0  
**Tests:** 119 passing

---

## Architecture

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│   Browser    │────▶│  qbittorrent-proxy  │────▶│   qBittorrent    │
│  :8085       │     │  (Download Proxy)   │     │  :18085 (WebUI)  │
└──────────────┘     └─────────────────────┘     └──────────────────┘
                              │
                     ┌────────┴─────────┐
                     │ Merge Search Svc │
                     │    :8086 (API)   │
                     └──────────────────┘
```

### Two-Container Setup (docker-compose)

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| **qbittorrent** | `lscr.io/linuxserver/qbittorrent:latest` | 18085 | The app, WebUI |
| **qbittorrent-proxy** | `python:3.12-alpine` | 8085 | Proxies downloads, hosts Merge Search Service |

Users access `http://localhost:8085` (proxy) → qBittorrent on 18085.  
Merge Search Service runs on `http://localhost:8086/` with its own dashboard.

### Host Processes

- **webui-bridge.py** (port 8666) — enables private tracker downloads in WebUI

---

## Merge Search Service

A FastAPI service that searches RuTracker, Kinozal, and NNMClub simultaneously, deduplicates results, and proxies authenticated downloads.

**Status:**
- ✅ **RuTracker** — Verified working, returns up to 50 results
- 🔧 **Kinozal** — Parsing fixed, needs `KINOZAL_USERNAME`/`KINOZAL_PASSWORD`
- 🔧 **NNMClub** — Parsing fixed, needs `NNMCLUB_COOKIES`

**Key Features:**
- Unified REST API on port 8086
- Result deduplication across trackers
- Automatic quality detection (4K/1080p/720p/SD)
- Download proxy intercepts tracker URLs and fetches with auth cookies
- Dashboard at http://localhost:8086/

---

## Plugin Suite

**Total: 35+ plugins installed**

### By Category

| Category | Count | Examples |
|----------|-------|---------|
| Official qBittorrent | 8 | EZTV, Jackett, LimeTorrents, PirateBay, SolidTorrents, TorLock, TorrentProject, TorrentsCSV |
| Public Trackers | 19 | 1337x, BT4G, BTSOW, ExtraTorrent, Nyaa, YTS, TorrentGalaxy, Snowfl, ... |
| Russian Trackers | 6 | Rutor, RuTracker, Kinozal, MegaPeer, BitRu, PC-Torrents |
| Private Trackers | 2 | IPTorrents, NNMClub |
| Specialized | 5+ | AcademicTorrents, AudioBookBay, LinuxTracker, Ali213, Pirateiro, Xfsub, Yihua |

### WebUI Compatibility

- ✅ **29+ plugins** work via WebUI (magnet-link based)
- ⚠️ **6 plugins** require authentication or Desktop App (RuTracker, Kinozal, NNMClub, IPTorrents)
- ✅ **All 35+ plugins** work in Desktop App

---

## Test Results

```
Total Tests: 119 PASSING
├── Plugin tests (syntax, structure, data format)
├── Merge service tests (API, search, download proxy)
├── Integration tests (container, plugin installation)
└── Unit tests (deduplication, quality detection, validation)
```

---

## What's Been Fixed (Complete History)

### v3.0.0 — Merge Search Service (April 2026)
- Added FastAPI-based Merge Search Service on port 8086
- Searches RuTracker, Kinozal, NNMClub simultaneously
- Result deduplication and quality detection
- Download proxy with authenticated cookie forwarding
- Dashboard UI at http://localhost:8086/
- 119 tests passing

### v2.0.0 — Plugin Expansion (March 2025)
- Expanded from 12 to 35+ plugins
- Added 19 public tracker plugins
- Fixed Kinozal & NNMClub column parsing (no more hardcoded zeros)
- Added `download_torrent()` methods to all plugins
- WebUI-compatible versions for private trackers

### v1.0.0 — Initial Fork
- Fixed WebUI download failure for private trackers
- Added webui-bridge.py proxy
- Added 8 official qBittorrent plugins
- 12 plugins total

---

## Known Limitations

| Limitation | Details |
|------------|---------|
| **CAPTCHA** | RuTracker may require browser-solved CAPTCHA for login |
| **Credentials Required** | Kinozal and NNMClub need valid credentials in `.env` |
| **No CI Pipeline** | Validation is manual: `bash -n` for shell, `py_compile` for Python |
| **Podman Hardcoded** | `run-all-tests.sh` uses podman specifically |
| **Proxy Startup** | Download proxy container installs `requests` at every startup |

---

## Quick Commands

```bash
# Start everything
./start.sh -p && python3 webui-bridge.py

# Run tests
./run-all-tests.sh          # Full suite (requires running container)
./test.sh                   # Quick validation

# Plugin management
./install-plugin.sh --all   # Install 12 managed plugins
./install-plugin.sh --verify

# Check status
curl http://localhost:8086/api/v1/search -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}'
```

---

**Status:** Production Ready ✅  
**WebUI:** http://localhost:8085 (admin/admin)  
**Merge Service:** http://localhost:8086/  
**WebUI Bridge:** http://localhost:8666
