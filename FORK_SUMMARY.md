# qBitTorrent-Fixed - Fork Summary

## Why This Fork Exists

The original qBitTorrent search plugins had several critical issues:

1. **WebUI Downloads Failed** - Private trackers (RuTracker, Kinozal, NNMClub) would search successfully but downloads never started
2. **Missing Plugins** - Only 4 Russian trackers were included, missing 8 official qBittorrent plugins
3. **Hardcoded Data** - Some plugins returned zeros for seeds/leech/size instead of real data
4. **No Documentation** - No clear explanation of what worked and what didn't

## What This Fork Fixes

### ✅ Complete Plugin Suite (12 Total)

**Added 8 Official Plugins:**
- EZTV - TV shows
- Jackett - Meta search engine
- LimeTorrents - General content
- The Pirate Bay - General content
- Solid Torrents - General content
- TorLock - General content
- TorrentProject - General content
- torrents-csv - General content

**Plus Original 4 Russian Trackers:**
- RuTracker - Russian content
- Rutor - Russian content
- Kinozal - Movies/TV
- NNMClub - General content

### ✅ Fixed All Issues

#### 1. WebUI Download Issue - SOLVED

**Root Cause:** qBittorrent WebUI sends download URLs directly to `/api/v2/torrents/add` which bypasses the plugin's `download_torrent()` method. Private trackers require authentication (cookies/session) which only works through `nova2dl.py`.

**Solution:** 
- Created `webui-bridge.py` - A proxy server that intercepts WebUI download requests
- For private trackers, it uses `nova2dl.py` with proper authentication
- For public trackers, it proxies the request normally

#### 2. Hardcoded Data - FIXED

**Problem:** Kinozal and NNMClub returned zeros for seeds/leech/size.

**Solution:** Updated plugins with proper regex parsers to extract real data from HTML.

#### 3. Missing Download Methods - ADDED

All plugins now have proper `download_torrent()` methods that:
- Handle magnet links correctly
- Download .torrent files for HTTP URLs
- Return proper format: `filepath url`

## Plugin Status Matrix

| Plugin | Search | WebUI Download | Desktop Download | Type |
|--------|--------|----------------|------------------|------|
| **RuTracker** | ✅ | ✅* | ✅ | Private |
| **PirateBay** | ✅ | ✅ | ✅ | Public |
| **EZTV** | ✅ | ✅ | ✅ | Public |
| **Rutor** | ✅ | ✅ | ✅ | Public |
| **LimeTorrents** | ✅ | ✅ | ✅ | Public |
| **SolidTorrents** | ✅ | ✅ | ✅ | Public |
| **TorrentProject** | ✅ | ✅ | ✅ | Public |
| **torrents-csv** | ✅ | ✅ | ✅ | Public |
| **TorLock** | ✅ | ✅ | ✅ | Public |
| **Jackett** | ✅ | ✅ | ✅ | Meta |
| **Kinozal** | ✅ | ✅* | ✅ | Private |
| **NNMClub** | ✅ | ✅* | ✅ | Private |

*Requires credentials in `.env` file for WebUI

## Architecture

### How WebUI Downloads Work Now

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   WebUI     │────▶│  webui-bridge   │────▶│   nova2dl.py     │
│  (User)     │     │   (Port 8666)   │     │ (Authentication) │
└─────────────┘     └─────────────────┘     └──────────────────┘
                              │                        │
                              ▼                        ▼
                       ┌─────────────┐        ┌──────────────┐
                       │ qBittorrent │        │   Tracker    │
                       │   (API)     │        │ (RuTracker)  │
                       └─────────────┘        └──────────────┘
```

**Without Bridge (Default):**
```
WebUI ──▶ qBittorrent API ──▶ Direct Download (FAILS for private trackers)
```

**With Bridge (This Fork):**
```
WebUI ──▶ Bridge ──▶ nova2dl.py ──▶ Authenticated Download (WORKS!)
```

## Files Added/Modified

### New Files
- `webui-bridge.py` - WebUI proxy for private tracker support
- `setup.sh` - Comprehensive setup script
- `FORK_SUMMARY.md` - This file
- Multiple test scripts
- Comprehensive documentation

### Modified Plugins
All 12 plugins updated with:
- Proper `download_torrent()` methods
- Correct column data extraction
- WebUI compatibility

## Quick Start

```bash
# 1. Clone this fork
git clone https://github.com/yourusername/qBitTorrent-Fixed.git
cd qBitTorrent-Fixed

# 2. Run setup
./setup.sh

# 3. Configure credentials (optional, for private trackers)
vim .env
# Add: RUTRACKER_USERNAME=your_user
# Add: RUTRACKER_PASSWORD=your_pass

# 4. Start WebUI Bridge (for private tracker support)
python3 webui-bridge.py

# 5. Access WebUI
http://localhost:8085
```

## Testing

```bash
# Test all plugins
python3 tests/test_all_plugins.py

# Verify installation
./install-plugin.sh --verify

# Test specific functionality
python3 tests/final_verification.py
```

## Known Limitations

1. **WebUI Bridge Required for Private Trackers**
   - Must run `python3 webui-bridge.py` alongside qBittorrent
   - Bridge runs on port 8666

2. **Credentials Required**
   - Private trackers need valid credentials in `.env`
   - Public trackers work without configuration

3. **Magnet Links Work Best**
   - PirateBay, EZTV, SolidTorrents return magnet links
   - These work universally without bridge

## Migration from Original

If you were using the original qBitTorrent setup:

```bash
# Backup your config
cp -r config/qBittorrent config/qBittorrent.backup

# Copy this fork
cp -r qBitTorrent-Fixed/* /path/to/your/qbittorrent/

# Reinstall plugins
./install-plugin.sh --all

# Restart container
./restart.sh
```

## Contributing

This fork welcomes contributions:
- Additional plugins
- Better WebUI integration
- Improved documentation
- Bug fixes

## License

Apache 2.0 - Same as original qBittorrent

## Credits

- Original qBittorrent team
- Original plugin authors
- This fork's fixes and documentation

---

**Status:** Production Ready ✅  
**Version:** 2.0.0  
**Last Updated:** March 2025
