#!/bin/bash
# install-host-power-guard.sh
#
# MANUAL PREREQUISITE — run ONCE per host, with sudo, BEFORE running
# any project test / challenge / build that boots containers or
# spawns long-running CLI agents.
#
# Background (CONST-033 / CONST-034): on 2026-04-26 18:23:43 the host
# suspended mid-session, killing HelixAgent + 41 services + the user's
# SSH session. On 2026-04-28 18:37:55 the host POWERED OFF mid-session,
# again killing all work. journalctl showed:
#   systemd-logind[1183]: The system will power off now!
# Root cause: the GDM greeter session at the local console has its own
# power policy; SSH sessions don't count as activity. Suspend masking
# alone is insufficient — poweroff must also be blocked.
#
# This script applies defence in depth so neither the greeter, nor any
# DE, nor any user with logind privileges, can suspend OR power off the
# host while it's running mission-critical workloads.
#
# Verification (re-run the challenge after this script):
#   bash challenges/scripts/host_no_auto_poweroff_challenge.sh
# All assertions must PASS.

set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR: must be run as root (sudo)." >&2
    exit 1
fi

echo "[1/4] Masking sleep / suspend / hibernate / hybrid-sleep targets..."
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

echo "[2/4] Setting AllowSuspend=no in /etc/systemd/sleep.conf.d/..."
mkdir -p /etc/systemd/sleep.conf.d
cat > /etc/systemd/sleep.conf.d/00-no-suspend.conf <<'EOF'
# CONST-033: host runs mission-critical parallel CLI-agent + container
# workloads; auto-suspend is unsafe. Defence in depth — see also the
# masked targets above and the logind drop-in below.
[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowSuspendThenHibernate=no
AllowHybridSleep=no
EOF

echo "[3/4] Setting logind IdleAction=ignore + HandleLidSwitch=ignore + HandlePowerKey=ignore..."
mkdir -p /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/00-no-idle-suspend.conf <<'EOF'
# CONST-033 / CONST-034: do not suspend or power off the host on idle,
# lid close, or power-button press. SSH sessions don't count as activity;
# the GDM greeter's idle policy was the historical trigger. The power-off
# on 2026-04-28 was caused by systemd-logind initiating poweroff while
# long-running agent work was in progress.
[Login]
IdleAction=ignore
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
HandlePowerKey=ignore
HandlePowerKeyLongPress=poweroff
EOF

echo "[4/4] Disabling GNOME power-button-action for current and future sessions..."
# Current user (if running inside a GNOME session)
if command -v gsettings &>/dev/null && [[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
    gsettings set org.gnome.settings-daemon.plugins.power power-button-action 'nothing' 2>/dev/null || true
fi
# GDM greeter — create a dconf lockdown so the greeter never powers off
mkdir -p /etc/dconf/db/local.d
cat > /etc/dconf/db/local.d/00-no-gdm-poweroff <<'EOF'
[org/gnome/settings-daemon/plugins/power]
power-button-action='nothing'
sleep-inactive-ac-type='nothing'
sleep-inactive-battery-type='nothing'
EOF
dconf update 2>/dev/null || true

echo "Reloading systemd..."
systemctl daemon-reload
systemctl reload-or-restart systemd-logind || true

echo
echo "DONE. Verify with:"
echo "  bash challenges/scripts/host_no_auto_poweroff_challenge.sh"
echo "All assertions must PASS."
echo
echo "NOTE: HandlePowerKey=ignore means the physical power button is ignored."
echo "To force-shutdown in an emergency, hold the power button for 5+ seconds."
