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

cookie_jar="/tmp/qbit_init_cookies.txt"
    target_pass="admin"

    if [[ -z "$temp_pass" ]]; then
        echo "[init] No temp password found - trying empty password..."
        result=$(curl -s -X POST http://localhost:7185/api/v2/auth/login \
            -d "username=admin" -d "password=")
        if [[ "$result" == "Ok." ]]; then
            temp_pass=""
        else
            echo "[init] Could not determine temp password"
            exit 1
        fi
    else
        echo "[init] Found temp password: $temp_pass"
    fi

    # Login and save session cookie
    result=$(curl -s -X POST http://localhost:7185/api/v2/auth/login \
        -d "username=admin" -d "password=$temp_pass" \
        -c "$cookie_jar")
    
    if [[ "$result" != "Ok." ]]; then
        echo "[init] Login failed: $result"
        exit 1
    fi
    
    echo "[init] Logged in, setting password to '$target_pass'..."
    
    # Set the password using form-urlencoded with cookie session
    curl -s -X POST http://localhost:7185/api/v2/app/setPreferences \
        -b "$cookie_jar" \
        --data-urlencode "json={\"web_ui_password\":\"$target_pass\"}" \
        -w "\nHTTP: %{http_code}\n"
    
    # Verify it worked
    curl -s -X POST http://localhost:7185/api/v2/auth/logout || true
    rm -f "$cookie_jar"
    
    result=$(curl -s -X POST http://localhost:7185/api/v2/auth/login \
        -d "username=admin" -d "password=$target_pass")
    
    if [[ "$result" == "Ok." ]]; then
        echo "[init] SUCCESS - Password set to '$target_pass'"
    else
        echo "[init] WARNING: Password set may have failed"
        exit 1
    fi

echo "[init] Done"