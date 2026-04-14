#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

print_test_header() { echo -e "\n${BLUE}========================================${NC}"; echo -e "${BLUE}TEST: $1${NC}"; echo -e "${BLUE}========================================${NC}"; }
print_pass() { echo -e "${GREEN}[PASS]${NC} $1"; TESTS_PASSED=$((TESTS_PASSED + 1)); }
print_fail() { echo -e "${RED}[FAIL]${NC} $1"; TESTS_FAILED=$((TESTS_FAILED + 1)); }
print_skip() { echo -e "${YELLOW}[SKIP]${NC} $1"; }
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }

test_file_exists() {
    local file="$1"
    local description="${2:-$file}"
    if [[ -f "$file" ]]; then
        print_pass "$description exists"
        return 0
    else
        print_fail "$description exists (missing: $file)"
        return 1
    fi
}

test_directory_exists() {
    local dir="$1"
    local description="${2:-$dir}"
    if [[ -d "$dir" ]]; then
        print_pass "$description exists"
        return 0
    else
        print_fail "$description exists (missing: $dir)"
        return 1
    fi
}

test_file_executable() {
    local file="$1"
    if [[ -x "$file" ]]; then
        print_pass "$file is executable"
        return 0
    else
        print_fail "$file is executable"
        return 1
    fi
}

test_env_var() {
    local var_name="$1"
    local var_value="${!var_name:-}"
    if [[ -n "$var_value" ]]; then
        print_pass "Environment variable $var_name is set"
        return 0
    else
        print_fail "Environment variable $var_name is set"
        return 1
    fi
}

test_env_file() {
    local env_file="$1"
    if [[ -f "$env_file" ]]; then
        if grep -q "RUTRACKER_USERNAME=" "$env_file" 2>/dev/null || grep -q "RUTRACKER_USER=" "$env_file" 2>/dev/null; then
            local username
            username=$(grep -E "^RUTRACKER_(USERNAME|USER)=" "$env_file" 2>/dev/null | head -1 | cut -d'=' -f2)
            if [[ "$username" != "your_username_here" && "$username" != "YOUR_USERNAME_HERE" && -n "$username" ]]; then
                print_pass ".env file exists and credentials are configured"
                return 0
            else
                print_fail ".env file exists but credentials are not configured"
                return 1
            fi
        else
            print_fail ".env file is missing required variables"
            return 1
        fi
    else
        print_fail ".env file exists"
        return 1
    fi
}

test_qbittorrent_data_dir() {
    local data_dir="${QBITTORRENT_DATA_DIR:-/mnt/DATA}"
    
    print_info "QBITTORRENT_DATA_DIR: $data_dir"
    
    if [[ -n "$data_dir" ]]; then
        print_pass "QBITTORRENT_DATA_DIR is set: $data_dir"
    else
        print_fail "QBITTORRENT_DATA_DIR is not set"
        return 1
    fi
    
    if [[ -d "$data_dir" ]]; then
        print_pass "Data directory exists: $data_dir"
    else
        print_info "Data directory will be created on first run: $data_dir"
    fi
    
    return 0
}

test_qbittorrent_config() {
    local config_file="$SCRIPT_DIR/config/qBittorrent/config/qBittorrent.conf"
    
    if [[ -f "$config_file" ]]; then
        print_pass "qBittorrent config file exists"
        
        if grep -q "DefaultSavePath=/DATA" "$config_file" 2>/dev/null; then
            print_pass "Config has correct download path"
        else
            print_fail "Config has incorrect download path (should be /DATA)"
            return 1
        fi
        
        if grep -q "TempPath=/DATA/Incomplete" "$config_file" 2>/dev/null; then
            print_pass "Config has correct incomplete path"
        else
            print_fail "Config has incorrect incomplete path (should be /DATA/Incomplete)"
            return 1
        fi
    else
        print_info "qBittorrent config will be created on first run"
    fi
    
    return 0
}

test_no_stale_config() {
    local stale_config="$SCRIPT_DIR/config/qBittorrent/qBittorrent.conf"
    
    if [[ -f "$stale_config" ]] && [[ ! -L "$stale_config" ]]; then
        if grep -q "SavePath=/downloads/" "$stale_config" 2>/dev/null || \
           grep -q "DefaultSavePath=/downloads/" "$stale_config" 2>/dev/null; then
            print_fail "Stale config file with wrong paths detected: config/qBittorrent/qBittorrent.conf"
            print_info "Run ./start.sh to clean up stale config"
            return 1
        fi
    fi
    
    print_pass "No stale config files detected"
    return 0
}

test_volume_mapping() {
    local compose_file="$SCRIPT_DIR/docker-compose.yml"
    
    if [[ -f "$compose_file" ]]; then
        if grep -q '\${QBITTORRENT_DATA_DIR:-/mnt/DATA}:/DATA' "$compose_file" 2>/dev/null; then
            print_pass "Volume mapping is correct (DATA directory)"
        else
            print_fail "Volume mapping might be incorrect"
            return 1
        fi
    fi
    
    return 0
}

test_container_write_permissions() {
    local container_name="${1:-qbittorrent}"
    
    if command -v podman &> /dev/null; then
        if podman ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
            if podman exec "$container_name" sh -c 'touch /DATA/.write_test && rm /DATA/.write_test' 2>/dev/null; then
                print_pass "Container can write to /DATA directory"
                return 0
            else
                print_fail "Container cannot write to /DATA directory (check permissions)"
                return 1
            fi
        else
            print_skip "Container write test (container not running)"
            return 0
        fi
    elif command -v docker &> /dev/null; then
        if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
            if docker exec "$container_name" sh -c 'touch /DATA/.write_test && rm /DATA/.write_test' 2>/dev/null; then
                print_pass "Container can write to /DATA directory"
                return 0
            else
                print_fail "Container cannot write to /DATA directory (check permissions)"
                return 1
            fi
        else
            print_skip "Container write test (container not running)"
            return 0
        fi
    else
        print_skip "Container write test (no container runtime)"
        return 0
    fi
}

test_docker_compose_syntax() {
    local compose_file="$1"
    if command -v docker &> /dev/null; then
        if docker compose -f "$compose_file" config &> /dev/null; then
            print_pass "docker-compose.yml syntax is valid"
            return 0
        else
            print_fail "docker-compose.yml syntax is valid"
            docker compose -f "$compose_file" config 2>&1 || true
            return 1
        fi
    elif command -v podman-compose &> /dev/null; then
        if podman-compose -f "$compose_file" config &> /dev/null; then
            print_pass "docker-compose.yml syntax is valid"
            return 0
        else
            print_fail "docker-compose.yml syntax is valid"
            return 1
        fi
    else
        print_skip "docker-compose.yml syntax (no container runtime available)"
        return 0
    fi
}

test_python_syntax() {
    local py_file="$1"
    if command -v python3 &> /dev/null; then
        if python3 -m py_compile "$py_file" 2>/dev/null; then
            print_pass "$py_file has valid Python syntax"
            return 0
        else
            print_fail "$py_file has valid Python syntax"
            python3 -m py_compile "$py_file" 2>&1 || true
            return 1
        fi
    else
        print_skip "$py_file syntax check (python3 not available)"
        return 0
    fi
}

test_bash_syntax() {
    local bash_file="$1"
    if bash -n "$bash_file" 2>/dev/null; then
        print_pass "$bash_file has valid Bash syntax"
        return 0
    else
        print_fail "$bash_file has valid Bash syntax"
        bash -n "$bash_file" 2>&1 || true
        return 1
    fi
}

test_container_runtime() {
    if command -v podman &> /dev/null; then
        print_pass "Podman is available ($(podman --version))"
        return 0
    elif command -v docker &> /dev/null; then
        print_pass "Docker is available ($(docker --version))"
        return 0
    else
        print_fail "Container runtime (Podman or Docker)"
        return 1
    fi
}

test_compose_command() {
    if command -v podman-compose &> /dev/null; then
        print_pass "podman-compose is available"
        return 0
    elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
        print_pass "docker compose is available"
        return 0
    elif command -v docker-compose &> /dev/null; then
        print_pass "docker-compose is available"
        return 0
    else
        print_fail "Compose command (podman-compose or docker compose)"
        return 1
    fi
}

test_container_running() {
    local container_name="${1:-qbittorrent}"
    if command -v podman &> /dev/null; then
        if podman ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
            print_pass "Container '$container_name' is running"
            return 0
        else
            print_fail "Container '$container_name' is running"
            return 1
        fi
    elif command -v docker &> /dev/null; then
        if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
            print_pass "Container '$container_name' is running"
            return 0
        else
            print_fail "Container '$container_name' is running"
            return 1
        fi
    else
        print_skip "Container running check (no container runtime)"
        return 0
    fi
}

test_port_available() {
    local port="${1:-7186}"
    if command -v ss &> /dev/null; then
        if ! ss -tln 2>/dev/null | grep -q ":${port} "; then
            print_pass "Port $port is available"
            return 0
        else
            print_fail "Port $port is available (already in use)"
            return 1
        fi
    elif command -v netstat &> /dev/null; then
        if ! netstat -tln 2>/dev/null | grep -q ":${port} "; then
            print_pass "Port $port is available"
            return 0
        else
            print_fail "Port $port is available (already in use)"
            return 1
        fi
    else
        print_skip "Port $port availability check"
        return 0
    fi
}

test_webui_accessible() {
    local port="${1:-7186}"
    local url="http://localhost:${port}"
    if command -v curl &> /dev/null; then
        if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null | grep -q "200\|401\|403"; then
            print_pass "Web UI is accessible at $url"
            return 0
        else
            print_fail "Web UI is accessible at $url"
            return 1
        fi
    elif command -v wget &> /dev/null; then
        if wget -q --spider --timeout=5 "$url" 2>/dev/null; then
            print_pass "Web UI is accessible at $url"
            return 0
        else
            print_fail "Web UI is accessible at $url"
            return 1
        fi
    else
        print_skip "Web UI accessibility check (curl/wget not available)"
        return 0
    fi
}

test_rutracker_plugin_credentials() {
    local py_file="$1"
    if [[ -f "$py_file" ]]; then
        if command -v python3 &> /dev/null; then
            local result
            result=$(python3 -c "
import os
import sys

sys.path.insert(0, '$SCRIPT_DIR/plugins')

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

username = os.environ.get('RUTRACKER_USERNAME', os.environ.get('RUTRACKER_USER', ''))
if username and username not in ['your_username_here', 'YOUR_USERNAME_HERE']:
    print('VALID')
else:
    print('INVALID')
" 2>/dev/null) || echo "ERROR"
            
            if [[ "$result" == "VALID" ]]; then
                print_pass "RuTracker plugin credentials are configured"
                return 0
            elif [[ "$result" == "INVALID" ]]; then
                print_fail "RuTracker plugin credentials are configured (not set)"
                return 1
            else
                print_fail "RuTracker plugin credentials check failed"
                return 1
            fi
        else
            print_skip "RuTracker plugin credentials check (python3 not available)"
            return 0
        fi
    else
        print_fail "RuTracker plugin file exists"
        return 1
    fi
}

run_all_tests() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}qBitTorrent Setup Validation Tests${NC}"
    echo -e "${GREEN}========================================${NC}"

    print_test_header "Project Structure"
    test_file_exists "docker-compose.yml" "docker-compose.yml" || true
    test_file_exists "start.sh" "start.sh" || true
    test_file_exists "stop.sh" "stop.sh" || true
    test_file_exists "test.sh" "test.sh" || true
    test_file_exists "install-plugin.sh" "install-plugin.sh" || true
    test_file_exists "README.md" "README.md" || true
    test_file_exists "AGENTS.md" "AGENTS.md" || true
    test_file_exists ".gitignore" ".gitignore" || true
    test_directory_exists "config/qBittorrent" "config/qBittorrent directory" || true
    test_file_exists "config/qBittorrent/.gitkeep" "config/qBittorrent/.gitkeep" || true

    print_test_header "Scripts"
    test_file_executable "start.sh" || true
    test_file_executable "stop.sh" || true
    test_file_executable "test.sh" || true
    test_file_executable "install-plugin.sh" || true
    test_bash_syntax "start.sh" || true
    test_bash_syntax "stop.sh" || true
    test_bash_syntax "test.sh" || true
    test_bash_syntax "install-plugin.sh" || true

    print_test_header "Plugin Files"
    test_directory_exists "plugins" "plugins directory" || true
    test_file_exists "plugins/rutracker.py" "RuTracker plugin" || true
    test_file_exists ".env.example" ".env.example" || true
    test_python_syntax "plugins/rutracker.py" || true

    print_test_header "Configuration"
    test_docker_compose_syntax "docker-compose.yml" || true
    if [[ -f ".env" ]]; then
        test_env_file ".env" || true
    else
        print_info ".env file not found (optional, credentials can be in ~/.qbit.env or exported)"
    fi

    print_test_header "Data Directory"
    test_qbittorrent_data_dir || true
    test_qbittorrent_config || true
    test_no_stale_config || true
    test_volume_mapping || true

    print_test_header "Dependencies"
    test_container_runtime || true
    test_compose_command || true

    print_test_header "Runtime Status"
    test_container_running "qbittorrent" || true
    
    if podman ps --format '{{.Names}}' 2>/dev/null | grep -q "^qbittorrent$" || \
       docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^qbittorrent$"; then
        test_webui_accessible "7186" || true
        test_container_write_permissions "qbittorrent" || true
    else
        print_skip "Web UI accessibility (container not running)"
        print_skip "Container write permissions (container not running)"
    fi
}

run_quick_test() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Quick Validation Test${NC}"
    echo -e "${GREEN}========================================${NC}\n"

    local failed=0

    test_file_exists "docker-compose.yml" || ((failed++)) || true
    test_file_executable "start.sh" || ((failed++)) || true
    test_file_executable "stop.sh" || ((failed++)) || true
    test_container_runtime || ((failed++)) || true
    test_qbittorrent_data_dir || ((failed++)) || true

    if [[ $failed -eq 0 ]]; then
        echo -e "\n${GREEN}All quick tests passed!${NC}"
        return 0
    else
        echo -e "\n${RED}Some tests failed. Please check the output above.${NC}"
        return 1
    fi
}

run_plugin_test() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}RuTracker Plugin Validation${NC}"
    echo -e "${GREEN}========================================${NC}\n"

    test_file_exists "plugins/rutracker.py" "RuTracker plugin file" || true
    test_python_syntax "plugins/rutracker.py" || true
    test_rutracker_plugin_credentials "plugins/rutracker.py" || true

    if [[ -f ".env" ]]; then
        test_env_file ".env" || true
    else
        print_info ".env not found, checking alternative locations..."
    fi

    if [[ -f "$HOME/.qbit.env" ]]; then
        test_env_file "$HOME/.qbit.env" || true
    fi

    if [[ -n "${RUTRACKER_USER:-}" ]] || [[ -n "${RUTRACKER_USERNAME:-}" ]]; then
        print_pass "RuTracker credentials found in environment variables"
    else
        print_info "RuTracker credentials not found in environment variables"
        print_info "Set RUTRACKER_USER and RUTRACKER_PASS in ~/.bashrc"
    fi
}

run_full_test() {
    run_all_tests
    echo ""
    run_plugin_test
}

show_summary() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Test Summary${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"

    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "\n${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "\n${RED}Some tests failed. Please review the output above.${NC}"
        return 1
    fi
}

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Validate and test qBitTorrent setup.

OPTIONS:
    -h, --help      Show this help message
    -a, --all       Run all validation tests
    -q, --quick     Run quick validation (default)
    -p, --plugin    Test RuTracker plugin only
    -f, --full      Run full test suite
    -c, --container Test container status only

EXAMPLES:
    $(basename "$0")              Run quick tests
    $(basename "$0") --all        Run all tests
    $(basename "$0") --plugin     Test plugin configuration
    $(basename "$0") --full       Run complete test suite

EOF
    exit 0
}

main() {
    local test_type="quick"

    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                ;;
            -a|--all)
                test_type="all"
                shift
                ;;
            -q|--quick)
                test_type="quick"
                shift
                ;;
            -p|--plugin)
                test_type="plugin"
                shift
                ;;
            -f|--full)
                test_type="full"
                shift
                ;;
            -c|--container)
                test_type="container"
                shift
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                ;;
        esac
    done

    case $test_type in
        all)
            run_all_tests
            show_summary
            ;;
        quick)
            run_quick_test
            ;;
        plugin)
            run_plugin_test
            show_summary
            ;;
        full)
            run_full_test
            show_summary
            ;;
        container)
            test_container_running "qbittorrent" || true
            test_webui_accessible "7186" || true
            ;;
    esac
}

main "$@"
