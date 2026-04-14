#!/bin/bash
# Run All Tests - Automation Script
# Executes all test suites and generates report

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_header() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════════════════╗"
    echo "║ $1"
    echo "╚════════════════════════════════════════════════════════════════════════════╝"
    echo ""
}

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }

detect_container_runtime() {
    if command -v podman &> /dev/null; then
        echo "podman"
    elif command -v docker &> /dev/null; then
        echo "docker"
    else
        echo ""
    fi
}

RUNTIME=$(detect_container_runtime)

if [[ -z "$RUNTIME" ]]; then
    print_error "Neither podman nor docker found"
    exit 1
fi

print_info "Using container runtime: $RUNTIME"

# Initialize results
OVERALL_STATUS=0
TEST_RESULTS=""

# Function to run test and capture result
run_test() {
    local test_name="$1"
    local test_cmd="$2"
    
    print_info "Running: $test_name"
    
    if eval "$test_cmd" > /tmp/test_output.txt 2>&1; then
        print_success "$test_name - PASSED"
        TEST_RESULTS="${TEST_RESULTS}✓ $test_name - PASSED\n"
        return 0
    else
        print_error "$test_name - FAILED"
        TEST_RESULTS="${TEST_RESULTS}✗ $test_name - FAILED\n"
        cat /tmp/test_output.txt
        OVERALL_STATUS=1
        return 1
    fi
}

print_header "RUNNING ALL TESTS - COMPREHENSIVE VALIDATION"

# Check prerequisites
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1/7: Checking Prerequisites"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if ! $RUNTIME ps --format '{{.Names}}' 2>/dev/null | grep -q "qbittorrent"; then
    print_error "qBittorrent container not running!"
    print_info "Starting container..."
    ./start.sh
    sleep 5
fi

print_success "Container is running"

# Test Suite 1: Comprehensive Plugin Test
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2/7: Comprehensive Plugin Test (12 plugins)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

run_test "Plugin Structure, Search, Download, Columns" \
    "python3 tests/comprehensive_test.py"

# Test Suite 2: Unit Tests
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3/7: Unit Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

run_test "Plugin Unit Tests" \
    "python3 tests/test_all_plugins.py"

# Test Suite 3: Integration Tests
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 4/7: Integration Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

run_test "Plugin Integration" \
    "python3 tests/test_plugin_integration.py"

# Test Suite 4: Merge Service Unit Tests
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 5/7: Merge Service Unit Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

run_test "Merge Service Unit Tests" \
    "python3 -m pytest tests/unit/merge_service/ -v --import-mode=importlib"

# Test Suite 5: Merge Service Integration
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 6/7: Merge Service Integration Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

run_test "Merge Service Integration Tests" \
    "python3 -m pytest tests/integration/test_merge_api.py -v --import-mode=importlib"

# Test Suite 6: Live Container Tests
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 7/7: Live Container Tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

run_test "Live Container Health Tests" \
    "python3 -m pytest tests/integration/test_live_containers.py -v --import-mode=importlib"

# Generate Report
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 TEST REPORT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create detailed report
REPORT_FILE="test_report_$(date +%Y%m%d_%H%M%S).txt"

{
    echo "════════════════════════════════════════════════════════════════════════════"
    echo "                    QBITTORRENT-FIXED TEST REPORT"
    echo "                    Generated: $(date)"
    echo "════════════════════════════════════════════════════════════════════════════"
    echo ""
    echo "CONTAINER STATUS:"
    echo "  Runtime: $RUNTIME"
    echo "  Container: $($RUNTIME ps --filter name=qbittorrent --format '{{.Names}}' 2>/dev/null || echo 'Not running')"
    echo "  Status: $($RUNTIME ps --filter name=qbittorrent --format '{{.Status}}' 2>/dev/null || echo 'Unknown')"
    echo "  WebUI: http://localhost:8085"
    echo ""
    echo "TEST RESULTS:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "$TEST_RESULTS"
    echo ""
    echo "OVERALL STATUS: $(if [ $OVERALL_STATUS -eq 0 ]; then echo '✅ ALL TESTS PASSED (100%)'; else echo '⚠️  SOME TESTS FAILED'; fi)"
    echo ""
    echo "════════════════════════════════════════════════════════════════════════════"
} > "$REPORT_FILE"

# Print summary
echo -e "$TEST_RESULTS"

if [ $OVERALL_STATUS -eq 0 ]; then
    echo ""
    print_success "🎉 ALL TESTS PASSED - 100% SUCCESS RATE!"
    echo ""
    print_info "Report saved to: $REPORT_FILE"
    echo ""
    echo "════════════════════════════════════════════════════════════════════════════"
    echo "                        ✅ READY FOR PRODUCTION"
    echo "════════════════════════════════════════════════════════════════════════════"
    exit 0
else
    echo ""
    print_error "❌ SOME TESTS FAILED"
    echo ""
    print_info "Report saved to: $REPORT_FILE"
    echo ""
    echo "════════════════════════════════════════════════════════════════════════════"
    echo "                        ⚠️  ISSUES NEED ATTENTION"
    echo "════════════════════════════════════════════════════════════════════════════"
    exit 1
fi
