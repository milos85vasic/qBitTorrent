#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
BIN_DIR="$ROOT_DIR/bin"
mkdir -p "$BIN_DIR"

echo "Building qbittorrent-proxy..."
cd "$ROOT_DIR" && go build -o "$BIN_DIR/qbittorrent-proxy" ./cmd/qbittorrent-proxy

echo "Building webui-bridge..."
cd "$ROOT_DIR" && go build -o "$BIN_DIR/webui-bridge" ./cmd/webui-bridge

echo "Building boba-jackett..."
cd "$ROOT_DIR" && go build -o "$BIN_DIR/boba-jackett" ./cmd/boba-jackett

echo "Build complete: $BIN_DIR/"
ls -la "$BIN_DIR/"