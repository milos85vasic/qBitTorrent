#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CONTAINER_RUNTIME=""
COMPOSE_CMD=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

load_env_file() {
    local env_file="$1"
    if [[ -f "$env_file" ]]; then
        print_info "Loading environment from: $env_file"
        set -a
        while IFS= read -r line || [[ -n "$line" ]]; do
            [[ "$line" =~ ^[[:space:]]*# ]] && continue
            [[ "$line" =~ ^[[:space:]]*$ ]] && continue
            if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
                local key="${BASH_REMATCH[1]}"
                local value="${BASH_REMATCH[2]}"
                key="${key//[[:space:]]/}"
                value="${value#\"}"
                value="${value%\"}"
                value="${value#\'}"
                value="${value%\'}"
                if [[ -z "${!key:-}" ]]; then
                    export "$key"="$value"
                fi
            fi
        done < "$env_file"
        set +a
    fi
}

load_environment() {
    local env_priority=(
        "$SCRIPT_DIR/.env"
        "$HOME/.qbit.env"
    )
    
    for env_file in "${env_priority[@]}"; do
        load_env_file "$env_file"
    done
    
    QBITTORRENT_DATA_DIR="${QBITTORRENT_DATA_DIR:-/mnt/DATA}"
    export QBITTORRENT_DATA_DIR
    
    print_info "Data directory: $QBITTORRENT_DATA_DIR"
}

create_data_directories() {
    print_info "Creating data directories..."
    
    local data_dir="$QBITTORRENT_DATA_DIR"
    
    if [[ ! -d "$data_dir" ]]; then
        print_warning "Data directory does not exist: $data_dir"
        print_info "Attempting to create: $data_dir"
        mkdir -p "$data_dir" 2>/dev/null || {
            print_warning "Could not create data directory. This is expected if it's a mounted volume."
        }
    fi
    
    local subdirs=(
        "Incomplete"
        "Torrents/All"
        "Torrents/Completed"
    )
    
    for subdir in "${subdirs[@]}"; do
        local full_path="$data_dir/$subdir"
        if [[ ! -d "$full_path" ]]; then
            print_info "Creating: $full_path"
            mkdir -p "$full_path" 2>/dev/null || {
                print_warning "Could not create subdirectory: $full_path"
            }
        fi
    done
    
    print_success "Data directories verified"
}

update_qbittorrent_config() {
    local config_file="$SCRIPT_DIR/config/qBittorrent/config/qBittorrent.conf"
    local config_dir
    config_dir=$(dirname "$config_file")
    
    if [[ ! -d "$config_dir" ]]; then
        mkdir -p "$config_dir"
    fi
    
    if [[ ! -f "$config_file" ]]; then
        print_info "Creating default qBittorrent configuration..."
        cat > "$config_file" << 'EOF'
[LegalNotice]
Accepted=true

[BitTorrent]
Session\DefaultSavePath=/DATA
Session\TempPath=/DATA/Incomplete
Session\TempPathEnabled=true
Session\IncompleteFilesExtension=.!qB

[Preferences]
Downloads\SavePath=/DATA
Downloads\TempPath=/DATA/Incomplete
Downloads\TempPathEnabled=true
Downloads\IncompleteFilesExt=!qB
Downloads\PreAllocation=false
Downloads\UseIncompleteExtension=true

Advanced\AnnounceToAllTrackers=true
Advanced\AnnounceToAllTiers=true
Advanced\AnonymousMode=false
Advanced\AsyncIOThreadsCount=10
Advanced\FilePoolSize=5000
Advanced\CheckingMemoryUse=512
Advanced\OutgoingPortsMin=0
Advanced\OutgoingPortsMax=0

Connection\GlobalDLLimit=0
Connection\GlobalDLLimitAlt=0
Connection\GlobalUPLimit=0
Connection\GlobalUPLimitAlt=0
Connection\MaxConnections=500
Connection\MaxConnectionsPerTorrent=100
Connection\MaxUploads=20
Connection\MaxUploadsPerTorrent=4

General\Locale=en
General\UseRandomPort=true
General\ExitCheckDownloads=true

WebUI\Enabled=true
WebUI\Port=8085
WebUI\Address=*
WebUI\LocalHostAuth=false
WebUI\AuthSubnetWhitelist=0.0.0.0/0
WebUI\AuthSubnetWhitelistEnabled=true
WebUI\ServerDomains=*
WebUI\UseUPNP=true
WebUI\UseHTTPS=false

MailNotification\Enabled=false

RSS\AutoDownloader\Enabled=false

Search\PluginManager\UseProxy=false
Search\PluginManager\Enabled=true
EOF
        print_success "Default configuration created"
    fi
    
    print_success "qBittorrent configuration ready"
}

detect_container_runtime() {
    if command -v podman &> /dev/null; then
        CONTAINER_RUNTIME="podman"
        if command -v podman-compose &> /dev/null; then
            COMPOSE_CMD="podman-compose"
        else
            print_error "podman-compose not found. Please install it."
            exit 1
        fi
        print_info "Using Podman with podman-compose"
    elif command -v docker &> /dev/null; then
        CONTAINER_RUNTIME="docker"
        if docker compose version &> /dev/null; then
            COMPOSE_CMD="docker compose"
        elif command -v docker-compose &> /dev/null; then
            COMPOSE_CMD="docker-compose"
        else
            print_error "Docker Compose not found. Please install it."
            exit 1
        fi
        print_info "Using Docker with Docker Compose"
    else
        print_error "Neither Podman nor Docker found. Please install one of them."
        exit 1
    fi
}

check_prerequisites() {
    if [[ ! -f "docker-compose.yml" ]]; then
        print_error "docker-compose.yml not found in $SCRIPT_DIR"
        exit 1
    fi

    if ! $COMPOSE_CMD config &> /dev/null; then
        print_error "Invalid docker-compose.yml syntax"
        $COMPOSE_CMD config
        exit 1
    fi
}

create_directories() {
    print_info "Creating necessary directories..."
    mkdir -p config/qBittorrent
    mkdir -p config/qBittorrent/nova3/engines
    print_success "Directories created"
}

pull_image() {
    print_info "Pulling latest image..."
    $COMPOSE_CMD pull
    print_success "Image pulled successfully"
}

copy_plugins() {
    print_info "Installing search plugins..."
    
    if [[ -d "plugins" ]]; then
        for plugin in plugins/*.py; do
            if [[ -f "$plugin" ]]; then
                cp "$plugin" config/qBittorrent/nova3/engines/
                print_success "Installed: $(basename "$plugin")"
            fi
        done
        
        for icon in plugins/*.png; do
            if [[ -f "$icon" ]]; then
                cp "$icon" config/qBittorrent/nova3/engines/
            fi
        done
    fi
}

start_container() {
    print_info "Starting qBitTorrent container..."
    
    if $COMPOSE_CMD up -d; then
        print_success "Container started successfully"
    else
        print_error "Failed to start container"
        exit 1
    fi
}

wait_for_container() {
    print_info "Waiting for container to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [[ $attempt -lt $max_attempts ]]; do
        if $CONTAINER_RUNTIME ps --format '{{.Names}}' | grep -q "^qbittorrent$"; then
            sleep 2
            print_success "Container is ready"
            return 0
        fi
        ((attempt++))
        sleep 1
    done
    
    print_warning "Container may not be fully ready yet"
    return 0
}

show_status() {
    echo ""
    print_info "Container Status:"
    $COMPOSE_CMD ps
    echo ""
    print_success "qBitTorrent Web UI: http://localhost:8085"
    print_info "Default credentials: admin / adminadmin"
    print_warning "Remember to change the default password!"
    echo ""
    print_info "Data Directory: $QBITTORRENT_DATA_DIR"
    print_info "  Downloads:     $QBITTORRENT_DATA_DIR"
    print_info "  Incomplete:    $QBITTORRENT_DATA_DIR/Incomplete"
    print_info "  Torrents:      $QBITTORRENT_DATA_DIR/Torrents"
    echo ""
    
    if [[ -f "config/qBittorrent/nova3/engines/rutracker.py" ]]; then
        print_info "RuTracker plugin installed"
        if [[ -f ".env" ]] && grep -q "^RUTRACKER_USERNAME=.\+" ".env" 2>/dev/null; then
            print_success "RuTracker credentials configured"
        else
            print_warning "Configure RuTracker credentials in .env file"
        fi
    fi
}

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Start qBitTorrent container using Podman or Docker (auto-detected).

OPTIONS:
    -h, --help      Show this help message
    -p, --pull      Pull latest image before starting
    -v, --verbose   Enable verbose output
    -s, --status    Show container status only
    --no-plugins    Skip plugin installation

EXAMPLES:
    $(basename "$0")              Start container
    $(basename "$0") -p           Pull latest image and start
    $(basename "$0") --verbose    Start with verbose output

EOF
    exit 0
}

main() {
    local pull_image_flag=false
    local verbose=false
    local status_only=false
    local install_plugins=true

    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                ;;
            -p|--pull)
                pull_image_flag=true
                shift
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            -s|--status)
                status_only=true
                shift
                ;;
            --no-plugins)
                install_plugins=false
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                ;;
        esac
    done

    if [[ "$verbose" == true ]]; then
        set -x
    fi

    load_environment
    detect_container_runtime
    check_prerequisites

    if [[ "$status_only" == true ]]; then
        $COMPOSE_CMD ps
        exit 0
    fi

    create_directories
    update_qbittorrent_config
    create_data_directories

    if [[ "$install_plugins" == true ]]; then
        copy_plugins
    fi

    if [[ "$pull_image_flag" == true ]]; then
        pull_image
    fi

    start_container
    wait_for_container
    show_status
}

main "$@"
