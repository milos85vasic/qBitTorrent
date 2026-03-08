# qBitTorrent Docker/Podman Setup

A containerized qBitTorrent setup with RuTracker search plugin, using Docker Compose or Podman Compose for easy deployment and management.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Scripts Reference](#scripts-reference)
- [RuTracker Plugin](#rutracker-plugin)
- [Testing & Validation](#testing--validation)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Uninstallation](#uninstallation)

## Prerequisites

### Container Runtime

This setup supports both **Podman** and **Docker**. The scripts automatically detect which one is available.

| Runtime | Minimum Version | Notes |
|---------|----------------|-------|
| Podman  | 3.0+           | Preferred on Linux systems (rootless) |
| Docker  | 20.10+         | With Docker Compose v2 |

Check if you have either installed:

```bash
podman --version    # Check Podman
docker --version    # Check Docker
```

### System Requirements

- **OS**: Linux (recommended), macOS, or Windows with WSL2
- **RAM**: Minimum 512MB, recommended 1GB+
- **Storage**: Depends on download volume
- **Network**: Internet connection for downloads

## Quick Start

1. Clone or download this repository:
   ```bash
   git clone <repository-url>
   cd qBitTorrent
   ```

2. Create configuration files:
   ```bash
   cp .env.example .env
   # Edit .env and add your RuTracker credentials
   ```

3. Make scripts executable:
   ```bash
   chmod +x *.sh
   ```

4. Start the service:
   ```bash
   ./start.sh
   ```

5. Access the Web UI at: **http://localhost:8085**

6. Login with default credentials:
   - Username: `admin`
   - Password: `adminadmin`

7. **Important**: Change the default password immediately after first login!

## Installation

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd qBitTorrent
```

### Step 2: Configure Environment

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your settings:
```bash
# Required: RuTracker Login Credentials
RUTRACKER_USERNAME=your_username
RUTRACKER_PASSWORD=your_password

# Optional: Custom RuTracker Mirrors
# RUTRACKER_MIRRORS=https://rutracker.org,https://rutracker.net

# Data Directory (default: /mnt/DATA)
QBITTORRENT_DATA_DIR=/path/to/your/data

# qBitTorrent Configuration
PUID=1000
PGID=1000
TZ=Europe/Moscow
WEBUI_PORT=8085
```

Find your UID/GID:
```bash
id -u    # Shows your UID
id -g    # Shows your GID
```

### Step 3: Configure Data Directory

The data directory is configured via the `QBITTORRENT_DATA_DIR` environment variable.

**Option 1: Using .env file (recommended)**
```bash
# Edit .env file
echo "QBITTORRENT_DATA_DIR=/your/custom/path" >> .env
```

**Option 2: Using ~/.bashrc**
```bash
# Add to ~/.bashrc
export QBITTORRENT_DATA_DIR="/your/custom/path"
```

**Option 3: Using ~/.qbit.env**
```bash
# Create or edit ~/.qbit.env
echo "QBITTORRENT_DATA_DIR=/your/custom/path" >> ~/.qbit.env
```

If not set, defaults to `/mnt/DATA`.

The `start.sh` script will automatically create the required subdirectories:
- `Incomplete/` - For partial downloads
- `Torrents/All/` - For all .torrent files
- `Torrents/Completed/` - For completed .torrent files

### Step 4: Start the Service

```bash
chmod +x *.sh
./start.sh
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `RUTRACKER_USERNAME` | RuTracker username | - | For plugin |
| `RUTRACKER_PASSWORD` | RuTracker password | - | For plugin |
| `RUTRACKER_MIRRORS` | Custom mirrors (comma-separated) | - | No |
| `QBITTORRENT_DATA_DIR` | Data directory for downloads | `/mnt/DATA` | No |
| `PUID` | User ID for file permissions | `1000` | Yes |
| `PGID` | Group ID for file permissions | `1000` | Yes |
| `TZ` | Timezone (TZ format) | `Europe/Moscow` | Yes |
| `WEBUI_PORT` | Port for Web UI | `8085` | Yes |

### Data Directory Structure

When `QBITTORRENT_DATA_DIR` is set, the following directory structure is automatically created:

| Path | Purpose |
|------|---------|
| `$QBITTORRENT_DATA_DIR` | Main download directory |
| `$QBITTORRENT_DATA_DIR/Incomplete` | Incomplete/partial downloads |
| `$QBITTORRENT_DATA_DIR/Torrents/All` | All .torrent files |
| `$QBITTORRENT_DATA_DIR/Torrents/Completed` | .torrent files of completed downloads |

### Credential Storage Options

You can store RuTracker credentials in multiple locations:

1. **Project `.env` file** (recommended for containers):
   ```bash
   # ./qBitTorrent/.env
   RUTRACKER_USERNAME=your_username
   RUTRACKER_PASSWORD=your_password
   ```

2. **Home directory `.qbit.env`** (recommended for local):
   ```bash
   # ~/.qbit.env
   RUTRACKER_USERNAME=your_username
   RUTRACKER_PASSWORD=your_password
   ```

3. **Bash configuration**:
   ```bash
   # Add to ~/.bashrc
   export RUTRACKER_USERNAME="your_username"
   export RUTRACKER_PASSWORD="your_password"
   ```

### Timezone Examples

Common timezone values:
- `UTC`
- `Europe/London`
- `Europe/Berlin`
- `Europe/Moscow`
- `America/New_York`
- `Asia/Tokyo`

### Network Configuration

The setup uses `network_mode: host` which:
- Bypasses container network isolation
- Allows direct access to all host network interfaces
- Required for some VPN configurations
- **Note**: Port mapping is not needed with host networking

### Volume Mappings

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./config` | `/config` | Stores qBitTorrent configuration |
| `./config/qBittorrent/nova3/engines` | `/config/qBittorrent/nova3/engines` | Search plugins |
| `$QBITTORRENT_DATA_DIR` | `/DATA` | Download destination (configurable) |

The data directory is configurable via the `QBITTORRENT_DATA_DIR` environment variable. You can set it in:
1. Project `.env` file
2. `~/.qbit.env` file
3. Shell environment (`~/.bashrc`)

## Usage

### Starting the Service

```bash
./start.sh
```

Options:
- `-p, --pull` - Pull latest image before starting
- `-v, --verbose` - Enable verbose output
- `-s, --status` - Show container status only
- `--no-plugins` - Skip plugin installation

### Stopping the Service

```bash
./stop.sh
```

Options:
- `-r, --remove` - Remove container after stopping
- `-p, --purge` - Remove container and local images

### Viewing Logs

```bash
# Using Podman
podman logs -f qbittorrent

# Using Docker
docker compose logs -f qbittorrent
```

### Accessing the Web UI

1. Open your browser
2. Navigate to `http://localhost:8085`
3. Login with credentials
4. Configure your download settings

### Container Management

```bash
# Check container status
./start.sh -s

# Restart container
./stop.sh && ./start.sh

# View resource usage
podman stats qbittorrent    # Podman
docker stats qbittorrent    # Docker
```

## Scripts Reference

### start.sh

Starts qBitTorrent container with automatic Podman/Docker detection and plugin installation.

```bash
Usage: ./start.sh [OPTIONS]

Options:
  -h, --help      Show help message
  -p, --pull      Pull latest image before starting
  -v, --verbose   Enable verbose output
  -s, --status    Show container status only
  --no-plugins    Skip plugin installation
```

### stop.sh

Stops qBitTorrent container gracefully.

```bash
Usage: ./stop.sh [OPTIONS]

Options:
  -h, --help      Show help message
  -v, --verbose   Enable verbose output
  -r, --remove    Remove container after stopping
  -p, --purge     Remove container and local images
```

### install-plugin.sh

Installs RuTracker search plugin.

```bash
Usage: ./install-plugin.sh [OPTIONS]

Options:
  -h, --help      Show help message
  -l, --local     Install for local qBittorrent
  -c, --container Install for containerized qBittorrent (default)
  -t, --test      Test plugin configuration
  -v, --verify    Verify credentials only
  -a, --all       Install for both local and container
```

### test.sh

Validates and tests the qBitTorrent setup.

```bash
Usage: ./test.sh [OPTIONS]

Options:
  -h, --help      Show help message
  -a, --all       Run all validation tests
  -q, --quick     Run quick validation (default)
  -p, --plugin    Test RuTracker plugin only
  -f, --full      Run full test suite
  -c, --container Test container status only
```

## RuTracker Plugin

### Features

- Search RuTracker directly from qBitTorrent Web UI
- Automatic mirror detection and failover
- Environment variable support for credentials
- Compatible with both local and containerized setups

### Installation

**For Container (automatic):**
```bash
./start.sh  # Plugins are installed automatically
```

**For Local qBittorrent:**
```bash
./install-plugin.sh --local
```

**For Both:**
```bash
./install-plugin.sh --all
```

### Configuration

1. Create `.env` file with your credentials:
   ```bash
   cp .env.example .env
   nano .env
   ```

2. Add your RuTracker credentials:
   ```
   RUTRACKER_USERNAME=your_username
   RUTRACKER_PASSWORD=your_password
   ```

3. Restart qBitTorrent to load the plugin

### Testing Plugin

```bash
./install-plugin.sh --test
```

### Using the Plugin

1. Open qBitTorrent Web UI
2. Go to **Search** tab
3. Select **RuTracker** from the search engines dropdown
4. Enter your search query
5. Click **Search**

### Troubleshooting Plugin

If the plugin doesn't work:

1. **Check credentials**:
   ```bash
   ./install-plugin.sh --verify
   ```

2. **Test plugin loading**:
   ```bash
   ./install-plugin.sh --test
   ```

3. **Check captcha**: Visit RuTracker website manually and login once to clear any captcha

4. **Check mirrors**: Ensure at least one RuTracker mirror is accessible from your network

## Testing & Validation

### Quick Test

Run basic validation:
```bash
./test.sh
```

### Full Test Suite

Run all tests including plugin validation:
```bash
./test.sh --full
```

### Test Specific Components

```bash
# Test plugin only
./test.sh --plugin

# Test container status
./test.sh --container

# Run all validation tests
./test.sh --all
```

### Test Results

The test script checks:
- Project structure (all required files)
- Script executability and syntax
- Configuration file validity
- Container runtime availability
- Container status
- Web UI accessibility
- Plugin configuration

## Troubleshooting

### Common Issues

#### Permission Denied

**Symptom**: Cannot write to download directory

**Solution**: Ensure PUID/PGID match your user:
```bash
id -u    # Get your UID
id -g    # Get your GID
```

Update `.env`:
```
PUID=<your-uid>
PGID=<your-gid>
```

#### Port Already in Use

**Symptom**: Error about port 8085 being in use

**Solution**: Change the port in `.env`:
```
WEBUI_PORT=8090
```

#### Container Won't Start

**Symptom**: Container exits immediately

**Solution**: Check logs:
```bash
podman logs qbittorrent
docker compose logs qbittorrent
```

#### Cannot Access Web UI

**Symptom**: Browser can't connect

**Solutions**:
1. Check container is running: `./start.sh -s`
2. Verify port: `netstat -tlnp | grep 8085`
3. Check firewall: `sudo ufw status`
4. Try localhost: `http://127.0.0.1:8085`

#### Plugin Not Working

**Symptom**: RuTracker not appearing in search engines

**Solutions**:
1. Verify plugin is installed: `ls -la config/qBittorrent/nova3/engines/`
2. Check credentials: `./install-plugin.sh --verify`
3. Restart container: `./stop.sh && ./start.sh`
4. Check qBitTorrent logs for errors

#### RuTracker Login Failed

**Symptom**: Plugin shows "Unable to connect using given credentials"

**Solutions**:
1. Verify username/password in `.env`
2. Login to RuTracker website manually to clear captcha
3. Check if RuTracker is accessible from your network
4. Try alternative mirrors in `.env`:
   ```
   RUTRACKER_MIRRORS=https://rutracker.org,https://rutracker.net,https://rutracker.nl
   ```

### Log Analysis

```bash
# Real-time logs
podman logs -f qbittorrent

# Last 100 lines
podman logs --tail=100 qbittorrent

# Logs with timestamps
podman logs -t qbittorrent
```

### Reset Configuration

```bash
./stop.sh -r
rm -rf config/qBittorrent/*
./start.sh
```

## Security

### Best Practices

1. **Change Default Password**: Immediately after first login
   - Go to Tools → Options → Web UI
   - Set new username and password

2. **Use HTTPS**: Consider using a reverse proxy with SSL

3. **Restrict Access**: Bind to specific IP if possible

4. **Keep Updated**: Regularly update the container image
   ```bash
   ./stop.sh
   podman pull lscr.io/linuxserver/qbittorrent:latest
   ./start.sh
   ```

5. **VPN Consideration**: For privacy, use a VPN

6. **Secure Credentials**: 
   - Never commit `.env` files
   - Use environment variables or secure credential storage
   - Consider using secrets management for production

### Firewall Configuration

If using UFW:
```bash
sudo ufw allow 8085/tcp
sudo ufw reload
```

### Reverse Proxy Setup (Optional)

Example Nginx configuration:
```nginx
server {
    listen 443 ssl;
    server_name qbittorrent.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8085;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Uninstallation

### Remove Container

```bash
./stop.sh -r
```

### Remove All Data

```bash
./stop.sh -r
rm -rf config/
rm -rf plugins/
rm -f .env
```

### Remove Image

```bash
podman rmi lscr.io/linuxserver/qbittorrent:latest
```

## Additional Resources

- [User Manual](docs/USER_MANUAL.md) - Detailed user guide
- [Contributing Guide](CONTRIBUTING.md) - How to contribute
- [Changelog](CHANGELOG.md) - Version history
- [qBitTorrent Documentation](https://www.qbittorrent.org/)
- [LinuxServer.io Documentation](https://docs.linuxserver.io/images/docker-qbittorrent)
- [RuTracker Plugin Repository](https://github.com/nbusseneau/qBittorrent-RuTracker-plugin)
- [Podman Documentation](https://docs.podman.io/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please read the [Contributing Guide](CONTRIBUTING.md) for details on submitting issues and pull requests.
