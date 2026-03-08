#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

PLUGIN_NAME="rutracker"
PLUGIN_FILE="plugins/${PLUGIN_NAME}.py"
PLUGIN_ICON="plugins/${PLUGIN_NAME}.png"

download_rutracker_icon() {
    print_info "Downloading RuTracker icon..."
    
    if curl -sL "https://raw.githubusercontent.com/nbusseneau/qBittorrent-RuTracker-plugin/master/rutracker.png" -o "$PLUGIN_ICON" 2>/dev/null; then
        print_success "RuTracker icon downloaded"
        return 0
    elif wget -q "https://raw.githubusercontent.com/nbusseneau/qBittorrent-RuTracker-plugin/master/rutracker.png" -O "$PLUGIN_ICON" 2>/dev/null; then
        print_success "RuTracker icon downloaded"
        return 0
    else
        print_warning "Could not download RuTracker icon (optional)"
        return 1
    fi
}

find_engines_dir() {
    local possible_paths=(
        "$HOME/.local/share/qBittorrent/nova3/engines"
        "$HOME/.config/qBittorrent/nova3/engines"
        "$HOME/.local/share/data/qBittorrent/nova3/engines"
        "/config/qBittorrent/nova3/engines"
    )

    for path in "${possible_paths[@]}"; do
        if [[ -d "$path" ]]; then
            echo "$path"
            return 0
        fi
    done

    echo ""
    return 1
}

install_plugin_local() {
    print_info "Installing RuTracker plugin locally..."

    local engines_dir
    engines_dir=$(find_engines_dir)

    if [[ -z "$engines_dir" ]]; then
        engines_dir="$HOME/.local/share/qBittorrent/nova3/engines"
        print_info "Creating engines directory: $engines_dir"
        mkdir -p "$engines_dir"
    fi

    print_info "Installing to: $engines_dir"

    cp "$PLUGIN_FILE" "$engines_dir/"

    if [[ -f "$PLUGIN_ICON" ]]; then
        cp "$PLUGIN_ICON" "$engines_dir/"
    fi

    print_success "RuTracker plugin installed to $engines_dir"
    print_info "Restart qBittorrent to load the plugin"
}

install_plugin_container() {
    print_info "Installing RuTracker plugin for container..."

    local config_dir="$SCRIPT_DIR/config/qBittorrent"
    local engines_dir="$config_dir/nova3/engines"

    mkdir -p "$engines_dir"

    cp "$PLUGIN_FILE" "$engines_dir/"

    if [[ -f "$PLUGIN_ICON" ]]; then
        cp "$PLUGIN_ICON" "$engines_dir/"
    fi

    print_success "RuTracker plugin installed to $engines_dir"
    print_info "Plugin will be available after (re)starting the container"
}

verify_credentials() {
    print_info "Verifying RuTracker credentials..."

    local has_credentials=false
    local credential_sources=()

    if [[ -f "$SCRIPT_DIR/.env" ]]; then
        if grep -q "^RUTRACKER_USERNAME=.\+" "$SCRIPT_DIR/.env" && grep -q "^RUTRACKER_PASSWORD=.\+" "$SCRIPT_DIR/.env"; then
            local username
            username=$(grep "^RUTRACKER_USERNAME=" "$SCRIPT_DIR/.env" | cut -d'=' -f2)
            if [[ "$username" != "your_username_here" && -n "$username" ]]; then
                has_credentials=true
                credential_sources+=("$SCRIPT_DIR/.env")
            fi
        fi
    fi

    if [[ -f "$HOME/.qbit.env" ]]; then
        if grep -q "^RUTRACKER_USERNAME=.\+" "$HOME/.qbit.env" && grep -q "^RUTRACKER_PASSWORD=.\+" "$HOME/.qbit.env"; then
            local username
            username=$(grep "^RUTRACKER_USERNAME=" "$HOME/.qbit.env" | cut -d'=' -f2)
            if [[ "$username" != "your_username_here" && -n "$username" ]]; then
                has_credentials=true
                credential_sources+=("$HOME/.qbit.env")
            fi
        fi
    fi

    if [[ "$has_credentials" == true ]]; then
        print_success "RuTracker credentials found in: ${credential_sources[*]}"
        return 0
    else
        print_warning "RuTracker credentials not configured"
        print_info "Create .env file from .env.example and add your credentials"
        print_info "Or create ~/.qbit.env with RUTRACKER_USERNAME and RUTRACKER_PASSWORD"
        return 1
    fi
}

test_plugin_loading() {
    print_info "Testing plugin loading..."

    if ! command -v python3 &> /dev/null; then
        print_warning "Python3 not available, skipping plugin test"
        return 0
    fi

    local test_result
    test_result=$(python3 -c "
import sys
import os

sys.path.insert(0, '$SCRIPT_DIR/plugins')

try:
    # Load environment
    env_paths = [
        '$SCRIPT_DIR/.env',
        os.path.expanduser('~/.qbit.env'),
    ]
    for env_path in env_paths:
        if os.path.isfile(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ.setdefault(key.strip(), value.strip().strip('\"').strip(\"'\"))

    # Import plugin
    import rutracker
    
    # Check configuration
    if rutracker.CONFIG.username == 'YOUR_USERNAME_HERE':
        print('CREDENTIALS_NOT_SET')
    else:
        print('OK')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1) || echo "ERROR"

    case "$test_result" in
        OK)
            print_success "Plugin loads correctly with configured credentials"
            return 0
            ;;
        CREDENTIALS_NOT_SET)
            print_warning "Plugin loads but credentials are not configured"
            return 1
            ;;
        *)
            print_error "Plugin failed to load: $test_result"
            return 1
            ;;
    esac
}

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Install RuTracker search plugin for qBittorrent.

OPTIONS:
    -h, --help      Show this help message
    -l, --local     Install for local qBittorrent
    -c, --container Install for containerized qBittorrent (default)
    -t, --test      Test plugin configuration
    -v, --verify    Verify credentials only
    -a, --all       Install for both local and container

EXAMPLES:
    $(basename "$0")              Install for container
    $(basename "$0") --local      Install for local qBittorrent
    $(basename "$0") --all        Install for both
    $(basename "$0") --test       Test plugin configuration

ENVIRONMENT:
    Credentials can be configured in:
    - ./.env (in project directory)
    - ~/.qbit.env (in home directory)
    - ~/.bashrc (export RUTRACKER_USERNAME and RUTRACKER_PASSWORD)

EOF
    exit 0
}

main() {
    local install_local=false
    local install_container=false
    local test_only=false
    local verify_only=false

    if [[ $# -eq 0 ]]; then
        install_container=true
    fi

    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                ;;
            -l|--local)
                install_local=true
                shift
                ;;
            -c|--container)
                install_container=true
                shift
                ;;
            -t|--test)
                test_only=true
                shift
                ;;
            -v|--verify)
                verify_only=true
                shift
                ;;
            -a|--all)
                install_local=true
                install_container=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                ;;
        esac
    done

    if [[ ! -f "$PLUGIN_FILE" ]]; then
        print_error "Plugin file not found: $PLUGIN_FILE"
        exit 1
    fi

    if [[ "$verify_only" == true ]]; then
        verify_credentials
        exit $?
    fi

    if [[ "$test_only" == true ]]; then
        verify_credentials
        test_plugin_loading
        exit $?
    fi

    download_rutracker_icon || true

    if [[ "$install_local" == true ]]; then
        install_plugin_local
    fi

    if [[ "$install_container" == true ]]; then
        install_plugin_container
    fi

    echo ""
    verify_credentials || true
    echo ""

    print_success "Installation complete!"
    print_info "Configure credentials in .env or ~/.qbit.env if not done already"
    
    if [[ "$install_container" == true ]]; then
        print_info "Restart container with: ./stop.sh && ./start.sh"
    fi
}

main "$@"
