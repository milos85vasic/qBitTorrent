#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BASE_URL="http://localhost:8085"
COOKIE_FILE="/tmp/qb_test_cookies.txt"
FAILED=0

print_success() { echo -e "${GREEN}[PASS]${NC} $1"; }
print_error() { echo -e "${RED}[FAIL]${NC} $1"; FAILED=1; }
print_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

cleanup() {
    rm -f "$COOKIE_FILE"
}
trap cleanup EXIT

print_info "Starting qBittorrent Automated Tests..."
print_info "=========================================="

# Test 1: Check containers are running
print_info "Test 1: Checking containers..."
if podman ps | grep -q "qbittorrent-proxy" && podman ps | grep -q "qbittorrent"; then
    print_success "Both containers are running"
else
    print_error "Containers not running"
    exit 1
fi

# Test 2: Check login page loads
print_info "Test 2: Checking login page..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/" || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    print_success "Login page accessible (HTTP 200)"
else
    print_error "Login page returned HTTP $HTTP_CODE"
fi

# Test 3: Check CSS loads properly
print_info "Test 3: Checking CSS files..."
CSS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/css/login.css" || echo "000")
if [ "$CSS_CODE" = "200" ]; then
    print_success "CSS files loading (HTTP 200)"
else
    print_error "CSS files returned HTTP $CSS_CODE"
fi

# Test 4: Login
print_info "Test 4: Testing login..."
LOGIN_RESULT=$(curl -s -c "$COOKIE_FILE" -X POST "$BASE_URL/api/v2/auth/login" \
    -d "username=admin" \
    -d "password=admin")
if [ "$LOGIN_RESULT" = "Ok." ]; then
    print_success "Login successful"
else
    print_error "Login failed: $LOGIN_RESULT"
fi

# Test 5: Check API access
print_info "Test 5: Checking API access..."
API_TEST=$(curl -s -b "$COOKIE_FILE" "$BASE_URL/api/v2/app/version" || echo "")
if [ -n "$API_TEST" ]; then
    print_success "API accessible (version: $API_TEST)"
else
    print_error "API not accessible"
fi

# Test 6: Check search plugins
print_info "Test 6: Checking search plugins..."
PLUGINS=$(curl -s -b "$COOKIE_FILE" "$BASE_URL/api/v2/search/plugins" | grep -o '"name":"rutracker"' || echo "")
if [ -n "$PLUGINS" ]; then
    print_success "RuTracker plugin available"
else
    print_error "RuTracker plugin not found"
fi

# Test 7: Test search functionality
print_info "Test 7: Testing search..."
SEARCH_RESULT=$(curl -s -b "$COOKIE_FILE" -X POST "$BASE_URL/api/v2/search/start" \
    -d "pattern=test" \
    -d "plugins=rutracker" \
    -d "category=all" | grep -o '"id":[0-9]*' | head -1)
if [ -n "$SEARCH_RESULT" ]; then
    SEARCH_ID=$(echo "$SEARCH_RESULT" | grep -o '[0-9]*')
    print_success "Search started (ID: $SEARCH_ID)"
    
    # Wait for results
    sleep 3
    
    # Test 8: Get search results
    print_info "Test 8: Checking search results..."
    RESULTS=$(curl -s -b "$COOKIE_FILE" "$BASE_URL/api/v2/search/results?id=$SEARCH_ID&limit=1")
    if echo "$RESULTS" | grep -q '"results":\['; then
        COUNT=$(echo "$RESULTS" | grep -o '"fileName"' | wc -l)
        print_success "Search returned $COUNT results"
        
        # Test 9: Test download
        print_info "Test 9: Testing RuTracker download..."
        URL=$(echo "$RESULTS" | grep -o '"fileUrl":"[^"]*"' | head -1 | sed 's/"fileUrl":"//' | sed 's/"$//')
        if [ -n "$URL" ]; then
            DOWNLOAD_RESULT=$(curl -s -b "$COOKIE_FILE" -X POST "$BASE_URL/api/v2/torrents/add" \
                -d "urls=$URL")
            if [ "$DOWNLOAD_RESULT" = "Ok." ]; then
                print_success "Download request successful"
                
                # Test 10: Verify torrent was added
                sleep 2
                print_info "Test 10: Verifying torrent added..."
                TORRENTS=$(curl -s -b "$COOKIE_FILE" "$BASE_URL/api/v2/torrents/info")
                if echo "$TORRENTS" | grep -q '"name":'; then
                    print_success "Torrent successfully added to list"
                else
                    print_error "Torrent not found in list"
                fi
            else
                print_error "Download request failed: $DOWNLOAD_RESULT"
            fi
        else
            print_error "No download URL found in results"
        fi
    else
        print_error "No search results"
    fi
else
    print_error "Search failed to start"
fi

# Summary
print_info "=========================================="
if [ $FAILED -eq 0 ]; then
    print_success "All tests passed!"
    exit 0
else
    print_error "Some tests failed!"
    exit 1
fi
