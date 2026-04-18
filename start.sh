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

cleanup_stale_config() {
    local stale_config="$SCRIPT_DIR/config/qBittorrent/qBittorrent.conf"
    local correct_config="$SCRIPT_DIR/config/qBittorrent/config/qBittorrent.conf"
    
    if [[ -f "$stale_config" ]] && [[ ! -L "$stale_config" ]]; then
        if grep -q "SavePath=/downloads/" "$stale_config" 2>/dev/null || \
           grep -q "DefaultSavePath=/downloads/" "$stale_config" 2>/dev/null; then
            print_warning "Found stale config with incorrect paths: $stale_config"
            print_info "Backing up and removing stale config..."
            
            if mv "$stale_config" "${stale_config}.backup.$(date +%s)" 2>/dev/null; then
                print_success "Stale config backed up and removed"
            elif rm -f "$stale_config" 2>/dev/null; then
                print_success "Stale config removed"
            else
                print_warning "Could not remove stale config (permission denied)"
                print_info "The correct config is being used at: config/qBittorrent/config/qBittorrent.conf"
            fi
        fi
    fi
}

_ensure_webui_credentials() {
    local config_file="$1"
    local webui_port="${WEBUI_PORT:-7185}"

    if [[ ! -f "$config_file" ]]; then
        return 0
    fi

    print_info "Ensuring WebUI credentials and port in: $config_file"

    if grep -q "^WebUI\\\\Port=" "$config_file" 2>/dev/null; then
        sed -i "s/^WebUI\\\\Port=.*/WebUI\\\\Port=${webui_port}/" "$config_file"
    fi

    if grep -q "^WebUI\\\\Username=" "$config_file" 2>/dev/null; then
        sed -i 's/^WebUI\\Username=.*/WebUI\\Username=admin/' "$config_file"
    fi

    local pbkdf2_hash='@ByteArray(XGCniD5hOQPEcE510BED2Q==:jLIBnLj5eCBZjRCvtE7dTSutDtS8mBQNKQ6rq/W3MszKNsKBjM2/8Ur9fxsADvQeh1wntKorznkorETYAFZawQ==)'
    if grep -q "^WebUI\\\\Password_PBKDF2=" "$config_file" 2>/dev/null; then
        sed -i "s|^WebUI\\\\Password_PBKDF2=.*|WebUI\\\\Password_PBKDF2=${pbkdf2_hash}|" "$config_file"
    fi

    local dup_lines
    dup_lines=$(grep -n "^\\[Application\\]$" "$config_file" 2>/dev/null | tail -n +2 | cut -d: -f1 | sort -rn || true)
    for line_num in $dup_lines; do
        sed -i "${line_num}d" "$config_file"
    done
}

update_qbittorrent_config() {
    local template_config="$SCRIPT_DIR/config/qBittorrent/config/qBittorrent.conf"
    local active_config="$SCRIPT_DIR/config/qBittorrent/qBittorrent.conf"
    local config_dir
    config_dir=$(dirname "$template_config")

    if [[ ! -d "$config_dir" ]]; then
        mkdir -p "$config_dir"
    fi

    if [[ ! -f "$template_config" ]]; then
        print_info "Creating default qBittorrent configuration..."
        cat > "$template_config" << EOF
[LegalNotice]
Accepted=true

[BitTorrent]
Session\DefaultSavePath=/downloads
Session\TempPath=/downloads/Incomplete
Session\TempPathEnabled=true
Session\IncompleteFilesExtension=.!qB

[Preferences]
Downloads\SavePath=/downloads
Downloads\TempPath=/downloads/Incomplete
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
WebUI\Port=${WEBUI_PORT:-7185}
WebUI\Address=*
WebUI\Username=admin
WebUI\Password_PBKDF2="@ByteArray(XGCniD5hOQPEcE510BED2Q==:jLIBnLj5eCBZjRCvtE7dTSutDtS8mBQNKQ6rq/W3MszKNsKBjM2/8Ur9fxsADvQeh1wntKorznkorETYAFZawQ==)"
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

    _ensure_webui_credentials "$template_config"
    _ensure_webui_credentials "$active_config"

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

    if [[ "$CONTAINER_RUNTIME" == "podman" ]]; then
        podman unshare chmod -R a+rw config/ 2>/dev/null || true
    fi

    print_success "Directories created"
}

pull_image() {
    print_info "Pulling latest image..."
    $COMPOSE_CMD pull
    print_success "Image pulled successfully"
}

copy_plugins() {
    print_info "Installing search plugins..."
    
    local engines_dir="config/qBittorrent/nova3/engines"
    
    if [[ ! -d "plugins" ]]; then
        print_warning "No plugins directory found"
        return 0
    fi
    
    local copy_cmd="cp"
    if [[ "$CONTAINER_RUNTIME" == "podman" ]]; then
        copy_cmd="podman unshare cp"
    fi
    
    for plugin in plugins/*.py; do
        if [[ -f "$plugin" ]]; then
            $copy_cmd "$plugin" "$engines_dir/"
            print_success "Installed: $(basename "$plugin")"
        fi
    done
    
    for icon in plugins/*.png; do
        if [[ -f "$icon" ]]; then
            $copy_cmd "$icon" "$engines_dir/"
        fi
    done
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

ensure_webui_password() {
    local webui_port="${WEBUI_PORT:-7185}"
    local max_attempts=30
    local attempt=0

    print_info "Waiting for WebUI to be ready..."
    while [[ $attempt -lt $max_attempts ]]; do
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${webui_port}/" 2>/dev/null | grep -q "200"; then
            break
        fi
        ((attempt++))
        sleep 1
    done

    if [[ $attempt -ge $max_attempts ]]; then
        print_warning "WebUI not ready, skipping password setup"
        return 0
    fi

    local temp_pass
    temp_pass=$($CONTAINER_RUNTIME logs qbittorrent 2>&1 | grep "temporary password" | tail -1 | grep -oP 'temporary password is provided for this session: \K.*' || true)

    if [[ -z "$temp_pass" ]]; then
        print_info "No temporary password found, trying direct login"
        local login_result
        login_result=$(curl -s -c /tmp/qbit_setup -X POST "http://localhost:${webui_port}/api/v2/auth/login" -d "username=admin&password=admin" 2>/dev/null || true)
        if [[ "$login_result" == "Ok." ]]; then
            print_success "WebUI login with admin/admin successful"
            return 0
        fi
        print_warning "Could not determine WebUI password"
        return 0
    fi

    local login_result
    login_result=$(curl -s -c /tmp/qbit_setup -X POST "http://localhost:${webui_port}/api/v2/auth/login" -d "username=admin&password=${temp_pass}" 2>/dev/null || true)

    if [[ "$login_result" != "Ok." ]]; then
        print_warning "Could not login with temp password"
        return 0
    fi

    curl -s -b /tmp/qbit_setup -X POST "http://localhost:${webui_port}/api/v2/app/setPreferences" \
        -d 'json={"web_ui_password":"admin"}' 2>/dev/null || true

    rm -f /tmp/qbit_setup 2>/dev/null
    print_success "WebUI password set to admin"
}

show_status() {
    echo ""
    print_info "Container Status:"
    $COMPOSE_CMD ps
    echo ""
    print_success "qBitTorrent Web UI: http://localhost:${WEBUI_PORT:-7185}"
    print_success "Merge Search Dashboard: http://localhost:${MERGE_SERVICE_PORT:-7187}/"
    print_info "Default credentials: admin / admin"
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

build_frontend() {
    if [[ ! -d "$SCRIPT_DIR/frontend" ]]; then
        print_warning "frontend/ directory not found, skipping Angular build"
        return 0
    fi

    if ! command -v ng &> /dev/null; then
        print_warning "Angular CLI not found, skipping frontend build"
        return 0
    fi

    print_info "Building Angular frontend..."
    cd "$SCRIPT_DIR/frontend"
    if ng build --configuration production 2>&1; then
        print_success "Angular frontend built successfully"
    else
        print_warning "Angular build failed — container will serve fallback or old assets"
    fi
    cd "$SCRIPT_DIR"
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
    --no-build      Skip Angular frontend build

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
    local build_frontend_flag=true

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
            --no-build)
                build_frontend_flag=false
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
    cleanup_stale_config
    update_qbittorrent_config
    create_data_directories

    if [[ "$build_frontend_flag" == true ]]; then
        build_frontend
    fi

    if [[ "$install_plugins" == true ]]; then
        copy_plugins
    fi

    if [[ "$pull_image_flag" == true ]]; then
        pull_image
    fi

    start_container
    wait_for_container
    ensure_webui_password
    show_status
}

main "$@"
