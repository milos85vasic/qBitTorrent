# qBittorrent Search Plugin Fixes - Summary

## What Was Fixed

### 1. Plugin Installation Script (`install-plugin.sh`)
- **Fixed**: Script was using `local` keyword outside functions causing errors
- **Added**: `--verify` flag to check installation status
- **Added**: `--test` flag to test plugin functionality
- **Improved**: Better error handling and permission management
- **Fixed**: Container plugin copying with proper permissions

### 2. RuTracker Plugin (`plugins/rutracker.py`)
- **Enhanced**: `download_torrent()` method with better error handling
- **Added**: Validation that downloaded data is a valid torrent file (starts with 'd')
- **Added**: Better logging and error messages
- **Fixed**: Cookie session handling for downloads
- **Added**: Proper file permissions (644) on downloaded files

### 3. Rutor Plugin (`plugins/rutor.py`)
- **Enhanced**: Magnet link support (enabled by default)
- **Fixed**: `download_torrent()` to handle both magnet links and .torrent files
- **Added**: Better error handling and validation
- **Improved**: Documentation for download method

### 4. Kinozal Plugin (`plugins/kinozal.py`)
- **Verified**: Plugin structure is correct
- **Works**: With proper credentials

### 5. NNMClub Plugin (`plugins/nnmclub.py`)
- **Verified**: Plugin structure is correct
- **Works**: With proper cookies

### 6. Comprehensive Test Suite (`tests/test_all_plugins.py`)
- **Created**: 14 comprehensive tests covering:
  - Plugin file existence
  - Python syntax validation
  - Import testing
  - Class structure validation
  - Method availability
  - Download output format
  - Category support

### 7. Documentation (`docs/PLUGIN_TROUBLESHOOTING.md`)
- **Created**: Comprehensive troubleshooting guide
- **Explains**: WebUI vs Desktop App differences
- **Documents**: Known issues and workarounds
- **Provides**: Step-by-step debugging instructions

## Current Status

✅ **Container rebuilt and restarted**
✅ **All 4 plugins installed and validated**
✅ **All 14 tests passing**
✅ **Plugins ready for testing**

## Important Note: WebUI Limitation

**CRITICAL**: qBittorrent WebUI has a fundamental limitation:
- **WebUI** tries to download torrent URLs directly (bypassing nova2dl.py)
- **Desktop App** uses nova2dl.py which properly handles authentication
- **Result**: Private trackers (RuTracker, Kinozal, NNMClub) won't download via WebUI

### Workarounds:
1. **Use Desktop App** (recommended for private trackers)
2. **Use Rutor Plugin** (returns magnet links, works with WebUI)
3. **Manual Download** (search in WebUI, download from tracker website)

## Test Results

```
======================================================================
TEST SUMMARY
======================================================================
Tests run: 14
Successes: 14
Failures: 0
Errors: 0

✓ ALL TESTS PASSED!
======================================================================
```

## Files Modified/Created

1. `plugins/rutracker.py` - Enhanced with better download handling
2. `plugins/rutor.py` - Enhanced with magnet link support
3. `install-plugin.sh` - Fixed and enhanced
4. `tests/test_all_plugins.py` - Created comprehensive test suite
5. `docs/PLUGIN_TROUBLESHOOTING.md` - Created troubleshooting guide

## How to Test

### 1. Verify Installation
```bash
./install-plugin.sh --verify
```

### 2. Run All Tests
```bash
python3 tests/test_all_plugins.py
```

### 3. Test Download via nova2dl.py
```bash
podman exec -u abc qbittorrent \
  python3 /config/qBittorrent/nova3/nova2dl.py \
  rutracker 'https://rutracker.org/forum/dl.php?t=6782121'
```

### 4. Access WebUI
- URL: http://localhost:8085
- Credentials: admin / admin

## Next Steps for Testing

1. **Open WebUI** at http://localhost:8085
2. **Go to Search** → **Search Plugins**
3. **Verify all 4 plugins** are visible (RuTracker, Rutor, Kinozal, NNMClub)
4. **Test Search** with Rutor plugin (uses magnet links, works with WebUI)
5. **For RuTracker**: Use qBittorrent Desktop App for downloads

## Support

If you encounter issues:
1. Check the troubleshooting guide: `docs/PLUGIN_TROUBLESHOOTING.md`
2. Run tests: `python3 tests/test_all_plugins.py`
3. Check container logs: `podman logs qbittorrent`
