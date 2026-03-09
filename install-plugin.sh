#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

PLUGINS=("rutracker" "rutor" "kinozal" "nnmclub")
LOCAL_MODE=false
INSTALL_ALL=false
SELECTED_PLUGINS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --local|-l)
            LOCAL_MODE=true
            shift
            ;;
        --all|-a)
            INSTALL_ALL=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS] [PLUGIN...]"
            echo ""
            echo "Options:"
            echo "  --local, -l     Install for local qBittorrent"
            echo "  --all, -a       Install all plugins"
            echo "  --help, -h      Show this help"
            echo ""
            echo "Available plugins: ${PLUGINS[*]}"
            echo ""
            echo "Examples:"
            echo "  $0 rutracker                    # Install RuTracker plugin"
            echo "  $0 --all                        # Install all plugins"
            echo "  $0 --local rutracker rutor      # Install plugins locally"
            exit 0
            ;;
        *)
            SELECTED_PLUGINS+=("$1")
            shift
            ;;
    esac
done

if [[ "${#SELECTED_PLUGINS[@]}" -eq 0 ]] && [[ "$INSTALL_ALL" == "false" ]]; then
    print_info "No plugins specified. Use --all to install all plugins or specify plugin names."
    print_info "Available plugins: ${PLUGINS[*]}"
    exit 1
fi

if [[ "$INSTALL_ALL" == "true" ]]; then
    SELECTED_PLUGINS=("${PLUGINS[@]}")
fi

install_plugin() {
    local plugin_name=$1
    local plugin_file="plugins/${plugin_name}.py"
    local plugin_icon="plugins/${plugin_name}.png"
    
    if [[ ! -f "$plugin_file" ]]; then
        print_error "Plugin file not found: $plugin_file"
        return 1
    fi
    
    if [[ "$LOCAL_MODE" == "true" ]]; then
        local engines_dir="$HOME/.local/share/qBittorrent/nova3/engines"
        mkdir -p "$engines_dir"
        print_info "Installing ${plugin_name} locally to: $engines_dir"
        cp "$plugin_file" "$engines_dir/"
        [[ -f "$plugin_icon" ]] && cp "$plugin_icon" "$engines_dir/"
    else
        # Install to local config directory
        local engines_dir="$SCRIPT_DIR/config/qBittorrent/nova3/engines"
        mkdir -p "$engines_dir"
        print_info "Installing ${plugin_name} to config dir: $engines_dir"
        cp "$plugin_file" "$engines_dir/"
        [[ -f "$plugin_icon" ]] && cp "$plugin_icon" "$engines_dir/"
        
        # Also copy to running container if it exists
        if command -v podman &> /dev/null && podman ps --format "{{.Names}}" | grep -q "qbittorrent"; then
            print_info "Copying ${plugin_name} to running container..."
            podman cp "$plugin_file" qbittorrent:/config/qBittorrent/nova3/engines/ 2>/dev/null || true
            [[ -f "$plugin_icon" ]] && podman cp "$plugin_icon" qbittorrent:/config/qBittorrent/nova3/engines/ 2>/dev/null || true
            print_success "${plugin_name} copied to container"
        elif command -v docker &> /dev/null && docker ps --format "{{.Names}}" | grep -q "qbittorrent"; then
            print_info "Copying ${plugin_name} to running container..."
            docker cp "$plugin_file" qbittorrent:/config/qBittorrent/nova3/engines/ 2>/dev/null || true
            [[ -f "$plugin_icon" ]] && docker cp "$plugin_icon" qbittorrent:/config/qBittorrent/nova3/engines/ 2>/dev/null || true
            print_success "${plugin_name} copied to container"
        fi
    fi
    
    print_success "${plugin_name} plugin installed"
}

# Download plugin icons
for plugin in "${SELECTED_PLUGINS[@]}"; do
    if [[ ! -f "plugins/${plugin}.png" ]]; then
        print_info "Downloading ${plugin} icon..."
        curl -sL "https://raw.githubusercontent.com/imDMG/qBt_SE/master/engines/${plugin}.png" -o "plugins/${plugin}.png" 2>/dev/null || \
        curl -sL "https://raw.githubusercontent.com/nbusseneau/qBittorrent-RuTracker-plugin/master/${plugin}.png" -o "plugins/${plugin}.png" 2>/dev/null || \
        print_info "Could not download ${plugin} icon (optional)"
    fi
done

# Install selected plugins
for plugin in "${SELECTED_PLUGINS[@]}"; do
    if [[ " ${PLUGINS[*]} " =~ " ${plugin} " ]]; then
        install_plugin "$plugin"
    else
        print_error "Unknown plugin: $plugin"
        print_info "Available plugins: ${PLUGINS[*]}"
    fi
done

if [[ "$LOCAL_MODE" == "false" ]]; then
    print_info "Restart container to load plugins: podman restart qbittorrent"
fi

print_success "Plugin installation complete!"
