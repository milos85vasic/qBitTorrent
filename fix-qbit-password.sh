#!/bin/bash

set -euo pipefail

QBIT_URL="${QBITTORRENT_URL:-http://localhost:7185}"

wait_for_qbit() {
    local max_wait=60
    local waited=0
    while [[ $waited -lt $max_wait ]]; do
        if curl -sf "$QBIT_URL/" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    return 1
}

set_password() {
    echo "[INFO] Waiting for qBittorrent..."
    wait_for_qbit || { echo "[ERROR] qBittorrent not responding"; return 1; }

    echo "[INFO] Getting temp password from qBittorrent logs..."
    local temp_pass
    temp_pass=$(podman logs qbittorrent 2>&1 | grep -oP 'temporary password is provided for this session: \K\w+' | tail -1)

    if [[ -z "$temp_pass" ]]; then
        echo "[ERROR] Could not find temporary password"
        return 1
    fi

    echo "[INFO] Found temp password, logging in..."
    local session_cookies
    session_cookies=$(mktemp)

    curl -s -c "$session_cookies" -b "$session_cookies" -X POST "$QBIT_URL/api/v2/auth/login" \
        -d "username=admin" -d "password=$temp_pass" || {
        echo "[ERROR] Login failed"; rm -f "$session_cookies"; return 1; }

    echo "[INFO] Setting permanent password 'admin'..."
    curl -s -b "$session_cookies" -X POST "$QBIT_URL/api/v2/app/setPreferences" \
        -d 'json={"web_ui_password":"admin"}' || {
        echo "[WARN] Setting password may have failed"; }

    rm -f "$session_cookies"

    echo "[INFO] Verifying login with 'admin'..."
    local verify
    verify=$(curl -s -X POST "$QBIT_URL/api/v2/auth/login" \
        -d "username=admin" -d "password=admin")

    if [[ "$verify" == "Ok." ]]; then
        echo "[SUCCESS] Password set to 'admin'"
        return 0
    else
        echo "[ERROR] Verification failed: $verify"
        return 1
    fi
}

set_password