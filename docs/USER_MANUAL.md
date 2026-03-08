# User Manual: qBitTorrent with RuTracker Plugin

## Table of Contents

1. [Getting Started](#getting-started)
2. [Using the Web Interface](#using-the-web-interface)
3. [Using the RuTracker Plugin](#using-the-rutracker-plugin)
4. [Managing Downloads](#managing-downloads)
5. [Configuration Guide](#configuration-guide)
6. [Common Tasks](#common-tasks)
7. [FAQ](#faq)

---

## Getting Started

### First Time Setup

1. **Start qBitTorrent**:
   ```bash
   cd /path/to/qBitTorrent
   ./start.sh
   ```

2. **Access Web UI**:
   - Open your web browser
   - Go to: `http://localhost:8085`
   - Default login:
     - Username: `admin`
     - Password: `adminadmin`

3. **Change Password** (Important!):
   - Click **Tools** → **Options**
   - Go to **Web UI** tab
   - Under **Authentication**, set new username and password
   - Click **Save**

4. **Configure Data Directory**:
   - The data directory is set via `QBITTORRENT_DATA_DIR` environment variable
   - Default: `/mnt/DATA`
   - To customize, add to `.env`:
     ```bash
     QBITTORRENT_DATA_DIR=/your/custom/path
     ```
   - Restart the container for changes to take effect
   - Required subdirectories are created automatically:
     - `Incomplete/` - Partial downloads
     - `Torrents/All/` - All .torrent files
     - `Torrents/Completed/` - Completed .torrent files

---

## Using the Web Interface

### Main Interface Overview

The qBitTorrent Web UI has several main sections:

| Section | Purpose |
|---------|---------|
| **Transfers** | View and manage active downloads |
| **Search** | Search for torrents using plugins |
| **RSS** | Subscribe to RSS feeds for automatic downloads |
| **Execution Log** | View application logs |

### Adding Torrents

**Method 1: From File**
1. Click **File** → **Add Torrent File**
2. Select your `.torrent` file
3. Choose download location
4. Click **Upload**

**Method 2: From URL/Magnet Link**
1. Click **File** → **Add Torrent Link**
2. Paste the URL or magnet link
3. Choose download location
4. Click **Download**

### Managing Downloads

| Action | How To |
|--------|--------|
| **Pause** | Right-click torrent → **Pause** |
| **Resume** | Right-click torrent → **Resume** |
| **Delete** | Right-click torrent → **Delete** |
| **Set Priority** | Right-click → **Set priority** → High/Normal/Low |
| **Limit Speed** | Right-click → **Set download/upload limit** |

### Viewing Download Details

Click on any torrent to see:
- **General**: Status, progress, size, hashes
- **Trackers**: Tracker status and peers
- **Peers**: Connected peers list
- **HTTP Sources**: HTTP/FTP sources
- **Content**: Files in the torrent

---

## Using the RuTracker Plugin

### Prerequisites

Before using the RuTracker plugin, ensure:

1. You have a RuTracker account
2. Credentials are configured in `.env` or `~/.qbit.env`

To verify:
```bash
./install-plugin.sh --verify
```

### Searching on RuTracker

1. **Open Search Tab**:
   - Click on **Search** in the left sidebar

2. **Configure Search**:
   - In the search box, type your query
   - Select **RuTracker** from the "Select search engine" dropdown
   - Click **Search** or press Enter

3. **Filter Results**:
   - Use category filters on the left
   - Sort by columns (name, size, seeders, etc.)

4. **Download**:
   - Double-click a result to download
   - Or right-click → **Download**

### Search Tips

| Tip | Description |
|-----|-------------|
| **Use Russian** | Searches work better in Russian |
| **Exact phrase** | Use quotes: `"exact phrase"` |
| **Exclude terms** | Use minus: `term -unwanted` |
| **Category filter** | Browse by category on RuTracker website first |

### Troubleshooting Search

**No results found:**
1. Check credentials: `./install-plugin.sh --test`
2. Visit RuTracker website and login manually
3. Clear any CAPTCHA by logging in via browser
4. Check if RuTracker mirrors are accessible

**Login failed:**
1. Verify username/password in `.env`
2. Ensure no special characters are causing issues
3. Try logging in via browser with same credentials

---

## Managing Downloads

### Download Categories

Organize downloads with categories:

1. Go to **Tools** → **Options** → **Downloads**
2. Under **Torrent Management Mode**, select **Automatic**
3. Create categories in the sidebar

**Creating a Category:**
1. Right-click **Category** in sidebar
2. Select **Add category**
3. Enter name and save path

### Scheduling Downloads

Limit bandwidth during certain hours:

1. Go to **Tools** → **Options** → **Speed**
2. Enable **Alternative rate limits**
3. Set **Scheduler**:
   - Select time range
   - Choose which limits to apply

### RSS Automation

Automatically download from RSS feeds:

1. Go to **RSS** tab
2. Click **New subscription**
3. Add RSS feed URL
4. Create download rules:
   - Click **RSS Downloader**
   - Add rules matching specific content

---

## Configuration Guide

### Essential Settings

Access via: **Tools** → **Options**

#### Downloads Tab

| Setting | Recommended Value |
|---------|-------------------|
| Default Save Path | `/DATA` (mapped from `QBITTORRENT_DATA_DIR`) |
| Keep incomplete torrents in | `/DATA/Incomplete` |
| Torrent Management Mode | Automatic |
| Pre-allocate disk space | Enabled (for less fragmentation) |

> **Note:** The `/DATA` path inside the container is mapped to the host directory specified by `QBITTORRENT_DATA_DIR` (default: `/mnt/DATA`).

#### Connection Tab

| Setting | Recommended Value |
|---------|-------------------|
| Port for incoming connections | Random or specific port |
| Global maximum connections | 500 |
| Maximum active downloads | 3-5 |
| Maximum active uploads | 3-5 |

#### Speed Tab

| Setting | Recommended Value |
|---------|-------------------|
| Global Download Limit | 0 (unlimited) or set as needed |
| Global Upload Limit | Set based on your connection |
| Alternative rate limits | Configure for off-peak hours |

#### BitTorrent Tab

| Setting | Recommended Value |
|---------|-------------------|
| Enable DHT | Enabled |
| Enable PeX | Enabled |
| Enable LSD | Enabled |
| Encryption mode | Prefer encryption |

#### Web UI Tab

| Setting | Recommended Value |
|---------|-------------------|
| Port | 8085 (or your choice) |
| Use UPnP | Optional |
| Authentication | **Enabled** (change default!) |
| Enable clickjacking protection | Enabled |

---

## Common Tasks

### Backing Up Configuration

```bash
# Backup config directory
tar -czf qbittorrent-config-backup.tar.gz config/

# Backup only essential files
tar -czf qbittorrent-essential-backup.tar.gz \
    config/qBittorrent/qBittorrent.ini \
    config/qBittorrent/fastresume/ \
    config/qBittorrent/BT_backup/
```

### Restoring Configuration

```bash
./stop.sh
tar -xzf qbittorrent-config-backup.tar.gz
./start.sh
```

### Exporting/Importing Torrents

**Export:**
1. Select torrents to export
2. Right-click → **Export .torrent**
3. Choose save location

**Import:**
1. Drag and drop `.torrent` files into the UI
2. Or use **File** → **Add Torrent File**

### Checking Disk Space

```bash
# Check download directory space
df -h /path/to/downloads

# Check config directory space
du -sh config/
```

### Updating qBitTorrent

```bash
./stop.sh
./start.sh -p    # Pull latest image
```

### Viewing Logs

```bash
# Container logs
podman logs -f qbittorrent

# Or use Docker
docker compose logs -f qbittorrent

# Application logs
# View in Web UI: Tools → Execution Log
```

---

## FAQ

### General Questions

**Q: How do I change the Web UI port?**
> Edit `.env` and change `WEBUI_PORT=8085` to your desired port, then restart.

**Q: How do I change the data/download directory?**
> Set `QBITTORRENT_DATA_DIR` in one of these locations:
> 1. Project `.env` file: `QBITTORRENT_DATA_DIR=/your/path`
> 2. `~/.qbit.env` file: `QBITTORRENT_DATA_DIR=/your/path`
> 3. Shell environment (`~/.bashrc`): `export QBITTORRENT_DATA_DIR=/your/path`
>
> Then restart the container: `./stop.sh && ./start.sh`

**Q: Can I access qBitTorrent remotely?**
> Yes, but secure it first:
> 1. Change default credentials
> 2. Use HTTPS (via reverse proxy)
> 3. Consider VPN for additional security

**Q: Why are downloads slow?**
> Check:
> 1. Seeders/peers count
> 2. Connection settings (Tools → Options → Connection)
> 3. Bandwidth limits (Tools → Options → Speed)
> 4. Port forwarding configuration

**Q: How do I move completed downloads?**
> qBitTorrent can't automatically move files, but you can:
> 1. Use categories with different save paths
> 2. Use external scripts with the "Run external program" feature

### Plugin Questions

**Q: RuTracker plugin shows no results**
> 1. Check credentials: `./install-plugin.sh --verify`
> 2. Login to RuTracker website manually to clear CAPTCHA
> 3. Ensure mirrors are accessible from your network

**Q: How do I update the plugin?**
> ```bash
> ./stop.sh
> ./install-plugin.sh --container
> ./start.sh
> ```

**Q: Can I use multiple search plugins?**
> Yes! qBitTorrent supports multiple plugins. Install them in the same `engines` directory.

### Container Questions

**Q: Container keeps restarting**
> Check logs:
> ```bash
> podman logs qbittorrent
> ```
> Common causes:
> - Permission issues (check PUID/PGID)
> - Volume mount failures
> - Port conflicts

**Q: How do I access files downloaded inside the container?**
> Files in `/DATA` inside the container are mapped to your host path (configured in `docker-compose.yml`)

**Q: Can I run multiple qBitTorrent instances?**
> Yes, but:
> 1. Use different ports
> 2. Use different config directories
> 3. Use different container names

### Performance Questions

**Q: How to optimize download speed?**
> 1. Enable DHT, PeX, LSD (Connection tab)
> 2. Increase max connections (Connection tab)
> 3. Ensure port is forwarded if behind NAT
> 4. Use wired connection instead of WiFi

**Q: qBitTorrent uses too much memory**
> 1. Reduce cache size (Advanced → Disk cache)
> 2. Reduce maximum connections
> 3. Reduce number of active torrents

**Q: How to limit bandwidth during the day?**
> Use the scheduler in Tools → Options → Speed:
> 1. Enable "Alternative rate limits"
> 2. Configure scheduler with time ranges
> 3. Set lower limits for "alternative" period

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | Add torrent link |
| `Ctrl+O` | Add torrent file |
| `Ctrl+P` | Open options |
| `Del` | Delete selected torrent |
| `Ctrl+A` | Select all torrents |
| `Ctrl+U` | Add torrent link |
| `Space` | Pause/Resume selected |

---

## Getting Help

### Logs Location

| Type | Location |
|------|----------|
| Container logs | `podman logs qbittorrent` |
| Application logs | Web UI: Tools → Execution Log |
| Config files | `config/qBittorrent/` |

### Useful Commands

```bash
# Check if container is running
./start.sh -s

# View container logs
podman logs -f qbittorrent

# Run validation tests
./test.sh --full

# Verify plugin configuration
./install-plugin.sh --test

# Restart container
./stop.sh && ./start.sh
```

### Support Resources

- [qBitTorrent Forum](https://qbforums.shiki.hu/)
- [qBitTorrent Reddit](https://www.reddit.com/r/qBittorrent/)
- [LinuxServer.io Discord](https://discord.gg/linuxserver)
- [Project Issues](https://github.com/your-repo/issues)

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────┐
│                  ESSENTIAL COMMANDS                  │
├─────────────────────────────────────────────────────┤
│  ./start.sh           Start container               │
│  ./stop.sh            Stop container                │
│  ./test.sh            Run validation tests          │
│  ./install-plugin.sh  Install RuTracker plugin      │
├─────────────────────────────────────────────────────┤
│                   WEB UI ACCESS                      │
├─────────────────────────────────────────────────────┤
│  URL:      http://localhost:8085                    │
│  User:     admin                                    │
│  Pass:     adminadmin (CHANGE IMMEDIATELY!)         │
├─────────────────────────────────────────────────────┤
│                  CONFIGURATION                       │
├─────────────────────────────────────────────────────┤
│  Edit .env file for settings                        │
│  Web UI: Tools → Options for detailed config        │
└─────────────────────────────────────────────────────┘
```

---

*Last updated: March 2026*
