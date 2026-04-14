#!/bin/bash
set -euo pipefail

echo "==================================="
echo "qBittorrent Full Integration Test"
echo "==================================="
echo ""

# Test containers
echo "1. Checking containers..."
podman ps | grep -q qbittorrent && echo "   ✓ qBittorrent running"
podman ps | grep -q qbittorrent-proxy && echo "   ✓ Download proxy running"

# Test login page
echo ""
echo "2. Testing login page..."
curl -s --max-time 5 "http://localhost:7186/" | grep -q "qBittorrent" && echo "   ✓ Login page loads"

# Test login
echo ""
echo "3. Testing login..."
rm -f /tmp/test_cookie.txt
if curl -s --max-time 5 -c /tmp/test_cookie.txt -X POST "http://localhost:7186/api/v2/auth/login" \
    -d "username=admin" -d "password=admin" | grep -q "Ok"; then
    echo "   ✓ Login successful"
else
    echo "   ✗ Login failed"
    exit 1
fi

# Test search
echo ""
echo "4. Testing RuTracker search..."
SEARCH_ID=$(curl -s --max-time 5 -b /tmp/test_cookie.txt -X POST "http://localhost:7186/api/v2/search/start" \
    -d "pattern=test" -d "plugins=rutracker" -d "category=all" | grep -o '"id":[0-9]*' | grep -o '[0-9]*')
if [ -n "$SEARCH_ID" ]; then
    echo "   ✓ Search started (ID: $SEARCH_ID)"
    sleep 3
    
    # Get results
    RESULTS=$(curl -s --max-time 5 -b /tmp/test_cookie.txt "http://localhost:7186/api/v2/search/results?id=$SEARCH_ID&limit=1")
    if echo "$RESULTS" | grep -q '"fileName"'; then
        echo "   ✓ Search returned results"
        
        # Test download
        echo ""
        echo "5. Testing RuTracker download..."
        URL=$(echo "$RESULTS" | grep -o '"fileUrl":"[^"]*"' | head -1 | sed 's/.*":"//' | sed 's/"$//')
        if curl -s --max-time 10 -b /tmp/test_cookie.txt -X POST "http://localhost:7186/api/v2/torrents/add" \
            -d "urls=$URL" | grep -q "Ok"; then
            echo "   ✓ Download successful"
            
            sleep 2
            # Verify
            if curl -s --max-time 5 -b /tmp/test_cookie.txt "http://localhost:7186/api/v2/torrents/info" | grep -q '"name":'; then
                echo "   ✓ Torrent added to list"
            else
                echo "   ✗ Torrent not in list"
            fi
        else
            echo "   ✗ Download failed"
        fi
    else
        echo "   ✗ No search results"
    fi
else
    echo "   ✗ Search failed"
fi

echo ""
echo "==================================="
echo "Test complete!"
echo "==================================="
