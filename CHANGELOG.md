# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
