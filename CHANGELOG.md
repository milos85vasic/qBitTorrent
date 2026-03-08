# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Comprehensive test suite in `tests/run_tests.sh`
- Simple validation script `test.sh` in project root
- Plugin installation script `install-plugin.sh`
- Detailed documentation in `docs/USER_MANUAL.md`
- AI agent guidelines in `AGENTS.md`
- Test documentation in `tests/README.md`
- RuTracker search plugin with environment variable support
- Support for multiple credential sources (`.env`, `~/.qbit.env`, environment)
- Automatic Podman/Docker runtime detection
- Colored output for all shell scripts

### Changed

- Enhanced `start.sh` with plugin auto-installation
- Enhanced `stop.sh` with purge options
- Improved `.env.example` with detailed comments
- Updated `README.md` with comprehensive documentation

### Security

- Added comprehensive `.gitignore` for sensitive files
- Plugin warns when credentials are not configured
- Never commits `.env` files with real credentials

## [1.0.0] - 2024-01-01

### Added

- Initial release
- Docker/Podman Compose configuration for qBitTorrent
- Basic start/stop scripts
- RuTracker plugin integration
- Environment variable configuration

[Unreleased]: https://github.com/milos85vasic/qBitTorrent/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/milos85vasic/qBitTorrent/releases/tag/v1.0.0
