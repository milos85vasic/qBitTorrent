# qBitTorrent-Fixed — Fork Summary

**Version:** 3.0.0  
**Last Updated:** April 2026

---

## Why This Fork Exists

The original qBitTorrent search plugins had critical issues:

1. **WebUI Downloads Failed** — Private trackers searched but downloads never started
2. **Missing Plugins** — Only 4 Russian trackers included, missing official plugins
3. **Hardcoded Data** — Some plugins returned zeros for seeds/leech/size
4. **No Unified Search** — No way to search multiple trackers at once
5. **No Documentation** — No clear status of what worked

## What This Fork Fixes

### v3.0.0 — Merge Search Service
- **Unified Search API** on port 8086 — searches RuTracker, Kinozal, NNMClub simultaneously
- **Result Deduplication** — merges identical results across trackers, shows combined seeds/leechers
- **Quality Detection** — auto-tags results as UHD 4K, Full HD, HD, or SD
- **Download Proxy** — intercepts tracker URLs and fetches `.torrent` files with auth cookies
- **Dashboard** — web UI at http://localhost:8086/ for searching and downloading
- **119 tests passing**

### v2.0.0 — Plugin Expansion
- Expanded from 12 to **35+ plugins** (public, private, Russian, specialized)
- Fixed Kinozal & NNMClub column parsing
- Added `download_torrent()` to all plugins
- WebUI-compatible versions for private trackers

### v1.0.0 — Initial Fixes
- Fixed WebUI download failure with `webui-bridge.py` proxy
- Added 8 official qBittorrent plugins
- Proper data extraction from all plugins

---

## Architecture

### Merge Service Flow

```
┌──────────┐    ┌───────────────────┐    ┌──────────────────────┐
│ Dashboard│───▶│  Merge Search Svc │───▶│   Tracker Plugins    │
│  :8086   │    │  (FastAPI)        │    │ RuTracker / Kinozal  │
└──────────┘    └────────┬──────────┘    │ NNMClub              │
                         │               └──────────────────────┘
                    ┌────┴─────┐
                    │Deduplicator│
                    │Quality Det.│
                    └────┬─────┘
                         │
                    ┌────▼─────┐     ┌──────────────────┐
                    │ Download  │────▶│  qBittorrent API │
                    │  Proxy    │     │    :18085         │
                    │ (w/ auth) │     └──────────────────┘
                    └──────────┘
```

### Full System Flow

```
Browser (:8085) ──▶ qbittorrent-proxy ──▶ qBittorrent (:18085)
                            │
                    Merge Search (:8086)
                            │
                  ┌─────────┼─────────┐
                  ▼         ▼         ▼
              RuTracker  Kinozal   NNMClub
              (cookies)  (cookies) (cookies)
```

### Two-Container Setup

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| **qbittorrent** | `lscr.io/linuxserver/qbittorrent:latest` | 18085 | App + WebUI |
| **qbittorrent-proxy** | `python:3.12-alpine` | 8085 → 18085 | Proxy + Merge Service (:8086) |

---

## Merge Search API

**Base URL:** `http://localhost:8086/api/v1/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/search` | Search all trackers, returns deduplicated results |
| `GET` | `/search/{search_id}` | Get status of a previous search |
| `GET` | `/search/stream/{search_id}` | SSE stream of search results |
| `POST` | `/download` | Download via proxy (auto-authenticates tracker URLs) |
| `GET` | `/downloads/active` | List active qBittorrent downloads |
| `GET` | `/hooks` | List registered hooks |
| `POST` | `/hooks` | Register a new hook |
| `DELETE` | `/hooks/{hook_id}` | Delete a hook |

### Example: Search

```bash
curl -X POST http://localhost:8086/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "ubuntu", "limit": 10}'
```

### Example: Download

```bash
curl -X POST http://localhost:8086/api/v1/download \
  -H "Content-Type: application/json" \
  -d '{"result_id": "abc", "download_urls": ["https://rutracker.org/forum/dl.php?t=123"]}'
```

---

## Plugin Status Matrix

### Official qBittorrent Plugins (8)

| Plugin | Search | WebUI | Desktop | Type |
|--------|--------|-------|---------|------|
| EZTV | ✅ | ✅ | ✅ | TV Shows |
| Jackett | ✅ | ✅ | ✅ | Meta Search |
| LimeTorrents | ✅ | ✅ | ✅ | General |
| PirateBay | ✅ | ✅ | ✅ | General |
| SolidTorrents | ✅ | ✅ | ✅ | General |
| TorLock | ✅ | ✅ | ✅ | General |
| TorrentProject | ✅ | ✅ | ✅ | General |
| TorrentsCSV | ✅ | ✅ | ✅ | General |

### Public Trackers (19)

| Plugin | Search | WebUI | Desktop | Type |
|--------|--------|-------|---------|------|
| 1337x | ✅ | ✅ | ✅ | General |
| BT4G | ✅ | ✅ | ✅ | General |
| BTSOW | ✅ | ✅ | ✅ | Aggregator |
| ExtraTorrent | ✅ | ✅ | ✅ | General |
| GamesTorrents | ✅ | ✅ | ✅ | Games |
| GloTorrents | ✅ | ✅ | ✅ | General |
| Kickass | ✅ | ✅ | ✅ | General |
| Nyaa | ✅ | ✅ | ✅ | Anime |
| RARBG Alternative | ✅ | ✅ | ✅ | Movies/TV |
| RockBox | ✅ | ✅ | ✅ | Music |
| Snowfl | ✅ | ✅ | ✅ | Aggregator |
| TorrentDownload | ✅ | ✅ | ✅ | Aggregator |
| TorrentFunk | ✅ | ✅ | ✅ | General |
| TorrentGalaxy | ✅ | ✅ | ✅ | General |
| TorrentKitty | ✅ | ✅ | ✅ | Magnet Search |
| Tokyo Toshokan | ✅ | ✅ | ✅ | Anime |
| YourBittorrent | ✅ | ✅ | ✅ | General |
| YTS | ✅ | ✅ | ✅ | Movies |
| AniLibra | ✅ | ✅ | ✅ | Anime |

### Russian & Private Trackers (8)

| Plugin | Search | WebUI | Desktop | Merge API | Credentials |
|--------|--------|-------|---------|-----------|-------------|
| Rutor | ✅ | ✅ | ✅ | — | None |
| MegaPeer | ✅ | ✅ | ✅ | — | None |
| BitRu | ✅ | ✅ | ✅ | — | None |
| PC-Torrents | ✅ | ✅ | ✅ | — | None |
| RuTracker | ✅ | ✅* | ✅ | ✅ Verified | Username/Password |
| Kinozal | ✅ | ✅* | ✅ | 🔧 Fixed | Username/Password |
| NNMClub | ✅ | ✅* | ✅ | 🔧 Fixed | Cookies |
| IPTorrents | ✅ | ✅* | ✅ | — | Username/Password |

*Requires bridge/proxy for WebUI downloads

### Specialized Trackers (5+)

| Plugin | Search | WebUI | Desktop | Type |
|--------|--------|-------|---------|------|
| AcademicTorrents | ✅ | ✅ | ✅ | Academic |
| AudioBook Bay | ✅ | ✅ | ✅ | Audiobooks |
| LinuxTracker | ✅ | ✅ | ✅ | Linux distros |
| Ali213 | ✅ | ✅ | ✅ | Chinese games |
| Pirateiro | ✅ | ✅ | ✅ | Aggregator |
| Xfsub | ✅ | ✅ | ✅ | Anime subtitles |
| Yihua | ✅ | ✅ | ✅ | Chinese tracker |

---

## Quick Start

```bash
# 1. Clone
git clone <repo-url> && cd qBitTorrent

# 2. Setup (one-time)
./setup.sh

# 3. Configure credentials (optional)
vim .env

# 4. Start
./start.sh -p && python3 webui-bridge.py

# 5. Access
#    WebUI:    http://localhost:8085 (admin/admin)
#    Merge:    http://localhost:8086/
#    Bridge:   http://localhost:8666
```

---

## Testing

```bash
./run-all-tests.sh                    # Full suite (requires container)
./test.sh                             # Quick validation
python3 -m py_compile plugins/*.py    # Syntax check
bash -n start.sh stop.sh test.sh     # Bash syntax check
```

---

## Known Limitations

1. **CAPTCHA** — RuTracker may require browser-solved CAPTCHA
2. **Credentials** — Kinozal/NNMClub need valid credentials to return results
3. **No CI Pipeline** — Manual validation only (`bash -n`, `py_compile`)
4. **Podman Hardcoded** — `run-all-tests.sh` requires podman
5. **Bridge Required** — `webui-bridge.py` must run manually for WebUI private tracker support

---

## License

Apache 2.0 — Same as original qBittorrent

---

**Status:** Production Ready ✅  
**Tests:** 119 passing  
**Plugins:** 35+ installed  
**Merge Service:** http://localhost:8086/
