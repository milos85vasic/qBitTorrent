#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="qbit-webui-bridge"
SERVICE_FILE="${SCRIPT_DIR}/webui-bridge.service"
TARGET_DIR="${HOME}/.config/systemd/user"

mkdir -p "${TARGET_DIR}"

sed "s|%h/qBitTorrent|${SCRIPT_DIR}|g" "${SERVICE_FILE}" > "${TARGET_DIR}/${SERVICE_NAME}.service"

systemctl --user daemon-reload
systemctl --user enable "${SERVICE_NAME}.service"
systemctl --user start "${SERVICE_NAME}.service"

echo "WebUI Bridge systemd service installed and started."
echo "Status: $(systemctl --user is-active "${SERVICE_NAME}.service")"
echo ""
echo "Manage with:"
echo "  systemctl --user status ${SERVICE_NAME}"
echo "  systemctl --user stop ${SERVICE_NAME}"
echo "  systemctl --user restart ${SERVICE_NAME}"
echo "  journalctl --user -u ${SERVICE_NAME} -f"
