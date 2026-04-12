# AGENTS.md - AI Agent Guidelines for qBitTorrent-Fixed

<!-- This file provides essential context for AI coding agents working on this project -->

---

## 🔴 MANDATORY CONSTRAINTS (CRITICAL)

### Default Credentials Requirement

**The qBittorrent WebUI MUST always use these default credentials:**

```
Username: admin
Password: admin
```

**This is NON-NEGOTIABLE.** These credentials are hardcoded in multiple configuration files and scripts. Changing them will break the setup.

---

## 📋 Project Overview

**qBitTorrent-Fixed** is a production-ready Docker/Podman containerized deployment of qBittorrent with enhanced search plugins. This is an infrastructure-as-code project that fixes known issues with qBittorrent search plugins, particularly for private trackers.

### Key Capabilities

- **12 Search Plugins**: 8 official plugins + 4 Russian trackers
- **WebUI Bridge**: Enables private tracker downloads in WebUI (normally impossible)
- **100% Test Coverage**: Comprehensive test suite for all plugins
- **Auto-Detection**: Works with both Docker and Podman
- **Multi-Source Credentials**: Supports `.env`, `~/.qbit.env`, and environment variables

### Plugin Architecture

| Category | Plugins | WebUI Support | Auth Required |
|----------|---------|---------------|---------------|
| **Public Trackers** | PirateBay, EZTV, Rutor, LimeTorrents, SolidTorrents, TorrentProject, torrents-csv, TorLock | ✅ Magnet links | No |
| **Meta Search** | Jackett | ✅ Configurable | Optional |
| **Private Trackers** | RuTracker, Kinozal, NNMClub | ⚠️ Requires Bridge | Yes |

---

## 🏗️ Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Container Runtime** | Docker / Podman (auto-detected) | Application containerization |
| **Orchestration** | Docker Compose / podman-compose | Multi-service management |
| **Base Image** | lscr.io/linuxserver/qbittorrent | qBittorrent application |
| **Plugins** | Python 3 | Search engine plugins |
| **Bridge** | Python 3 + http.server | WebUI proxy for auth handling |
| **Automation** | Bash 4+ | Setup and management scripts |
| **Configuration** | YAML / ENV files | Service configuration |

### Runtime Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         HOST SYSTEM                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │  start.sh   │    │  webui-     │    │   install-plugin.sh │  │
│  │  test.sh    │    │  bridge.py  │    │   setup.sh          │  │
│  └──────┬──────┘    └──────┬──────┘    └─────────────────────┘  │
│         │                  │                                      │
│  ┌──────▼──────────────────▼──────────────────────────────┐     │
│  │              DOCKER / PODMAN RUNTIME                    │     │
│  │  ┌─────────────────┐    ┌─────────────────────────┐    │     │
│  │  │   qbittorrent   │◄──►│   download-proxy        │    │     │
│  │  │   (container)   │    │   (webui-bridge.py)     │    │     │
│  │  │                 │    │                         │    │     │
│  │  │  Port: 18085    │    │  Port: 8085 (proxy)     │    │     │
│  │  │  Image:         │    │  Image: python:3.12     │    │     │
│  │  │  linuxserver/   │    │                         │    │     │
│  │  │  qbittorrent    │    │                         │    │     │
│  │  └─────────────────┘    └─────────────────────────┘    │     │
│  └─────────────────────────────────────────────────────────┘     │
│         │                  │                                      │
│  ┌──────▼──────────────────▼──────────────────────────────┐     │
│  │                    VOLUME MOUNTS                         │     │
│  │  ./config → /config (persistent config)                  │     │
│  │  ./.env → /config/.env (credentials)                     │     │
│  │  ./tmp → /shared-tmp (torrent files)                     │     │
│  │  /mnt/DATA → /downloads (download location)              │     │
│  └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
qBitTorrent/
├── docker-compose.yml          # Main container configuration (2 services)
├── .env.example                # Example environment configuration
├── .env                        # Actual credentials (gitignored)
│
├── 🚀 STARTUP SCRIPTS
│   ├── setup.sh                # One-time comprehensive setup
│   ├── start.sh                # Start containers with auto-detection
│   ├── stop.sh                 # Stop/remove containers
│   └── start-proxy.sh          # Proxy startup script (container internal)
│
├── 🔌 PLUGINS (12 total)
│   ├── eztv.py                 # TV shows
│   ├── jackett.py              # Meta search
│   ├── limetorrents.py         # Verified torrents
│   ├── piratebay.py            # Most popular public tracker
│   ├── solidtorrents.py        # Fast search
│   ├── torlock.py              # No fake torrents
│   ├── torrentproject.py       # Comprehensive search
│   ├── torrentscsv.py          # Open database
│   ├── rutracker.py            # Russian private tracker
│   ├── rutor.py                # Russian public tracker
│   ├── kinozal.py              # Movies/TV private tracker
│   ├── nnmclub.py              # General private tracker
│   │
│   └── 🔧 SUPPORT FILES
│       ├── helpers.py          # Shared helper functions
│       ├── nova2.py            # Search engine core
│       ├── novaprinter.py      # Output formatting
│       ├── socks.py            # Proxy support
│       └── download_proxy.py   # Download proxy for WebUI
│
├── 🌉 WEBUI BRIDGE
│   └── webui-bridge.py         # Enables private tracker downloads in WebUI
│
├── 🧪 TEST SUITE
│   ├── run-all-tests.sh        # Master test runner
│   ├── test.sh                 # Validation script
│   └── tests/
│       ├── comprehensive_test.py      # Full plugin testing
│       ├── test_all_plugins.py        # Unit tests
│       ├── test_plugin_integration.py # Integration tests
│       ├── final_verification.py      # Provider tests
│       └── ... (25+ test files)
│
├── 🔧 MANAGEMENT
│   └── install-plugin.sh       # Plugin installation for local/container
│
├── 📚 DOCUMENTATION
│   ├── README.md               # Main project documentation
│   ├── PLUGIN_STATUS.md        # Plugin compatibility matrix
│   ├── FORK_SUMMARY.md         # Architecture & fixes overview
│   ├── CHANGELOG.md            # Version history
│   └── docs/
│       ├── USER_MANUAL.md      # Complete usage guide
│       ├── PLUGIN_TROUBLESHOOTING.md
│       ├── PLUGINS.md
│       ├── DOWNLOAD_FIX.md
│       └── ...
│
├── ⚙️ CONFIGURATION (gitignored, created at runtime)
│   └── config/
│       └── qBittorrent/
│           ├── config/qBittorrent.conf  # Main config
│           └── nova3/engines/           # Installed plugins
│
└── 📥 DATA (external, configurable)
    └── /mnt/DATA/               # Downloads (configurable)
        ├── Incomplete/          # Partial downloads
        └── Torrents/            # .torrent files
```

---

## 🚀 Build/Run/Test Commands

### Quick Start (Recommended)

```bash
# Complete setup (one command)
./setup.sh

# Start services
./start.sh                    # Terminal 1: Start qBittorrent
python3 webui-bridge.py       # Terminal 2: Enable private tracker support

# Access
open http://localhost:8085    # Login: admin / admin
```

### Container Management

```bash
# Start with options
./start.sh              # Basic start
./start.sh -p           # Pull latest image first
./start.sh -s           # Show status only
./start.sh --no-plugins # Skip plugin installation
./start.sh -v           # Verbose mode

# Stop options
./stop.sh               # Stop containers
./stop.sh -r            # Stop and remove containers
./stop.sh --purge       # Stop, remove, and clean images
```

### Plugin Management

```bash
# Install for container (default)
./install-plugin.sh --all              # Install all 12 plugins
./install-plugin.sh rutracker rutor    # Install specific plugins
./install-plugin.sh --verify           # Verify installation
./install-plugin.sh --test             # Test plugin functionality

# Install for local qBittorrent
./install-plugin.sh --local --all      # Install to ~/.local/share/...
```

### Testing Commands

```bash
# Master test suite (RECOMMENDED)
./run-all-tests.sh

# Validation script
./test.sh               # Quick validation (default)
./test.sh --all         # All validation tests
./test.sh --plugin      # RuTracker plugin only
./test.sh --full        # Complete test suite
./test.sh --container   # Container status only

# Individual test suites
python3 tests/comprehensive_test.py       # Full coverage tests
python3 tests/test_all_plugins.py         # Unit tests
python3 tests/test_plugin_integration.py  # Integration tests
python3 tests/final_verification.py       # Provider tests
```

### Manual Docker/Podman Commands

```bash
# Start
podman-compose up -d           # Podman
docker compose up -d           # Docker

# Stop
podman-compose down            # Podman
docker compose down            # Docker

# View logs
podman logs -f qbittorrent     # Podman
docker compose logs -f qbittorrent  # Docker

# Execute in container
podman exec -it qbittorrent /bin/sh
docker exec -it qbittorrent /bin/sh
```

---

## 🎨 Code Style Guidelines

### Bash Scripts

All bash scripts follow strict conventions:

```bash
#!/bin/bash
set -euo pipefail                    # Strict mode: exit on error, undefined vars, pipe fails

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"                     # Always work from script directory

# Standard color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'                         # No Color

# Standard print functions
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Container runtime detection (standard pattern)
detect_runtime() {
    if command -v podman &> /dev/null; then
        echo "podman"
    elif command -v docker &> /dev/null; then
        echo "docker"
    fi
}

# Always quote variables
[[ -f "$file" ]] || print_error "Missing: $file"
```

**Bash Style Rules:**
- Use `[[ ]]` for conditionals, never `[ ]`
- Quote ALL variables: `"$variable"` not `$variable`
- Use `local` for function variables
- Functions use `snake_case`
- Constants use `UPPER_CASE`
- Indent with 4 spaces
- Add `-h, --help` flags to all scripts

### Python (Plugin Code)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plugin description - one line summary."""
# VERSION: X.Y
# AUTHORS: Name (URL)

import os
import sys
from typing import Optional, List, Dict

class PluginName:
    """Main plugin class - docstring explaining purpose."""
    
    url = "https://tracker.example.com"
    name = "Plugin Name"
    supported_categories = {
        'all': '0',
        'movies': '1',
        # ...
    }
    
    def __init__(self):
        """Initialize with configuration."""
        self.config = self._load_config()
    
    def search(self, what: str, cat: str = 'all') -> None:
        """
        Search for torrents.
        
        Args:
            what: Search query
            cat: Category key from supported_categories
        """
        # Implementation
        pass
    
    def download_torrent(self, url: str) -> str:
        """
        Download torrent file or return magnet link.
        
        Args:
            url: Download URL
            
        Returns:
            Path to torrent file or magnet link string
        """
        # Implementation
        pass
```

**Python Style Rules:**
- Follow PEP 8
- Use type hints for function signatures
- Add docstrings to all classes and public methods
- Handle exceptions gracefully with try/except
- Support environment variables for configuration
- Maintain backward compatibility with qBittorrent API

### YAML/Docker Compose

```yaml
version: '3.8'

services:
  service-name:                      # Descriptive names
    image: repository/image:tag      # Specific tags preferred
    container_name: descriptive-name # For easier management
    
    environment:
      - VARIABLE_NAME=value          # Description of variable
    
    volumes:
      - ./local:/container:ro        # Purpose of mount
      - ${ENV_VAR:-default}:/path    # With default
    
    network_mode: host               # Or specific networks
    restart: unless-stopped          # Always include restart policy
    
    depends_on:                      # Document dependencies
      - other-service
```

**YAML Style Rules:**
- Use 2-space indentation
- Document environment variables inline
- Group related configuration
- Prefer unquoted when safe
- Use specific image tags, not `latest` where possible

---

## 🔧 Configuration System

### Environment Variables Priority

Credentials and configuration are loaded in this order (first wins):

1. **Shell environment** (already exported)
2. **Project `.env`** (`./.env`)
3. **Home config** (`~/.qbit.env`)
4. **Container env** (from docker-compose.yml)

### Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QBITTORRENT_DATA_DIR` | `/mnt/DATA` | Download directory |
| `WEBUI_PORT` | `8085` | WebUI access port |
| `WEBUI_USERNAME` | `admin` | WebUI login |
| `WEBUI_PASSWORD` | `admin` | WebUI password |
| `RUTRACKER_USERNAME` | - | RuTracker login |
| `RUTRACKER_PASSWORD` | - | RuTracker password |
| `KINOZAL_USERNAME` | - | Kinozal login |
| `KINOZAL_PASSWORD` | - | Kinozal password |
| `NNMCLUB_COOKIES` | - | NNMClub auth cookies |
| `PUID` | `1000` | User ID for container |
| `PGID` | `1000` | Group ID for container |
| `TZ` | `Europe/Moscow` | Timezone |

### Data Directory Structure

```
$QBITTORRENT_DATA_DIR/
├── Incomplete/                 # Partial downloads
├── Torrents/
│   ├── All/                   # All .torrent files
│   └── Completed/             # Completed .torrent files
└── [completed downloads]      # Finished files
```

---

## 🧪 Testing Strategy

### Test Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    TEST LAYERS                          │
├─────────────────────────────────────────────────────────┤
│  1. UNIT TESTS (test_plugin_unit.py)                    │
│     - Plugin class instantiation                        │
│     - Method availability                               │
│     - Basic syntax validation                           │
├─────────────────────────────────────────────────────────┤
│  2. INTEGRATION TESTS (test_plugin_integration.py)      │
│     - Plugin loading in container                       │
│     - Import verification                               │
│     - Cross-plugin compatibility                        │
├─────────────────────────────────────────────────────────┤
│  3. FUNCTIONAL TESTS (comprehensive_test.py)            │
│     - Search functionality                              │
│     - Download capability                               │
│     - Column data extraction                            │
├─────────────────────────────────────────────────────────┤
│  4. END-TO-END TESTS (test_e2e_download.py)             │
│     - Full download flow                                │
│     - WebUI integration                                 │
│     - Authentication flow                               │
├─────────────────────────────────────────────────────────┤
│  5. VALIDATION (test.sh)                                │
│     - File structure                                    │
│     - Configuration                                     │
│     - Container status                                  │
└─────────────────────────────────────────────────────────┘
```

### Running Tests

```bash
# Full test suite (REQUIRED before committing)
./run-all-tests.sh

# Expected output:
# ✅ ALL TESTS PASSED - 100% SUCCESS RATE!

# Quick validation during development
./test.sh --quick

# Test specific areas
./test.sh --plugin      # Plugin credentials and structure
./test.sh --container   # Container health
```

### Test Requirements

- All 12 plugins must pass structure validation
- Private trackers need valid credentials for full tests
- Container must be running for integration tests
- Tests generate timestamped reports: `test_report_YYYYMMDD_HHMMSS.txt`

---

## 🔒 Security Considerations

### Critical Security Rules

1. **NEVER commit credentials**
   - `.env` is in `.gitignore`
   - `~/.qbit.env` should also be gitignored
   - No credential files in repository

2. **Default credentials are intentional**
   - WebUI uses `admin/admin` by design
   - These are hardcoded in config generation
   - Changing them requires updating multiple files

3. **Private tracker authentication**
   - Credentials passed via environment variables
   - Plugins load from `.env` files at runtime
   - Session cookies handled by `nova2dl.py`

4. **File permissions**
   - Plugins: `644` (readable, not executable)
   - Scripts: `755` (executable)
   - Config: `600` recommended for credential files

5. **Network security**
   - Uses `network_mode: host` for simplicity
   - WebUI accessible on localhost only by default
   - No HTTPS configured (add reverse proxy for production)

### Credential Storage Options

```bash
# Option 1: Project .env (gitignored)
echo "RUTRACKER_USERNAME=myuser" >> .env
echo "RUTRACKER_PASSWORD=mypass" >> .env
chmod 600 .env

# Option 2: Home directory config
echo "RUTRACKER_USERNAME=myuser" >> ~/.qbit.env
chmod 600 ~/.qbit.env

# Option 3: Shell exports (session only)
export RUTRACKER_USERNAME=myuser
export RUTRACKER_PASSWORD=mypass
```

---

## 🐛 Troubleshooting Guide

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Container won't start | Port conflict | Check port 8085/18085: `ss -tln \| grep 8085` |
| Plugin not showing | Cache issue | Restart container + hard refresh (Ctrl+Shift+R) |
| Private tracker download fails | Auth bypass | Run `python3 webui-bridge.py` |
| Permission denied | PUID/PGID mismatch | Run `id` on host, update `.env` |
| Stale config errors | Old config file | Run `./start.sh` (auto-cleans) |
| Tests fail | Container not running | Start container: `./start.sh` |
| RuTracker login fails | CAPTCHA | Login via browser first |

### Debug Commands

```bash
# Check container status
podman ps -a | grep qbittorrent
docker compose ps

# View logs
podman logs -f qbittorrent
docker compose logs -f qbittorrent

# Check plugin installation
podman exec qbittorrent ls /config/qBittorrent/nova3/engines/

# Test plugin directly
podman exec -u abc qbittorrent \
  python3 /config/qBittorrent/nova3/nova2dl.py \
  rutracker 'https://rutracker.org/forum/dl.php?t=12345'

# Verify credentials in container
podman exec qbittorrent env | grep -E "RUTRACKER|KINOZAL|NNMCLUB"

# Check file permissions
ls -la config/qBittorrent/nova3/engines/
```

---

## 📝 Git Workflow

### What to Commit

✅ **DO commit:**
- Configuration files: `docker-compose.yml`, `.env.example`
- Scripts: `*.sh`, `*.py` (except generated)
- Plugins: `plugins/*.py`
- Documentation: `*.md`
- Tests: `tests/*.py`

❌ **NEVER commit:**
- `.env` files (contain credentials)
- `config/qBittorrent/*` (runtime config)
- `downloads/` (downloaded content)
- `tmp/` (temporary files)
- `__pycache__/` (Python cache)
- `*.pyc`, `*.pyo` (compiled Python)

### Commit Message Format

```
Type: Brief description

- Use present tense: "Add feature" not "Added"
- Be specific: "Fix RuTracker login timeout" not "Fix bug"
- Reference issues: "Fix #123: Description"

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation
- test: Tests
- refactor: Code restructuring
- chore: Maintenance
```

### Pre-Commit Checklist

```bash
# 1. Run full test suite
./run-all-tests.sh

# 2. Verify no credentials leaked
grep -r "RUTRACKER_PASSWORD" --include="*.py" --include="*.sh" --include="*.md" .
# Should only show .env.example with placeholder

# 3. Check syntax
bash -n start.sh stop.sh test.sh install-plugin.sh
python3 -m py_compile plugins/*.py

# 4. Validate docker-compose
docker compose config  # or podman-compose config
```

---

## 🔌 Plugin Development

### Plugin Template

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MyTracker search plugin for qBittorrent."""
# VERSION: 1.0

import os
import sys
from urllib.parse import urlencode
from urllib.request import build_opener

try:
    import novaprinter
except ImportError:
    pass


class MyTracker:
    """MyTracker search engine plugin."""
    
    url = "https://mytracker.example.com"
    name = "MyTracker"
    supported_categories = {
        'all': '0',
        'movies': '1',
        'tv': '2',
        'music': '3',
    }
    
    def __init__(self):
        """Initialize plugin."""
        self.opener = build_opener()
        self.opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (compatible; qBittorrent)')
        ]
    
    def search(self, what: str, cat: str = 'all') -> None:
        """Search for torrents."""
        category = self.supported_categories.get(cat, '0')
        search_url = f"{self.url}/search?q={what}&cat={category}"
        
        # Fetch and parse results
        # Call novaprinter.print() for each result
        # Format: name, link, size, seeds, leech, engine_url, desc_link
        
    def download_torrent(self, url: str) -> str:
        """Download torrent file or return magnet link."""
        # Return magnet link directly
        if url.startswith('magnet:'):
            return url
        
        # Or download .torrent file
        # Return format: "filepath url" or just "magnet_link"
        pass


# For standalone testing
if __name__ == "__main__":
    plugin = MyTracker()
    plugin.search("test")
```

### Required Plugin Methods

| Method | Required | Description |
|--------|----------|-------------|
| `__init__` | Yes | Initialize plugin, set up HTTP opener |
| `search(what, cat)` | Yes | Main search method, outputs via novaprinter |
| `download_torrent(url)` | Yes | Download torrent or return magnet |

### Output Format (novaprinter)

```python
novaprinter.print(
    name="Ubuntu 22.04 LTS",           # Torrent name
    link="magnet:?xt=urn:btih:...",    # Download URL or magnet
    size="2377711616",                 # Size in bytes
    seeds="25",                        # Seeders count
    leech="3",                         # Leechers count
    engine_url="https://tracker.com", # Tracker URL
    desc_link="https://...",          # Description page
    pub_date="1647261600"             # Unix timestamp (optional)
)
```

---

## 📚 Reference Documentation

| Document | Purpose |
|----------|---------|
| `README.md` | Main project overview |
| `PLUGIN_STATUS.md` | Plugin compatibility matrix |
| `FORK_SUMMARY.md` | Architecture and fixes overview |
| `docs/USER_MANUAL.md` | Complete usage guide |
| `docs/PLUGIN_TROUBLESHOOTING.md` | Debug guide |
| `docs/PLUGINS.md` | Plugin development guide |
| `CHANGELOG.md` | Version history |
| `LICENSE` | Apache 2.0 license |

---

## 🎯 Quick Reference

### One-Liners

```bash
# Complete setup from scratch
./setup.sh && python3 webui-bridge.py

# Restart everything
./stop.sh -r && ./start.sh

# Test everything
./run-all-tests.sh

# Check what's installed
./install-plugin.sh --verify

# View logs
podman logs -f qbittorrent 2>&1 | grep -i error
```

### File Permissions Quick Fix

```bash
# Fix plugin permissions
chmod 644 plugins/*.py
chmod 644 config/qBittorrent/nova3/engines/*.py

# Fix script permissions
chmod 755 *.sh

# Secure credential files
chmod 600 .env ~/.qbit.env 2>/dev/null || true
```

---

## 📞 Support

- **Documentation**: Check `docs/` folder
- **Tests**: Run `./run-all-tests.sh` to diagnose
- **Logs**: `podman logs qbittorrent`
- **Status**: Check `PLUGIN_STATUS.md` for known issues

---

**Version**: 2.0.0  
**License**: Apache 2.0  
**Last Updated**: April 2025
