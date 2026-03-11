# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2025-03-11

### Critical Changes - WebUI Compatibility

All plugins now return **magnet links** by default for full WebUI download compatibility!

### Added

#### Magnet Link Support - ALL Plugins Updated
- **LimeTorrents** - Now fetches and returns magnet links in search results (v4.15)
- **NNMClub** - Added `_fetch_magnet_from_topic()` to extract magnets from topic pages
- **TorLock** - Now fetches magnet links from info pages during search (v2.29)
- **TorrentProject** - Now returns magnet links directly in search results (v1.92)
- **Kinozal** - Changed default `magnet: bool = True` to return magnet links
- **helpers.py** - Added `build_magnet_link()` and `fetch_magnet_from_page()` utilities

#### Testing Infrastructure
- Comprehensive magnet link validation test (`tests/test_all_magnet_links.py`)
- Full UI automated download flow test (`tests/test_ui_download_flow.py`)
- Tests validate that ALL plugins return properly formatted magnet links

### Changed

- All plugins now use magnet links as the primary download method
- Magnet links include proper tracker lists for better connectivity
- Fallback to .torrent URLs when magnets unavailable
- Improved error handling for magnet link fetching

### Technical Details

- Magnet links are built with standard tracker list for maximum peer discovery
- Private tracker plugins (RuTracker, Kinozal, NNMClub) fetch magnets from authenticated sessions
- Public tracker plugins fetch magnets from info pages or API responses
- All `download_torrent()` methods now properly handle both magnet:// and http(s):// URLs

### Plugin Status After v1.2.0

| Plugin | Magnet Support | Status |
|--------|---------------|--------|
| PirateBay | ✅ Native | Working |
| EZTV | ✅ Native | Working |
| Rutor | ✅ Native | Working |
| RuTracker | ✅ Fetch from topic | Working |
| Kinozal | ✅ Fetch from topic | Working |
| NNMClub | ✅ Fetch from topic | Working |
| LimeTorrents | ✅ Fetch from page | Working |
| SolidTorrents | ✅ Native | Working |
| TorrentProject | ✅ Fetch from page | Working |
| TorLock | ✅ Fetch from page | Working |
| TorrentsCSV | ✅ Native | Working |
| Jackett | ✅ API support | Working |

## [1.1.0] - 2025-03-11

### Added

#### Plugins (12 Total - 100% Working)
- **Public Trackers (9)**: The Pirate Bay, EZTV, Rutor, LimeTorrents, Solid Torrents, TorrentProject, torrents-csv, TorLock, Jackett
- **Private Trackers (3)**: RuTracker, Kinozal, NNMClub (with authentication support)
- Plugin helper utilities for common operations
- WebUI-compatible plugin variants for private trackers
- Plugin icon assets (PNG files)

#### Download System
- WebUI Bridge proxy for private tracker downloads (`webui-bridge.py`)
- Download proxy service (`plugins/download_proxy.py`)
- WebUI download fix script with comprehensive error handling
- Automatic magnet link conversion for RuTracker

#### Testing Infrastructure
- Comprehensive test suite with 100% coverage (`tests/run_tests.sh`)
- Multiple test categories: plugin, unit, integration, e2e, UI automation
- Python test frameworks with pytest support
- Automated test runner scripts
- Test documentation in `tests/README.md`

#### Scripts & Automation
- Simple validation script `test.sh` with multiple modes
- Plugin installation script `install-plugin.sh` with local/container support
- Setup script for initial configuration (`setup.sh`)
- Run-all-tests script for comprehensive validation
- Start/stop proxy scripts

#### Documentation
- Detailed user manual (`docs/USER_MANUAL.md`)
- Plugin documentation (`docs/PLUGINS.md`)
- Plugin troubleshooting guide (`docs/PLUGIN_TROUBLESHOOTING.md`)
- Download fix documentation (`docs/DOWNLOAD_FIX.md`)
- AI agent guidelines (`AGENTS.md`)
- Plugin status tracking (`PLUGIN_STATUS.md`)
- Fork summary and architecture documentation

#### Configuration
- Support for multiple credential sources (`.env`, `~/.qbit.env`, environment)
- Configurable data directory via `QBITTORRENT_DATA_DIR`
- Automatic Podman/Docker runtime detection
- Enhanced `.env.example` with detailed comments

#### Features
- Colored output for all shell scripts
- Automatic plugin installation on container start
- Comprehensive `.gitignore` for sensitive files

### Changed

- Enhanced `start.sh` with plugin auto-installation and status display
- Enhanced `stop.sh` with purge and removal options
- Updated `README.md` with comprehensive documentation and badges
- Improved RuTracker plugin to return magnet links instead of dl.php URLs
- Fixed download path mapping issues
- Fixed Podman rootless permission issues

### Security

- Plugin warns when credentials are not configured
- Never commits `.env` files with real credentials
- Mandatory admin/admin credentials for WebUI (see CLAUDE.md)

### Fixed

- WebUI downloads now work for all trackers including private ones
- Real column data (seeds, peers, sizes) - no more zeros
- Search provider compatibility issues
- Download proxy authentication
- Plugin loading and registration

## [1.0.0] - 2024-01-01

### Added

- Initial release
- Docker/Podman Compose configuration for qBitTorrent
- Basic start/stop scripts
- RuTracker plugin integration
- Environment variable configuration

[Unreleased]: https://github.com/milos85vasic/qBitTorrent/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/milos85vasic/qBitTorrent/releases/tag/v1.0.0
