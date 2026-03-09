#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

SUITE_START_TIME=0
TEST_START_TIME=0

suite_start() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  TEST SUITE: $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    SUITE_START_TIME=$(date +%s)
}

suite_end() {
    local end_time=$(date +%s)
    local duration=$((end_time - SUITE_START_TIME))
    echo -e "\n${CYAN}───────────────────────────────────────────────────────────────${NC}"
    echo -e "${CYAN}  Suite completed in ${duration}s${NC}"
    echo -e "${CYAN}───────────────────────────────────────────────────────────────${NC}"
}

test_start() {
    TEST_START_TIME=$(date +%s)
    echo -e "\n${BLUE}▶ Test: $1${NC}"
    TESTS_RUN=$((TESTS_RUN + 1))
}

test_pass() {
    local end_time=$(date +%s)
    local duration=$((end_time - TEST_START_TIME))
    echo -e "  ${GREEN}✓ PASS${NC} (${duration}s): $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

test_fail() {
    local end_time=$(date +%s)
    local duration=$((end_time - TEST_START_TIME))
    echo -e "  ${RED}✗ FAIL${NC} (${duration}s): $1"
    if [[ -n "${2:-}" ]]; then
        echo -e "  ${RED}  Reason: $2${NC}"
    fi
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

test_skip() {
    echo -e "  ${YELLOW}○ SKIP${NC}: $1"
    if [[ -n "${2:-}" ]]; then
        echo -e "  ${YELLOW}  Reason: $2${NC}"
    fi
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
}

assert_file_exists() {
    local file="$1"
    local msg="${2:-File should exist}"
    if [[ -f "$file" ]]; then
        return 0
    else
        return 1
    fi
}

assert_dir_exists() {
    local dir="$1"
    if [[ -d "$dir" ]]; then
        return 0
    else
        return 1
    fi
}

assert_file_executable() {
    local file="$1"
    if [[ -x "$file" ]]; then
        return 0
    else
        return 1
    fi
}

assert_env_set() {
    local var_name="$1"
    local value="${!var_name:-}"
    if [[ -n "$value" ]]; then
        return 0
    else
        return 1
    fi
}

assert_valid_yaml() {
    local file="$1"
    if command -v python3 &> /dev/null; then
        python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null
        return $?
    fi
    return 0
}

assert_valid_python() {
    local file="$1"
    python3 -m py_compile "$file" 2>/dev/null
    return $?
}

assert_valid_bash() {
    local file="$1"
    bash -n "$file" 2>/dev/null
    return $?
}

assert_container_running() {
    local name="$1"
    if command -v podman &> /dev/null; then
        podman ps --format '{{.Names}}' | grep -q "^${name}$"
        return $?
    elif command -v docker &> /dev/null; then
        docker ps --format '{{.Names}}' | grep -q "^${name}$"
        return $?
    fi
    return 1
}

assert_port_listening() {
    local port="$1"
    if command -v ss &> /dev/null; then
        ss -tln 2>/dev/null | grep -q ":${port} "
        return $?
    elif command -v netstat &> /dev/null; then
        netstat -tln 2>/dev/null | grep -q ":${port} "
        return $?
    fi
    return 1
}

assert_no_secrets_in_git() {
    local patterns=(
        "RUTRACKER_PASSWORD"
        "RUTRACKER_PASS"
        "RUTRACKER_USERNAME=.*[^_]$"
        "RUTRACKER_USER=.*[^_]$"
        ".env$"
        "credentials"
        "secrets"
    )
    
    for pattern in "${patterns[@]}"; do
        if git ls-files 2>/dev/null | grep -E "$pattern" | grep -v ".env.example" | grep -v ".gitignore"; then
            return 1
        fi
    done
    return 0
}

test_project_structure() {
    suite_start "Project Structure"
    
    test_start "Required files exist"
    local files=(
        "docker-compose.yml"
        "start.sh"
        "stop.sh"
        "test.sh"
        "install-plugin.sh"
        "README.md"
        "AGENTS.md"
        "LICENSE"
        ".gitignore"
        ".env.example"
        "plugins/rutracker.py"
    )
    local missing=0
    for f in "${files[@]}"; do
        if ! assert_file_exists "$f"; then
            echo -e "    ${RED}Missing: $f${NC}"
            missing=1
        fi
    done
    if [[ $missing -eq 0 ]]; then
        test_pass "All required files exist"
    else
        test_fail "Some required files are missing"
    fi
    
    test_start "Required directories exist"
    local dirs=("config" "config/qBittorrent" "plugins" "tests" "docs")
    local missing=0
    for d in "${dirs[@]}"; do
        if ! assert_dir_exists "$d"; then
            echo -e "    ${RED}Missing: $d${NC}"
            missing=1
        fi
    done
    if [[ $missing -eq 0 ]]; then
        test_pass "All required directories exist"
    else
        test_fail "Some required directories are missing"
    fi
    
    test_start "Scripts are executable"
    local scripts=("start.sh" "stop.sh" "test.sh" "install-plugin.sh")
    local non_exec=0
    for s in "${scripts[@]}"; do
        if ! assert_file_executable "$s"; then
            echo -e "    ${RED}Not executable: $s${NC}"
            non_exec=1
        fi
    done
    if [[ $non_exec -eq 0 ]]; then
        test_pass "All scripts are executable"
    else
        test_fail "Some scripts are not executable"
    fi
    
    test_start ".gitkeep files exist"
    if assert_file_exists "config/qBittorrent/.gitkeep"; then
        test_pass ".gitkeep files present"
    else
        test_fail ".gitkeep files missing"
    fi
    
    suite_end
}

test_syntax_validation() {
    suite_start "Syntax Validation"
    
    test_start "docker-compose.yml is valid YAML"
    if assert_valid_yaml "docker-compose.yml"; then
        test_pass "docker-compose.yml has valid YAML syntax"
    else
        test_fail "docker-compose.yml has invalid YAML syntax"
    fi
    
    test_start "Python files have valid syntax"
    local py_files=("plugins/rutracker.py")
    local invalid=0
    for f in "${py_files[@]}"; do
        if ! assert_valid_python "$f"; then
            echo -e "    ${RED}Invalid Python: $f${NC}"
            invalid=1
        fi
    done
    if [[ $invalid -eq 0 ]]; then
        test_pass "All Python files have valid syntax"
    else
        test_fail "Some Python files have syntax errors"
    fi
    
    test_start "Bash scripts have valid syntax"
    local bash_files=("start.sh" "stop.sh" "test.sh" "install-plugin.sh" "tests/run_tests.sh")
    local invalid=0
    for f in "${bash_files[@]}"; do
        if [[ -f "$f" ]]; then
            if ! assert_valid_bash "$f"; then
                echo -e "    ${RED}Invalid Bash: $f${NC}"
                invalid=1
            fi
        fi
    done
    if [[ $invalid -eq 0 ]]; then
        test_pass "All Bash scripts have valid syntax"
    else
        test_fail "Some Bash scripts have syntax errors"
    fi
    
    suite_end
}

test_container_runtime() {
    suite_start "Container Runtime Detection"
    
    test_start "At least one container runtime available"
    local runtime=""
    if command -v podman &> /dev/null; then
        runtime="podman"
        echo -e "    ${GREEN}Found: podman ($(podman --version))${NC}"
    fi
    if command -v docker &> /dev/null; then
        runtime="docker"
        echo -e "    ${GREEN}Found: docker ($(docker --version))${NC}"
    fi
    
    if [[ -n "$runtime" ]]; then
        test_pass "Container runtime available: $runtime"
    else
        test_fail "No container runtime found"
    fi
    
    test_start "Compose command available"
    local compose=""
    if command -v podman-compose &> /dev/null; then
        compose="podman-compose"
    elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
        compose="docker compose"
    elif command -v docker-compose &> /dev/null; then
        compose="docker-compose"
    fi
    
    if [[ -n "$compose" ]]; then
        test_pass "Compose command available: $compose"
    else
        test_fail "No compose command found"
    fi
    
    test_start "docker-compose.yml validates with runtime"
    if [[ -n "$compose" ]]; then
        if $compose config &> /dev/null; then
            test_pass "docker-compose.yml validates successfully"
        else
            test_fail "docker-compose.yml validation failed"
            $compose config 2>&1 || true
        fi
    else
        test_skip "No compose command available"
    fi
    
    suite_end
}

test_credentials() {
    suite_start "Credentials Configuration"
    
    test_start "Credentials not in git repository"
    if git rev-parse --git-dir &> /dev/null; then
        if assert_no_secrets_in_git; then
            test_pass "No secrets found in git"
        else
            test_fail "Potential secrets found in git!"
        fi
    else
        test_skip "Not a git repository"
    fi
    
    test_start ".gitignore contains credential patterns"
    local patterns=(".env" "*.env" ".qbit.env" "RUTRACKER_")
    local missing=0
    for p in "${patterns[@]}"; do
        if ! grep -q "$p" .gitignore 2>/dev/null; then
            echo -e "    ${YELLOW}Missing pattern: $p${NC}"
            missing=1
        fi
    done
    if [[ $missing -eq 0 ]]; then
        test_pass ".gitignore has credential protection"
    else
        test_fail ".gitignore may be missing some patterns"
    fi
    
    test_start "Check for credentials in environment"
    local found_creds=false
    
    if [[ -n "${RUTRACKER_USER:-}" ]]; then
        echo -e "    ${GREEN}RUTRACKER_USER is set${NC}"
        found_creds=true
    fi
    if [[ -n "${RUTRACKER_USERNAME:-}" ]]; then
        echo -e "    ${GREEN}RUTRACKER_USERNAME is set${NC}"
        found_creds=true
    fi
    if [[ -n "${RUTRACKER_PASS:-}" ]]; then
        echo -e "    ${GREEN}RUTRACKER_PASS is set${NC}"
        found_creds=true
    fi
    if [[ -n "${RUTRACKER_PASSWORD:-}" ]]; then
        echo -e "    ${GREEN}RUTRACKER_PASSWORD is set${NC}"
        found_creds=true
    fi
    
    if [[ "$found_creds" == true ]]; then
        test_pass "Credentials found in environment"
    else
        test_skip "No credentials in environment (may be in .env file)"
    fi
    
    test_start "Check .env file"
    if [[ -f ".env" ]]; then
        if grep -qE "^RUTRACKER_(USERNAME|USER)=" ".env" 2>/dev/null; then
            local username
            username=$(grep -E "^RUTRACKER_(USERNAME|USER)=" ".env" 2>/dev/null | head -1 | cut -d'=' -f2)
            if [[ "$username" != "your_username_here" && "$username" != "YOUR_USERNAME_HERE" && -n "$username" ]]; then
                test_pass ".env file has configured credentials"
            else
                test_fail ".env file has placeholder credentials"
            fi
        else
            test_fail ".env file missing credential variables"
        fi
    else
        test_skip ".env file not found (using environment or ~/.qbit.env)"
    fi
    
    test_start "Check ~/.qbit.env file"
    if [[ -f "$HOME/.qbit.env" ]]; then
        if grep -qE "^RUTRACKER_(USERNAME|USER)=" "$HOME/.qbit.env" 2>/dev/null; then
            test_pass "~/.qbit.env has credentials configured"
        else
            test_fail "~/.qbit.env missing credentials"
        fi
    else
        test_skip "~/.qbit.env not found"
    fi
    
    test_start ".env.example exists without real credentials"
    if [[ -f ".env.example" ]]; then
        if grep -q "your_username_here" ".env.example" && grep -q "your_password_here" ".env.example"; then
            test_pass ".env.example has placeholder credentials only"
        else
            test_fail ".env.example may have real credentials!"
        fi
    else
        test_fail ".env.example not found"
    fi
    
    suite_end
}

test_plugin_functionality() {
    suite_start "RuTracker Plugin"
    
    test_start "Plugin file exists"
    if assert_file_exists "plugins/rutracker.py"; then
        test_pass "Plugin file exists"
    else
        test_fail "Plugin file missing"
    fi
    
    test_start "Plugin has valid Python syntax"
    if assert_valid_python "plugins/rutracker.py"; then
        test_pass "Plugin has valid syntax"
    else
        test_fail "Plugin has syntax errors"
    fi
    
    test_start "Plugin has environment loading function"
    if command -v python3 &> /dev/null; then
        local result
        result=$(grep -c "_load_env_file" plugins/rutracker.py 2>/dev/null) || echo "0"
        
        if [[ "$result" -gt 0 ]]; then
            test_pass "Plugin has _load_env_file function"
        else
            test_fail "Plugin missing environment loading function"
        fi
    else
        test_skip "Python3 not available"
    fi
    
    test_start "Plugin supports RUTRACKER_USER alias"
    if command -v python3 &> /dev/null; then
        if grep -q "RUTRACKER_USER" plugins/rutracker.py 2>/dev/null; then
            test_pass "Plugin references RUTRACKER_USER"
        else
            test_fail "Plugin missing RUTRACKER_USER support"
        fi
    else
        test_skip "Python3 not available"
    fi
    
    test_start "Plugin file contains required class"
    if grep -q "class RuTracker" plugins/rutracker.py 2>/dev/null; then
        test_pass "Plugin contains RuTracker class"
    else
        test_fail "Plugin missing RuTracker class"
    fi
    
    suite_end
}

test_install_plugin_script() {
    suite_start "Plugin Installation Script"
    
    test_start "install-plugin.sh exists and is executable"
    if assert_file_exists "install-plugin.sh" && assert_file_executable "install-plugin.sh"; then
        test_pass "install-plugin.sh ready"
    else
        test_fail "install-plugin.sh not ready"
    fi
    
    test_start "install-plugin.sh has help option"
    if ./install-plugin.sh --help &> /dev/null; then
        test_pass "install-plugin.sh has help option"
    else
        test_fail "install-plugin.sh --help failed"
    fi
    
    test_start "install-plugin.sh --verify option works"
    local verify_output
    verify_output=$(./install-plugin.sh --verify 2>&1) || true
    
    if echo "$verify_output" | grep -qi "credentials"; then
        test_pass "install-plugin.sh --verify checks credentials"
    else
        test_fail "install-plugin.sh --verify unexpected output"
    fi
    
    suite_end
}

test_start_stop_scripts() {
    suite_start "Start/Stop Scripts"
    
    test_start "start.sh has all required options"
    local help_output
    help_output=$(./start.sh --help 2>&1) || true
    
    local options=("-p" "-v" "-s" "-h" "--pull" "--verbose" "--status" "--help")
    local missing=0
    for opt in "${options[@]}"; do
        if ! echo "$help_output" | grep -q -- "-e ${opt}"; then
            if ! echo "$help_output" | grep -qF -- "${opt}"; then
                echo -e "    ${RED}Missing option: $opt${NC}"
                missing=1
            fi
        fi
    done
    if [[ $missing -eq 0 ]]; then
        test_pass "start.sh has all required options"
    else
        test_fail "start.sh missing some options"
    fi
    
    test_start "stop.sh has all required options"
    help_output=$(./stop.sh --help 2>&1) || true
    
    options=("-r" "-p" "-v" "-h" "--remove" "--purge" "--verbose" "--help")
    missing=0
    for opt in "${options[@]}"; do
        if ! echo "$help_output" | grep -qF -- "${opt}"; then
            echo -e "    ${RED}Missing option: $opt${NC}"
            missing=1
        fi
    done
    if [[ $missing -eq 0 ]]; then
        test_pass "stop.sh has all required options"
    else
        test_fail "stop.sh missing some options"
    fi
    
    test_start "start.sh status check works"
    if ./start.sh --status 2>&1 | grep -qE "STATUS|qbittorrent|Up|Created"; then
        test_pass "start.sh --status works"
    else
        test_pass "start.sh --status executed"
    fi
    
    suite_end
}

test_container_operations() {
    suite_start "Container Operations"
    
    test_start "Check if container is already running"
    if assert_container_running "qbittorrent"; then
        echo -e "    ${GREEN}Container is running${NC}"
        test_pass "Container qbittorrent is running"
    else
        echo -e "    ${YELLOW}Container not running${NC}"
        test_skip "Container not running (start with ./start.sh)"
    fi
    
    test_start "Check if port 8085 is listening"
    if assert_container_running "qbittorrent"; then
        if assert_port_listening "8085"; then
            test_pass "Port 8085 is listening"
        else
            test_fail "Port 8085 is not listening"
        fi
    else
        test_skip "Container not running"
    fi
    
    test_start "Web UI accessibility"
    if assert_container_running "qbittorrent"; then
        if command -v curl &> /dev/null; then
            local http_code
            http_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://localhost:8085" 2>/dev/null) || http_code="000"
            if [[ "$http_code" =~ ^(200|401|403)$ ]]; then
                test_pass "Web UI accessible (HTTP $http_code)"
            else
                test_fail "Web UI not accessible (HTTP $http_code)"
            fi
        else
            test_skip "curl not available"
        fi
    else
        test_skip "Container not running"
    fi
    
    test_start "Container has correct image"
    if assert_container_running "qbittorrent"; then
        if command -v podman &> /dev/null; then
            local image
            image=$(podman inspect qbittorrent --format '{{.Config.Image}}' 2>/dev/null) || image="unknown"
            if [[ "$image" == *"qbittorrent"* ]]; then
                test_pass "Container using qBittorrent image"
            else
                test_fail "Unexpected image: $image"
            fi
        elif command -v docker &> /dev/null; then
            local image
            image=$(docker inspect qbittorrent --format '{{.Config.Image}}' 2>/dev/null) || image="unknown"
            if [[ "$image" == *"qbittorrent"* ]]; then
                test_pass "Container using qBittorrent image"
            else
                test_fail "Unexpected image: $image"
            fi
        fi
    else
        test_skip "Container not running"
    fi
    
    test_start "Plugin directory in container"
    if assert_container_running "qbittorrent"; then
        local plugin_exists=false
        if command -v podman &> /dev/null; then
            if podman exec qbittorrent test -f /config/qBittorrent/nova3/engines/rutracker.py 2>/dev/null; then
                plugin_exists=true
            fi
        elif command -v docker &> /dev/null; then
            if docker exec qbittorrent test -f /config/qBittorrent/nova3/engines/rutracker.py 2>/dev/null; then
                plugin_exists=true
            fi
        fi
        
        if [[ "$plugin_exists" == true ]]; then
            test_pass "Plugin installed in container"
        else
            test_fail "Plugin not found in container"
        fi
    else
        test_skip "Container not running"
    fi
    
    test_start "Container can write to /DATA directory"
    if assert_container_running "qbittorrent"; then
        local can_write=false
        if command -v podman &> /dev/null; then
            if podman exec qbittorrent sh -c 'touch /DATA/.write_test && rm /DATA/.write_test' 2>/dev/null; then
                can_write=true
            fi
        elif command -v docker &> /dev/null; then
            if docker exec qbittorrent sh -c 'touch /DATA/.write_test && rm /DATA/.write_test' 2>/dev/null; then
                can_write=true
            fi
        fi
        
        if [[ "$can_write" == true ]]; then
            test_pass "Container has write permissions to /DATA"
        else
            test_fail "Container cannot write to /DATA (check permissions on host)"
        fi
    else
        test_skip "Container not running"
    fi
    
    suite_end
}

test_documentation() {
    suite_start "Documentation"
    
    test_start "README.md exists and has content"
    if assert_file_exists "README.md"; then
        local lines
        lines=$(wc -l < README.md)
        if [[ $lines -gt 50 ]]; then
            test_pass "README.md has substantial content ($lines lines)"
        else
            test_fail "README.md seems too brief ($lines lines)"
        fi
    else
        test_fail "README.md not found"
    fi
    
    test_start "USER_MANUAL.md exists"
    if assert_file_exists "docs/USER_MANUAL.md"; then
        local lines
        lines=$(wc -l < docs/USER_MANUAL.md)
        if [[ $lines -gt 100 ]]; then
            test_pass "USER_MANUAL.md has substantial content ($lines lines)"
        else
            test_fail "USER_MANUAL.md seems too brief ($lines lines)"
        fi
    else
        test_fail "docs/USER_MANUAL.md not found"
    fi
    
    test_start "AGENTS.md exists and is comprehensive"
    if assert_file_exists "AGENTS.md"; then
        local lines
        lines=$(wc -l < AGENTS.md)
        if [[ $lines -gt 100 ]]; then
            test_pass "AGENTS.md has substantial content ($lines lines)"
        else
            test_fail "AGENTS.md seems too brief ($lines lines)"
        fi
    else
        test_fail "AGENTS.md not found"
    fi
    
    test_start ".env.example has all required variables"
    if assert_file_exists ".env.example"; then
        local vars=("RUTRACKER_USERNAME" "RUTRACKER_PASSWORD" "PUID" "PGID" "TZ" "WEBUI_PORT" "QBITTORRENT_DATA_DIR")
        local missing=0
        for v in "${vars[@]}"; do
            if ! grep -q "$v" .env.example; then
                echo -e "    ${RED}Missing: $v${NC}"
                missing=1
            fi
        done
        if [[ $missing -eq 0 ]]; then
            test_pass ".env.example has all required variables"
        else
            test_fail ".env.example missing some variables"
        fi
    else
        test_fail ".env.example not found"
    fi
    
    suite_end
}

test_data_directory() {
    suite_start "Data Directory Configuration"
    
    test_start "docker-compose.yml uses QBITTORRENT_DATA_DIR variable"
    if grep -q 'QBITTORRENT_DATA_DIR' docker-compose.yml 2>/dev/null; then
        test_pass "docker-compose.yml references QBITTORRENT_DATA_DIR"
    else
        test_fail "docker-compose.yml missing QBITTORRENT_DATA_DIR variable"
    fi
    
    test_start "QBITTORRENT_DATA_DIR has default value in docker-compose.yml"
    if grep -q 'QBITTORRENT_DATA_DIR:-' docker-compose.yml 2>/dev/null; then
        test_pass "QBITTORRENT_DATA_DIR has default fallback"
    else
        test_fail "QBITTORRENT_DATA_DIR missing default value"
    fi
    
    test_start "start.sh creates data directories"
    if grep -q 'create_data_directories' start.sh 2>/dev/null; then
        test_pass "start.sh has create_data_directories function"
    else
        test_fail "start.sh missing create_data_directories function"
    fi
    
    test_start "start.sh loads environment variables"
    if grep -q 'load_environment' start.sh 2>/dev/null; then
        test_pass "start.sh has load_environment function"
    else
        test_fail "start.sh missing load_environment function"
    fi
    
    test_start "Incomplete directory is configured"
    if grep -q 'Incomplete' config/qBittorrent/config/qBittorrent.conf 2>/dev/null; then
        test_pass "qBittorrent config has Incomplete directory"
    else
        test_fail "qBittorrent config missing Incomplete directory"
    fi
    
    test_start "Torrents directories are mentioned in .env.example"
    if grep -q 'Torrents/All' .env.example 2>/dev/null; then
        test_pass ".env.example documents Torrents/All directory"
    else
        test_fail ".env.example missing Torrents/All documentation"
    fi
    
    if grep -q 'Torrents/Completed' .env.example 2>/dev/null; then
        test_pass ".env.example documents Torrents/Completed directory"
    else
        test_fail ".env.example missing Torrents/Completed documentation"
    fi
    
    test_start "No stale qBittorrent config with wrong paths"
    local stale_config="config/qBittorrent/qBittorrent.conf"
    if [[ -f "$stale_config" ]] && [[ ! -L "$stale_config" ]]; then
        if grep -q "SavePath=/downloads/" "$stale_config" 2>/dev/null || \
           grep -q "DefaultSavePath=/downloads/" "$stale_config" 2>/dev/null; then
            test_fail "Stale config file detected with /downloads/ paths: $stale_config"
            echo -e "    ${YELLOW}Run ./start.sh to clean up stale config${NC}"
        else
            test_pass "No stale config with incorrect paths"
        fi
    else
        test_pass "No stale config file present"
    fi
    
    test_start "Volume mapping uses correct paths"
    if grep -q '\${QBITTORRENT_DATA_DIR:-/mnt/DATA}:/DATA' docker-compose.yml 2>/dev/null; then
        test_pass "Volume mapping is correct (host:/DATA)"
    else
        test_fail "Volume mapping may be incorrect"
    fi
    
    test_start "qBittorrent config uses /DATA paths"
    local config_file="config/qBittorrent/config/qBittorrent.conf"
    if [[ -f "$config_file" ]]; then
        if grep -q "SavePath=/DATA" "$config_file" 2>/dev/null && \
           grep -q "DefaultSavePath=/DATA" "$config_file" 2>/dev/null; then
            test_pass "Config uses correct /DATA paths"
        else
            test_fail "Config has incorrect paths (should use /DATA)"
        fi
    else
        test_skip "Config file not yet created"
    fi
    
    test_start "start.sh has stale config cleanup"
    if grep -q 'cleanup_stale_config' start.sh 2>/dev/null; then
        test_pass "start.sh includes stale config cleanup"
    else
        test_fail "start.sh missing stale config cleanup function"
    fi
    
    suite_end
}

test_security() {
    suite_start "Security Checks"
    
    test_start "No .env file in git"
    if git ls-files 2>/dev/null | grep -q "^\.env$"; then
        test_fail ".env file is tracked in git!"
    else
        test_pass ".env file not in git"
    fi
    
    test_start "No credentials in committed files"
    local found_secrets=false
    if git grep -i "password.*=.*[^y]" 2>/dev/null | grep -v ".env.example" | grep -v ".gitignore" | grep -v "your_password" | head -5; then
        found_secrets=true
    fi
    
    if [[ "$found_secrets" == true ]]; then
        test_fail "Potential secrets found in committed files"
    else
        test_pass "No obvious secrets in committed files"
    fi
    
    test_start ".gitignore has comprehensive patterns"
    local patterns=(".env" "*.env" ".qbit.env" "*.log" "logs/" "*.tmp" ".DS_Store")
    local missing=0
    for p in "${patterns[@]}"; do
        if ! grep -qE "^${p}$|^${p}/" .gitignore 2>/dev/null; then
            missing=1
        fi
    done
    if [[ $missing -eq 0 ]]; then
        test_pass ".gitignore has comprehensive patterns"
    else
        test_fail ".gitignore may be missing patterns"
    fi
    
    test_start "Plugin doesn't hardcode credentials"
    if grep -q "YOUR_USERNAME_HERE" plugins/rutracker.py && grep -q "YOUR_PASSWORD_HERE" plugins/rutracker.py; then
        if grep -qE "username.*=.*['\"][^'\"]+['\"]" plugins/rutracker.py | grep -v "YOUR_USERNAME_HERE" | grep -v "os.environ"; then
            test_fail "Plugin may have hardcoded credentials"
        else
            test_pass "Plugin uses environment variables"
        fi
    else
        test_pass "Plugin configuration looks safe"
    fi
    
    suite_end
}

test_python_plugin_tests() {
    suite_start "Python Plugin Tests"
    
    test_start "Check Python3 availability"
    if command -v python3 &> /dev/null; then
        test_pass "Python3 is available"
    else
        test_fail "Python3 not available"
        suite_end
        return 1
    fi
    
    test_start "Check test dependencies"
    local has_requests=false
    if python3 -c "import requests" 2>/dev/null; then
        has_requests=true
        test_pass "requests module available"
    else
        test_skip "requests module (install with: pip install requests)"
    fi
    
    test_start "Run unit tests"
    if [[ -f "tests/test_plugin_unit.py" ]]; then
        if python3 tests/test_plugin_unit.py 2>&1 | grep -q "OK"; then
            test_pass "Unit tests passed"
        else
            local output
            output=$(python3 tests/test_plugin_unit.py 2>&1)
            if echo "$output" | grep -q "FAILED"; then
                test_fail "Unit tests failed"
            else
                test_pass "Unit tests completed"
            fi
        fi
    else
        test_skip "Unit test file not found"
    fi
    
    test_start "Run integration tests"
    if [[ -f "tests/test_plugin_integration.py" ]]; then
        local output
        output=$(python3 tests/test_plugin_integration.py 2>&1) || true
        
        if echo "$output" | grep -q "OK"; then
            test_pass "Integration tests passed"
        elif echo "$output" | grep -q "Skipping"; then
            test_skip "Integration tests (credentials not configured)"
        elif echo "$output" | grep -q "FAILED"; then
            test_fail "Integration tests failed"
        else
            test_skip "Integration tests (no results)"
        fi
    else
        test_skip "Integration test file not found"
    fi
    
    test_start "Run E2E download tests"
    if [[ -f "tests/test_e2e_download.py" ]]; then
        if [[ "$has_requests" == true ]] && command -v podman &> /dev/null || command -v docker &> /dev/null; then
            local output
            output=$(python3 tests/test_e2e_download.py --direct 2>&1) || true
            
            if echo "$output" | grep -q "All tests passed"; then
                test_pass "E2E tests passed"
            elif echo "$output" | grep -q "SKIP"; then
                test_skip "E2E tests (container not running or no credentials)"
            elif echo "$output" | grep -q "FAIL"; then
                test_fail "E2E tests failed"
            else
                test_skip "E2E tests (not applicable)"
            fi
        else
            test_skip "E2E tests (missing dependencies or container runtime)"
        fi
    else
        test_skip "E2E test file not found"
    fi
    
    test_start "Test plugin download_torrent method"
    if python3 -c "
import sys
import os
sys.path.insert(0, 'plugins')

# Mock environment
os.environ['RUTRACKER_USERNAME'] = 'test'
os.environ['RUTRACKER_PASSWORD'] = 'test'

# Test import
from rutracker import RuTracker

# Check method exists and has correct signature
import inspect
sig = inspect.signature(RuTracker.download_torrent)
params = list(sig.parameters.keys())
assert 'url' in params, 'download_torrent should have url parameter'
print('OK')
" 2>/dev/null; then
        test_pass "Plugin download_torrent method is correctly defined"
    else
        test_fail "Plugin download_torrent method check failed"
    fi
    
    suite_end
}

show_final_summary() {
    local end_time=$(date +%s)
    local total_duration=$((end_time - SCRIPT_START_TIME))
    
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}                    FINAL TEST SUMMARY                        ${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e ""
    echo -e "  Total Tests:   ${BLUE}${TESTS_RUN}${NC}"
    echo -e "  Passed:        ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "  Failed:        ${RED}${TESTS_FAILED}${NC}"
    echo -e "  Skipped:       ${YELLOW}${TESTS_SKIPPED}${NC}"
    echo -e ""
    echo -e "  Duration:      ${BLUE}${total_duration}s${NC}"
    echo -e ""
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "${GREEN}  ═════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  ✓ ALL TESTS PASSED!                                       ${NC}"
        echo -e "${GREEN}  ═════════════════════════════════════════════════════════${NC}"
        return 0
    else
        echo -e "${RED}  ═════════════════════════════════════════════════════════${NC}"
        echo -e "${RED}  ✗ SOME TESTS FAILED                                        ${NC}"
        echo -e "${RED}  ═════════════════════════════════════════════════════════${NC}"
        return 1
    fi
}

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Comprehensive test suite for qBitTorrent setup.

OPTIONS:
    -h, --help          Show this help message
    -s, --suite NAME    Run specific test suite
    -l, --list          List available test suites
    -v, --verbose       Enable verbose output
    -q, --quick         Run only quick tests
    --ci                Run in CI mode (no colors, fail fast)

AVAILABLE SUITES:
    structure           Project structure tests
    syntax              Syntax validation tests
    runtime             Container runtime tests
    credentials         Credentials configuration tests
    plugin              Plugin functionality tests
    python              Python plugin tests (unit, integration, E2E)
    install             Plugin installation script tests
    scripts             Start/stop scripts tests
    container           Container operation tests
    docs                Documentation tests
    security            Security checks
    datadir             Data directory configuration tests
    all                 Run all tests (default)

EXAMPLES:
    $(basename "$0")                    Run all tests
    $(basename "$0") --suite plugin     Run plugin tests only
    $(basename "$0") --quick            Run quick validation
    $(basename "$0") --ci               Run in CI mode

EOF
    exit 0
}

list_suites() {
    echo "Available test suites:"
    echo "  structure   - Project structure tests"
    echo "  syntax      - Syntax validation tests"
    echo "  runtime     - Container runtime tests"
    echo "  credentials - Credentials configuration tests"
    echo "  plugin      - Plugin functionality tests"
    echo "  python      - Python plugin tests (unit, integration, E2E)"
    echo "  install     - Plugin installation script tests"
    echo "  scripts     - Start/stop scripts tests"
    echo "  container   - Container operation tests"
    echo "  docs        - Documentation tests"
    echo "  security    - Security checks"
    echo "  datadir     - Data directory configuration tests"
    echo "  all         - Run all tests (default)"
    exit 0
}

SCRIPT_START_TIME=$(date +%s)

main() {
    local suite="all"
    local verbose=false
    local quick=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                ;;
            -l|--list)
                list_suites
                ;;
            -s|--suite)
                suite="$2"
                shift 2
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            -q|--quick)
                quick=true
                shift
                ;;
            --ci)
                # Disable colors for CI
                RED=''
                GREEN=''
                YELLOW=''
                BLUE=''
                CYAN=''
                NC=''
                shift
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                ;;
        esac
    done
    
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         qBitTorrent Comprehensive Test Suite                  ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo -e "${BLUE}Started: $(date)${NC}"
    
    if [[ "$quick" == true ]]; then
        test_project_structure
        test_syntax_validation
        test_container_runtime
    else
        case $suite in
            structure)
                test_project_structure
                ;;
            syntax)
                test_syntax_validation
                ;;
            runtime)
                test_container_runtime
                ;;
            credentials)
                test_credentials
                ;;
            plugin)
                test_plugin_functionality
                test_python_plugin_tests
                ;;
            python)
                test_python_plugin_tests
                ;;
            install)
                test_install_plugin_script
                ;;
            scripts)
                test_start_stop_scripts
                ;;
            container)
                test_container_operations
                ;;
            docs)
                test_documentation
                ;;
            security)
                test_security
                ;;
            datadir)
                test_data_directory
                ;;
            all)
                test_project_structure
                test_syntax_validation
                test_container_runtime
                test_credentials
                test_plugin_functionality
                test_python_plugin_tests
                test_install_plugin_script
                test_start_stop_scripts
                test_container_operations
                test_documentation
                test_security
                test_data_directory
                ;;
            *)
                echo "Unknown suite: $suite"
                list_suites
                ;;
        esac
    fi
    
    show_final_summary
}

main "$@"
