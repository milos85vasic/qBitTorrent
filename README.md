# qBitTorrent Docker/Podman Setup

A containerized qBitTorrent setup using Docker Compose or Podman Compose for easy deployment and management.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Scripts Reference](#scripts-reference)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Uninstallation](#uninstallation)

## Prerequisites

### Container Runtime

This setup supports both **Podman** and **Docker**. The scripts automatically detect which one is available.

| Runtime | Minimum Version | Notes |
|---------|----------------|-------|
| Podman  | 3.0+           | Preferred on Linux systems |
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

2. Create the config directory:
   ```bash
   mkdir -p config/qBittorrent
   ```

3. Start the service:
   ```bash
   ./start.sh
   ```

4. Access the Web UI at: **http://localhost:8085**

5. Login with default credentials:
   - Username: `admin`
   - Password: `adminadmin`

6. **Important**: Change the default password immediately after first login!

## Installation

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd qBitTorrent
```

### Step 2: Configure Environment

Edit `docker-compose.yml` to match your system:

```yaml
environment:
  - PUID=1000                    # Your user ID (run `id -u`)
  - PGID=1000                    # Your group ID (run `id -g`)
  - TZ=Europe/Moscow             # Your timezone
  - WEBUI_PORT=8085              # Web UI port
```

Find your IDs:
```bash
id -u    # Shows your UID
id -g    # Shows your GID
```

### Step 3: Configure Volumes

Edit the volume mappings in `docker-compose.yml`:

```yaml
volumes:
  - ./config:/config             # Configuration storage
  - /mnt/DATA:/DATA              # Your download location
```

### Step 4: Create Directories

```bash
mkdir -p config/qBittorrent
```

### Step 5: Start the Service

```bash
./start.sh
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PUID` | User ID for file permissions | `1000` | Yes |
| `PGID` | Group ID for file permissions | `1000` | Yes |
| `TZ` | Timezone (TZ format) | `Europe/Moscow` | Yes |
| `WEBUI_PORT` | Port for Web UI | `8085` | Yes |

### Timezone Examples

Common timezone values:
- `UTC`
- `Europe/London`
- `Europe/Berlin`
- `America/New_York`
- `Asia/Tokyo`
- `Australia/Sydney`

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
| `/mnt/DATA` | `/DATA` | Download destination |

## Usage

### Starting the Service

```bash
./start.sh
```

Options:
- Detects and uses Podman or Docker automatically
- Pulls the latest image if not present
- Starts the container in detached mode

### Stopping the Service

```bash
./stop.sh
```

Options:
- Gracefully stops the container
- Preserves all configuration and data

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
./start.sh status

# Restart container
./stop.sh && ./start.sh

# View resource usage
podman stats qbittorrent    # Podman
docker stats qbittorrent    # Docker
```

## Scripts Reference

### start.sh

Automated start script with Podman/Docker detection.

```bash
Usage: ./start.sh [OPTIONS]

Options:
  -h, --help      Show this help message
  -p, --pull      Pull latest image before starting
  -v, --verbose   Enable verbose output

Features:
  - Auto-detects Podman or Docker
  - Creates necessary directories
  - Validates configuration
  - Starts container in detached mode
```

### stop.sh

Graceful stop script.

```bash
Usage: ./stop.sh [OPTIONS]

Options:
  -h, --help      Show this help message
  -v, --verbose   Enable verbose output
  -r, --remove    Remove container after stopping

Features:
  - Graceful shutdown (30s timeout)
  - Preserves data and configuration
```

## Troubleshooting

### Common Issues

#### Permission Denied

**Symptom**: Cannot write to download directory

**Solution**: Ensure PUID/PGID match your user:
```bash
id -u    # Get your UID
id -g    # Get your GID
```

Update `docker-compose.yml`:
```yaml
- PUID=<your-uid>
- PGID=<your-gid>
```

#### Port Already in Use

**Symptom**: Error about port 8085 being in use

**Solution**: Change the port in `docker-compose.yml`:
```yaml
- WEBUI_PORT=8090    # Use different port
```

#### Container Won't Start

**Symptom**: Container exits immediately

**Solution**: Check logs for errors:
```bash
podman logs qbittorrent
# or
docker compose logs qbittorrent
```

#### Cannot Access Web UI

**Symptom**: Browser can't connect to Web UI

**Solutions**:
1. Check if container is running: `podman ps` or `docker ps`
2. Verify the port: `netstat -tlnp | grep 8085`
3. Check firewall: `sudo ufw status`
4. Try localhost: `http://127.0.0.1:8085`

#### Volume Mount Issues

**Symptom**: Downloads not appearing in expected location

**Solution**: Verify volume paths in `docker-compose.yml`:
```bash
ls -la /mnt/DATA    # Check host path exists
```

### Log Analysis

View detailed logs:
```bash
# Real-time logs
podman logs -f qbittorrent

# Last 100 lines
podman logs --tail=100 qbittorrent

# Logs with timestamps
podman logs -t qbittorrent
```

### Reset Configuration

To reset qBitTorrent to defaults:

```bash
./stop.sh
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

### Firewall Configuration

If using UFW:
```bash
sudo ufw allow 8085/tcp
sudo ufw reload
```

### Reverse Proxy Setup (Optional)

For HTTPS access, use a reverse proxy like Nginx or Traefik.

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
    }
}
```

## Uninstallation

### Remove Container

```bash
./stop.sh -r    # Stop and remove container
```

### Remove All Data (Including Configuration)

```bash
./stop.sh -r
rm -rf config/
```

### Remove Image

```bash
podman rmi lscr.io/linuxserver/qbittorrent:latest
```

## Additional Resources

- [qBitTorrent Documentation](https://www.qbittorrent.org/)
- [LinuxServer.io Documentation](https://docs.linuxserver.io/images/docker-qbittorrent)
- [Podman Documentation](https://docs.podman.io/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.
