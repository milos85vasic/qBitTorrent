# AGENTS.md - Guidelines for AI Agents

This document provides guidelines for AI coding agents working in this repository.

## Project Overview

This is a Docker/Podman Compose configuration project for running qBitTorrent in a containerized environment. It contains infrastructure-as-code rather than application code. The setup supports both Podman and Docker (auto-detected).

## Build/Run/Test Commands

### Using Helper Scripts (Recommended)

```bash
# Start qBitTorrent container
./start.sh

# Start with latest image pull
./start.sh -p

# Stop container
./stop.sh

# Stop and remove container
./stop.sh -r

# Show container status
./start.sh -s
```

### Manual Docker/Podman Commands

```bash
# Start (Docker)
docker compose up -d

# Start (Podman)
podman-compose up -d

# Stop
docker compose down        # or podman-compose down

# View logs
docker compose logs -f qbittorrent

# Pull latest image
docker compose pull
```

### Validation Commands

```bash
# Validate docker-compose.yml syntax
docker compose config
podman-compose config

# Validate with verbose output
docker compose config --verbose
```

### Testing

This project has no automated tests. Manual verification:
1. Start container: `./start.sh`
2. Access Web UI: http://localhost:8085
3. Default credentials: admin / adminadmin (change immediately)
4. Verify download directory is accessible

## Project Structure

```
.
├── docker-compose.yml    # Main container configuration
├── start.sh              # Start script (Podman/Docker auto-detect)
├── stop.sh               # Stop script (Podman/Docker auto-detect)
├── config/               # qBitTorrent configuration (gitignored)
│   └── qBittorrent/      # Persistent config storage
│       └── .gitkeep      # Keeps directory in git
├── LICENSE               # Apache 2.0 License
├── README.md             # Project documentation
└── AGENTS.md             # This file
```

## Code Style Guidelines

### Bash Scripts

- Use `set -euo pipefail` for strict mode
- Add help text with `-h, --help` flags
- Use functions for modularity
- Prefer `[[ ]]` over `[ ]` for conditionals
- Quote all variables to prevent word splitting
- Use meaningful variable names
- Add color output for user feedback
- Check for command availability with `command -v`

### Bash Script Template

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_info() { echo "[INFO] $1"; }

detect_runtime() {
    if command -v podman &> /dev/null; then
        echo "podman"
    elif command -v docker &> /dev/null; then
        echo "docker"
    fi
}
```

### YAML/Docker Compose

- Use 2-space indentation
- Include version specification at top
- Use descriptive service names (e.g., `qbittorrent`, not `app`)
- Document environment variables with inline comments
- Group related configuration sections together
- Use consistent quoting style (prefer unquoted when safe)

### Formatting Example

```yaml
version: '3.8'
services:
  service-name:
    image: repository/image:tag
    container_name: descriptive-name
    environment:
      - VARIABLE_NAME=value    # Description of variable
    volumes:
      - ./local:/container     # Purpose of mount
    restart: unless-stopped
```

### Environment Variables

- Use uppercase with underscores: `PUID`, `WEBUI_PORT`
- Document each variable with inline comments
- Keep sensitive values in `.env` files (add to .gitignore)
- Provide sensible defaults where possible

### Naming Conventions

- **Files**: lowercase with hyphens: `docker-compose.yml`, `start.sh`
- **Directories**: lowercase: `config/`
- **Containers**: lowercase with hyphens: `qbittorrent`
- **Environment variables**: SCREAMING_SNAKE_CASE

### Comments

- Add comments for non-obvious configuration choices
- Document why specific ports or paths are used
- Explain any deviation from default settings
- Keep comments concise and relevant

## Error Handling

### Container Issues

```bash
# Check container logs for errors
docker compose logs qbittorrent
podman logs qbittorrent

# Inspect container state
docker inspect qbittorrent
podman inspect qbittorrent

# Verify network connectivity
docker exec qbittorrent ping -c 3 google.com
podman exec qbittorrent ping -c 3 google.com

# Check file permissions
ls -la config/
```

### Common Issues

1. **Permission denied**: Ensure PUID/PGID match your user's UID/GID
2. **Port conflicts**: Check if WEBUI_PORT is already in use
3. **Volume mount failures**: Verify host paths exist and are accessible
4. **Network issues**: With `network_mode: host`, ensure no firewall blocking

## Container Runtime Detection

The scripts auto-detect the container runtime in this order:
1. **Podman** - Preferred on Linux systems (rootless by default)
2. **Docker** - Fallback option

Detection logic:
```bash
if command -v podman &> /dev/null; then
    CONTAINER_RUNTIME="podman"
    COMPOSE_CMD="podman-compose"
elif command -v docker &> /dev/null; then
    CONTAINER_RUNTIME="docker"
    COMPOSE_CMD="docker compose"
fi
```

## Security Considerations

- Never commit sensitive data (passwords, API keys) to repository
- Change default Web UI credentials immediately after first login
- Keep qBitTorrent version updated for security patches
- Consider using VPN for torrent traffic (not configured in this setup)
- Review container permissions and capabilities

## Git Workflow

### Commit Messages

- Use present tense: "Add environment variable" not "Added"
- Be descriptive but concise
- Reference issues if applicable

### What to Commit

- Configuration files: `docker-compose.yml`
- Scripts: `start.sh`, `stop.sh`
- Documentation: `README.md`, `AGENTS.md`
- Ignore: `config/` contents, `.env` files

## Configuration Changes

When modifying `docker-compose.yml`:

1. Validate syntax: `docker compose config`
2. Test changes: `./start.sh`
3. Verify functionality: Check Web UI access
4. Review logs: `docker compose logs qbittorrent`
5. Document changes in commit message

## Best Practices

1. **Idempotency**: Changes should be repeatable without side effects
2. **Documentation**: Keep README.md updated with any changes
3. **Minimal privileges**: Use least permissive settings that work
4. **Resource limits**: Consider adding memory/CPU limits if needed
5. **Health checks**: Add healthcheck directive for critical services

## Extending the Configuration

To add additional services:

1. Add new service block in `docker-compose.yml`
2. Document purpose and configuration
3. Test inter-service communication if applicable
4. Update README.md with new service information

## Useful Commands Reference

```bash
# List all containers
docker ps -a
podman ps -a

# View resource usage
docker stats qbittorrent
podman stats qbittorrent

# Execute command in container
docker exec -it qbittorrent /bin/sh
podman exec -it qbittorrent /bin/sh

# Copy file from container
docker cp qbittorrent:/config/qBittorrent/config.conf ./
podman cp qbittorrent:/config/qBittorrent/config.conf ./

# Inspect container networks
docker network ls
podman network ls
```

## License

This project is licensed under Apache 2.0. When contributing, ensure all code is compatible with this license.
