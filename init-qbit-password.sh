#!/bin/bash
set -euo pipefail

echo "[init] Waiting for qBittorrent to be ready..."
max_wait=120
waited=0
while [[ $waited -lt $max_wait ]]; do
    if curl -sf http://localhost:7185/ >/dev/null 2>&1; then
        echo "[init] qBittorrent is ready"
        break
    fi
    sleep 2
    waited=$((waited + 2))
done

echo "[init] Checking for existing password or setting up..."

# Get current temp password from logs (if any)
temp_pass=$(podman logs qbittorrent 2>&1 | grep -oP 'temporary password is provided for this session: \K\w+' | tail -1 || true)

if [[ -z "$temp_pass" ]]; then
    echo "[init] No temp password found - checking if password is already set..."
    # Try to login with default - if it works, we're done
    result=$(curl -s -X POST http://localhost:7185/api/v2/auth/login \
        -d "username=admin" -d "password=admin")
    if [[ "$result" == "Ok." ]]; then
        echo "[init] Password already set to 'admin'"
        exit 0
    fi
    echo "[init] Login failed, trying other methods..."
    # Try empty password (for fresh setup)
    result=$(curl -s -X POST http://localhost:7185/api/v2/auth/login \
        -d "username=admin" -d "password=")
    if [[ "$result" == "Ok." ]]; then
        echo "[init] Got empty temp password, setting to 'admin'..."
        # Set password via API - need to use proper JSON format
        curl -s -X POST http://localhost:7185/api/v2/app/setPreferences \
            -H "Content-Type: application/json" \
            -d '{"json":"{\"web_ui_password\":\"admin\"}"}'
        
        result=$(curl -s -X POST http://localhost:7185/api/v2/auth/login \
            -d "username=admin" -d "password=admin")
        if [[ "$result" == "Ok." ]]; then
            echo "[init] SUCCESS - Password set to 'admin'"
        else
            echo "[init] Warning: Could not verify password was set"
        fi
    fi
else
    echo "[init] Found temp password: $temp_pass"
    # Login with temp password
    result=$(curl -s -X POST http://localhost:7185/api/v2/auth/login \
        -d "username=admin" -d "password=$temp_pass")
    
    if [[ "$result" == "Ok." ]]; then
        echo "[init] Logged in with temp, setting password to 'admin'..."
        
        # Try setting password using proper API call (multiple formats)
        curl -s -X POST http://localhost:7185/api/v2/app/setPreferences \
            -d "json={\"web_ui_password\":\"admin\"}" || true
        curl -s -X POST http://localhost:7185/api/v2/app/setPreferences \
            --data-urlencode "json={\"web_ui_password\":\"admin\"}" || true
        
        # Logout and test
        curl -s -X POST http://localhost:7185/api/v2/auth/logout || true
        
        result=$(curl -s -X POST http://localhost:7185/api/v2/auth/login \
            -d "username=admin" -d "password=admin")
        
        if [[ "$result" == "Ok." ]]; then
            echo "[init] SUCCESS - Password set to 'admin'"
        else
            echo "[init] WARNING: Password setting may have failed"
        fi
    else
        echo "[init] Could not login with temp password"
    fi
fi

echo "[init] Done"