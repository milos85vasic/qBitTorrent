# AGENTS.md - Guidelines for AI Agents

This document provides guidelines for AI coding agents working in this repository.

## Project Overview

This is a Docker/Podman Compose configuration project for running qBitTorrent in a containerized environment with RuTracker search plugin. It contains infrastructure-as-code rather than application code. The setup supports both Podman and Docker (auto-detected).

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

### Plugin Management

```bash
# Install RuTracker plugin for container
./install-plugin.sh

# Install for local qBittorrent
./install-plugin.sh --local

# Test plugin configuration
./install-plugin.sh --test

# Verify credentials only
./install-plugin.sh --verify
```

### Validation & Testing

```bash
# Quick validation (default)
./test.sh

# Run all validation tests
./test.sh --all

# Test RuTracker plugin only
./test.sh --plugin

# Run full test suite
./test.sh --full

# Test container status only
./test.sh --container

# Comprehensive test suite (detailed)
./tests/run_tests.sh

# Run specific test suite
./tests/run_tests.sh --suite plugin

# List available test suites
./tests/run_tests.sh --list

# Quick tests only
./tests/run_tests.sh --quick
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

## Project Structure

```
.
├── docker-compose.yml       # Main container configuration
├── start.sh                 # Start script (Podman/Docker auto-detect)
├── stop.sh                  # Stop script (Podman/Docker auto-detect)
├── test.sh                  # Validation and testing script
├── install-plugin.sh        # Plugin installation script
├── plugins/                 # Search plugins source
│   └── rutracker.py         # RuTracker search plugin
├── config/                  # qBitTorrent configuration (gitignored)
│   └── qBittorrent/         # Persistent config storage
│       ├── nova3/engines/   # Installed plugins
│       └── .gitkeep         # Keeps directory in git
├── docs/                    # Documentation
│   └── USER_MANUAL.md       # User manual
├── .env.example             # Example environment file
├── LICENSE                  # Apache 2.0 License
├── README.md                # Project documentation
└── AGENTS.md                # This file
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
- Use consistent error handling with exit codes

### Bash Script Template

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

detect_runtime() {
    if command -v podman &> /dev/null; then
        echo "podman"
    elif command -v docker &> /dev/null; then
        echo "docker"
    fi
}
```

### Python (Plugin Code)

- Follow PEP 8 style guide
- Use type hints where appropriate
- Add docstrings to functions and classes
- Handle exceptions gracefully
- Support environment variables for configuration
- Maintain backward compatibility with qBittorrent API

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

- Use uppercase with underscores: `PUID`, `WEBUI_PORT`, `RUTRACKER_USERNAME`, `QBITTORRENT_DATA_DIR`
- Document each variable with inline comments
- Keep sensitive values in `.env` files (add to .gitignore)
- Provide sensible defaults where possible
- Support multiple credential sources (project .env, ~/.qbit.env, environment)

### Data Directory Configuration

The `QBITTORRENT_DATA_DIR` environment variable controls where downloads are stored:

| Variable | Description | Default |
|----------|-------------|---------|
| `QBITTORRENT_DATA_DIR` | Base directory for all downloads | `/mnt/DATA` |

**Directory Structure Created Automatically:**

| Path | Purpose |
|------|---------|
| `$QBITTORRENT_DATA_DIR/` | Main download directory |
| `$QBITTORRENT_DATA_DIR/Incomplete/` | Incomplete/partial downloads |
| `$QBITTORRENT_DATA_DIR/Torrents/All/` | All .torrent files |
| `$QBITTORRENT_DATA_DIR/Torrents/Completed/` | Completed .torrent files |

**Configuration Sources (in priority order):**
1. Project `.env` file (`./.env`)
2. Home directory config (`~/.qbit.env`)
3. Shell environment (from `~/.bashrc` exports)
4. Default value (`/mnt/DATA`)

### Naming Conventions

- **Files**: lowercase with hyphens: `docker-compose.yml`, `start.sh`
- **Directories**: lowercase: `config/`, `plugins/`, `docs/`
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

### Plugin Issues

```bash
# Test plugin configuration
./install-plugin.sh --test

# Verify credentials
./install-plugin.sh --verify

# Check plugin syntax
python3 -m py_compile plugins/rutracker.py

# Test plugin loading manually
cd plugins && python3 -c "import rutracker; print(rutracker.CONFIG.username)"
```

### Common Issues

1. **Permission denied**: Ensure PUID/PGID match your user's UID/GID
2. **Port conflicts**: Check if WEBUI_PORT is already in use
3. **Volume mount failures**: Verify host paths exist and are accessible
4. **Network issues**: With `network_mode: host`, ensure no firewall blocking
5. **Plugin not loading**: Check credentials in .env file
6. **RuTracker login failed**: Verify credentials and check for CAPTCHA

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

## Plugin Architecture

### Credential Loading Priority

The RuTracker plugin loads credentials from multiple sources in order:

1. Environment variables (`RUTRACKER_USERNAME`, `RUTRACKER_PASSWORD`)
2. Project `.env` file (`./.env`)
3. Home directory config (`~/.qbit.env`)
4. Shell environment (from `~/.bashrc` exports)

### Plugin Installation Locations

| Target | Path |
|--------|------|
| Container | `./config/qBittorrent/nova3/engines/` |
| Local Linux | `~/.local/share/qBittorrent/nova3/engines/` |
| Local macOS | `~/Library/Application Support/qBittorrent/nova3/engines/` |

## Security Considerations

- Never commit sensitive data (passwords, API keys) to repository
- `.env` files are in `.gitignore` and must not be committed
- Change default Web UI credentials immediately after first login
- Keep qBitTorrent version updated for security patches
- Consider using VPN for torrent traffic (not configured in this setup)
- Review container permissions and capabilities
- Store RuTracker credentials securely using environment files

## Git Workflow

### Commit Messages

- Use present tense: "Add environment variable" not "Added"
- Be descriptive but concise
- Reference issues if applicable

### What to Commit

- Configuration files: `docker-compose.yml`
- Scripts: `start.sh`, `stop.sh`, `test.sh`, `install-plugin.sh`
- Plugin source: `plugins/rutracker.py`
- Documentation: `README.md`, `AGENTS.md`, `docs/USER_MANUAL.md`
- Example config: `.env.example`
- Ignore: `config/` contents, `.env` files, plugin icons

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
6. **Validation**: Run `./test.sh --full` before committing changes
7. **Security**: Never commit credentials or sensitive data

## Testing

### Before Committing

Always run tests before committing changes:

```bash
# Quick validation
./test.sh

# Full test suite
./test.sh --full
```

### Test Categories

| Test | Command | Description |
|------|---------|-------------|
| Quick | `./test.sh` | Basic validation |
| All | `./test.sh --all` | All validation tests |
| Plugin | `./test.sh --plugin` | Plugin configuration |
| Full | `./test.sh --full` | Complete test suite |
| Container | `./test.sh --container` | Container status only |

### Manual Testing Checklist

1. [ ] Start container: `./start.sh`
2. [ ] Check container status: `./start.sh -s`
3. [ ] Access Web UI: http://localhost:8085
4. [ ] Login with credentials
5. [ ] Check RuTracker plugin in search engines
6. [ ] Test search functionality
7. [ ] Stop container: `./stop.sh`

## Extending the Configuration

To add additional services:

1. Add new service block in `docker-compose.yml`
2. Document purpose and configuration
3. Test inter-service communication if applicable
4. Update README.md with new service information
5. Run validation tests: `./test.sh --all`

To add additional plugins:

1. Add `.py` file to `plugins/` directory
2. Update `install-plugin.sh` if needed
3. Document in README.md
4. Test plugin loading: `./install-plugin.sh --test`

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

# Check plugin syntax
python3 -m py_compile plugins/rutracker.py

# Test bash script syntax
bash -n start.sh
bash -n stop.sh
```

## License

This project is licensed under Apache 2.0. When contributing, ensure all code is compatible with this license.
