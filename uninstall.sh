#!/usr/bin/env bash

set -euo pipefail

# Check if running as root/sudo and warn user
if [[ $EUID -eq 0 ]]; then
    echo "⚠️  Warning: This script is running as root/sudo."
    echo "   The uninstall script should typically be run as a regular user."
    echo "   However, we'll attempt to proceed with the current user's home directory."
    echo ""
    
    # If running as root, try to determine the original user
    if [[ -n "${SUDO_USER:-}" ]]; then
        REAL_USER="$SUDO_USER"
        REAL_HOME=$(eval echo "~$REAL_USER")
        echo "   Detected original user: $REAL_USER"
        echo "   Using home directory: $REAL_HOME"
    else
        echo "❌ Cannot determine original user. Please run without sudo:"
        echo "   ./uninstall.sh"
        exit 1
    fi
else
    REAL_USER="$USER"
    REAL_HOME="$HOME"
fi

SERVICE_NAME="elgato-virtualcam.service"
INSTALL_DIR="$REAL_HOME/.config/systemd/user"
TARGET_SERVICE="$INSTALL_DIR/$SERVICE_NAME"
TARGET_SCRIPT="$REAL_HOME/.local/bin/elgato-virtualcam.sh"

echo "🛑 Stopping systemd user service..."

# Check if systemd user session is available
if ! systemctl --user --quiet is-system-running 2>/dev/null; then
    echo "⚠️  Systemd user session not available. Skipping service management."
    echo "   This is normal if running with sudo or in certain environments."
    SERVICE_AVAILABLE=false
else
    SERVICE_AVAILABLE=true
fi

if [[ "$SERVICE_AVAILABLE" == "true" ]]; then
    if systemctl --user is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        systemctl --user disable --now "$SERVICE_NAME"
        echo "   Service stopped and disabled."
    else
        echo "⚠️  Service is not enabled or running."
    fi
fi

echo "🧹 Cleaning up installed files..."

if [[ -f "$TARGET_SERVICE" ]]; then
    echo "   Removing systemd service: $TARGET_SERVICE"
    rm -f "$TARGET_SERVICE"
else
    echo "   Systemd service file not found."
fi

if [[ -f "$TARGET_SCRIPT" ]]; then
    read -rp "❓ Delete script $TARGET_SCRIPT? [y/N]: " CONFIRM
    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
        echo "   Deleting $TARGET_SCRIPT"
        rm -f "$TARGET_SCRIPT"
    else
        echo "   Skipping script deletion."
    fi
else
    echo "   Script file not found."
fi

if [[ "$SERVICE_AVAILABLE" == "true" ]]; then
    echo "🔄 Reloading systemd user manager..."
    systemctl --user daemon-reload
else
    echo "🔄 Skipping systemd reload (session not available)."
fi

# Clean up tray controller
echo "🖱️  Cleaning up tray controller..."

# Stop running tray controller
pkill -f "virtualcam-tray.py" || true

# Remove autostart entry
AUTOSTART_FILE="$REAL_HOME/.config/autostart/elgato-virtualcam-tray.desktop"
if [[ -f "$AUTOSTART_FILE" ]]; then
    echo "   Removing autostart entry: $AUTOSTART_FILE"
    rm -f "$AUTOSTART_FILE"
else
    echo "   Autostart file not found."
fi

echo "🧯 Unloading v4l2loopback (optional)..."
if lsmod | grep -q v4l2loopback; then
    sudo modprobe -r v4l2loopback && echo "   Module unloaded."
else
    echo "   v4l2loopback not currently loaded."
fi

echo "ℹ️  Note: PyQt5 package left installed (may be used by other applications)"
echo "✅ Uninstall complete."
