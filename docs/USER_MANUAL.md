# qBitTorrent-Fixed User Manual

## Complete Guide to Using All 12 Search Plugins

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Plugin Overview](#plugin-overview)
3. [Configuration](#configuration)
4. [Using the WebUI](#using-the-webui)
5. [Using Private Trackers](#using-private-trackers)
6. [Troubleshooting](#troubleshooting)
7. [Testing](#testing)
8. [FAQ](#faq)

---

## Quick Start

### 1. Installation

```bash
# Clone and setup
git clone https://github.com/yourusername/qBitTorrent-Fixed.git
cd qBitTorrent-Fixed

# Run automated setup
./setup.sh

# Configure credentials (optional, for private trackers)
vim .env
```

### 2. Start Everything

```bash
# Terminal 1: Start qBittorrent
./start.sh

# Terminal 2: Start WebUI Bridge (for private trackers)
python3 webui-bridge.py

# Access WebUI
http://localhost:8085
# Login: admin / admin
```

### 3. Verify Installation

```bash
# Run all tests
./run-all-tests.sh

# Check plugin status
python3 tests/final_verification.py
```

---

## Plugin Overview

### Public Trackers (9 plugins)

These work immediately without configuration:

| Plugin | Content Type | WebUI | Magnet Links | Notes |
|--------|--------------|-------|--------------|-------|
| **The Pirate Bay** | General | ✅ | ✅ | Most popular |
| **EZTV** | TV Shows | ✅ | ✅ | Best for TV |
| **Rutor** | Russian | ✅ | ✅ | Russian content |
| **LimeTorrents** | General | ✅ | ❌ | Verified torrents |
| **Solid Torrents** | General | ✅ | ✅ | Fast search |
| **TorrentProject** | General | ✅ | ❌ | Comprehensive |
| **torrents-csv** | General | ✅ | ✅ | Open database |
| **TorLock** | General | ✅ | ✅ | No fake torrents |
| **Jackett** | Meta | ✅ | ❌ | Aggregates multiple |

### Private Trackers (3 plugins)

These require credentials:

| Plugin | Content Type | Credentials Required | Best For |
|--------|--------------|---------------------|----------|
| **RuTracker** | Russian | Username/Password | Russian content |
| **Kinozal** | Movies/TV | Username/Password | Movies and TV |
| **NNMClub** | General | Cookies | General content |

---

## Configuration

### Setting Up Credentials

Edit `.env` file:

```bash
# Public trackers (no configuration needed)

# Private trackers (optional, for WebUI support)
RUTRACKER_USERNAME=your_rutracker_username
RUTRACKER_PASSWORD=your_rutracker_password

KINOZAL_USERNAME=your_kinozal_username
KINOZAL_PASSWORD=your_kinozal_password

# For NNMClub, get cookies from browser:
# 1. Login to nnmclub.to in browser
# 2. Open developer tools (F12)
# 3. Go to Application/Storage > Cookies
# 4. Copy uid and pass cookies
NNMCLUB_COOKIES="uid=123456; pass=abcdef1234567890abcdef1234567890"
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QBITTORRENT_DATA_DIR` | `/mnt/DATA` | Download directory |
| `WEBUI_PORT` | `8085` | WebUI port |
| `WEBUI_USERNAME` | `admin` | WebUI login |
| `WEBUI_PASSWORD` | `admin` | WebUI password |
| `BRIDGE_PORT` | `8666` | WebUI Bridge port |

---

## Using the WebUI

### Basic Search

1. Open `http://localhost:8085`
2. Login with admin/admin
3. Click "Search" tab
4. Enter search term (e.g., "ubuntu")
5. Select plugin from dropdown
6. Click "Search"

### Downloading Torrents

#### Public Trackers (PirateBay, EZTV, etc.)

1. Search for content
2. Click download icon (⬇️)
3. Torrent appears in Transfer list
4. Download starts automatically

#### Private Trackers (RuTracker, Kinozal, NNMClub)

**Option A: Using WebUI Bridge (Recommended)**

1. Start WebUI Bridge: `python3 webui-bridge.py`
2. Search for content
3. Click download icon
4. Bridge handles authentication automatically

**Option B: Using Desktop App**

1. Install plugins locally: `./install-plugin.sh --local --all`
2. Open qBittorrent Desktop App
3. Go to View → Search Engine
4. Downloads work without bridge

**Option C: Manual Download**

1. Search in WebUI
2. Note the torrent name
3. Go to tracker website directly
4. Download .torrent file
5. Upload to qBittorrent WebUI

---

## Using Private Trackers

### RuTracker

**Requirements:**
- Active account on rutracker.org
- Valid username and password

**Setup:**
```bash
# Add to .env
RUTRACKER_USERNAME=your_username
RUTRACKER_PASSWORD=your_password

# Restart container
./restart.sh
```

**Usage:**
1. Enable RuTracker in Search Plugins
2. Search for Russian content
3. Click download (works with WebUI Bridge)

**Tips:**
- RuTracker has the best Russian content
- Very reliable for software and movies
- Works best with WebUI Bridge

### Kinozal

**Requirements:**
- Active account on kinozal.tv
- Valid username and password

**Setup:**
```bash
# Add to .env
KINOZAL_USERNAME=your_username
KINOZAL_PASSWORD=your_password
```

**Usage:**
1. Enable Kinozal in Search Plugins
2. Search for movies/TV shows
3. Works with WebUI Bridge

### NNMClub

**Requirements:**
- Active account on nnmclub.to
- Cookie-based authentication

**Setup:**
```bash
# Get cookies from browser
# Add to .env
NNMCLUB_COOKIES="uid=your_uid; pass=your_pass_hash"
```

**Getting Cookies:**
1. Login to nnmclub.to in browser
2. Press F12 (Developer Tools)
3. Go to Application/Storage → Cookies
4. Find `uid` and `pass` cookies
5. Copy values to .env

---

## Troubleshooting

### Issue: Plugin Not Showing in WebUI

**Solution:**
```bash
# Restart container
./restart.sh

# Hard refresh browser (Ctrl+Shift+R)
```

### Issue: Download Doesn't Start (Private Trackers)

**Cause:** WebUI bypasses authentication

**Solutions:**

1. **Use WebUI Bridge (Recommended)**
   ```bash
   python3 webui-bridge.py
   ```

2. **Use Desktop App**
   ```bash
   ./install-plugin.sh --local --all
   # Then use Desktop App
   ```

3. **Check Credentials**
   ```bash
   cat .env
   # Verify username/password are correct
   ```

### Issue: Search Returns No Results

**Check:**
1. Internet connection
2. Plugin is enabled
3. Try different search terms
4. Check container logs: `podman logs qbittorrent`

### Issue: Column Data Shows Zeros

**Status:** Fixed in this version

All plugins now return real data for seeds, leech, and size.

### Issue: Container Won't Start

**Solution:**
```bash
# Full reset
./stop.sh -r
podman system prune -f
./start.sh
```

---

## Testing

### Run All Tests

```bash
# Comprehensive test suite
./run-all-tests.sh

# Individual tests
python3 tests/comprehensive_test.py
python3 tests/final_verification.py
python3 tests/test_all_plugins.py
```

### Test Results

Tests cover:
- ✅ Plugin structure validation
- ✅ Search functionality
- ✅ Download functionality
- ✅ Column data validation (seeds, leech, size)
- ✅ Authentication handling

Expected result: **100% success rate**

---

## FAQ

### Q: Why create a fork instead of fixing upstream?

**A:** The WebUI limitation is in qBittorrent's core design. This fork provides a working solution while maintaining compatibility.

### Q: Do I need to run WebUI Bridge?

**A:** Only if you want to use private trackers (RuTracker, Kinozal, NNMClub) in WebUI. Public trackers work without it.

### Q: Is this legal?

**A:** The software itself is legal (Apache 2.0 license). Usage depends on your local laws and the content you download.

### Q: Will this break with qBittorrent updates?

**A:** The plugin API is stable. Updates to qBittorrent should not break functionality.

### Q: Can I add more plugins?

**A:** Yes! See `docs/PLUGINS.md` for adding custom plugins.

### Q: Why does RuTracker work in Desktop App but not WebUI?

**A:** Desktop App uses nova2dl.py with authentication. WebUI sends URLs directly without auth. The WebUI Bridge fixes this.

### Q: How do I update plugins?

**A:**
```bash
./install-plugin.sh --all
./restart.sh
```

### Q: Where are downloads saved?

**A:** Default: `/mnt/DATA` (configurable in `.env`)

Structure:
```
/mnt/DATA/
├── Incomplete/          # Partial downloads
├── Torrents/
│   ├── All/            # All .torrent files
│   └── Completed/      # Completed .torrent files
└── [completed files]   # Finished downloads
```

---

## Advanced Topics

### Custom Plugin Development

See `docs/PLUGIN_DEVELOPMENT.md` for creating custom search plugins.

### WebUI Bridge Configuration

Edit `webui-bridge.py`:
```python
QBITTORRENT_HOST = 'localhost'  # Change if remote
QBITTORRENT_PORT = 8085         # WebUI port
BRIDGE_PORT = 8666              # Bridge port
```

### Backup and Restore

**Backup:**
```bash
# Config
tar czf qbittorrent-backup-$(date +%Y%m%d).tar.gz config/

# Plugins
tar czf plugins-backup-$(date +%Y%m%d).tar.gz plugins/
```

**Restore:**
```bash
tar xzf qbittorrent-backup-YYYYMMDD.tar.gz
tar xzf plugins-backup-YYYYMMDD.tar.gz
./restart.sh
```

---

## Support

### Getting Help

1. **Documentation:** Read all docs in `docs/` folder
2. **Tests:** Run `./run-all-tests.sh` to diagnose issues
3. **Logs:** Check `podman logs qbittorrent`
4. **Issues:** Report on GitHub

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Run tests: `./run-all-tests.sh`
5. Submit pull request

---

## Version History

### v2.0.0 (Current)
- ✅ All 12 plugins working
- ✅ WebUI Bridge for private trackers
- ✅ Comprehensive test suite
- ✅ Full documentation

### v1.0.0
- Initial release
- 4 Russian trackers

---

**Last Updated:** March 2025  
**Version:** 2.0.0  
**License:** Apache 2.0
