#!/usr/bin/env bash

set -euo pipefail

SERVICE_NAME="elgato-virtualcam.service"
INSTALL_DIR="$HOME/.config/systemd/user"
TARGET_SERVICE="$INSTALL_DIR/$SERVICE_NAME"
TARGET_SCRIPT="$HOME/.local/bin/elgato-virtualcam.sh"

echo "🛑 Stopping systemd user service..."
if systemctl --user is-enabled --quiet "$SERVICE_NAME"; then
  systemctl --user disable --now "$SERVICE_NAME"
else
  echo "⚠️  Service is not enabled or running."
fi

echo "🧹 Cleaning up installed files..."

if [[ -f "$TARGET_SERVICE" ]]; then
  echo "   Removing systemd service: $TARGET_SERVICE"
  rm -f "$TARGET_SERVICE"
fi

if [[ -f "$TARGET_SCRIPT" ]]; then
  read -rp "❓ Delete script $TARGET_SCRIPT? [y/N]: " CONFIRM
  if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "   Deleting $TARGET_SCRIPT"
    rm -f "$TARGET_SCRIPT"
  else
    echo "   Skipping script deletion."
  fi
fi

echo "🔄 Reloading systemd user manager..."
systemctl --user daemon-reload

# Clean up tray controller
echo "🖱️  Cleaning up tray controller..."

# Stop running tray controller
pkill -f "virtualcam-tray.py" || true

# Remove autostart entry
AUTOSTART_FILE="$HOME/.config/autostart/elgato-virtualcam-tray.desktop"
if [[ -f "$AUTOSTART_FILE" ]]; then
  echo "   Removing autostart entry: $AUTOSTART_FILE"
  rm -f "$AUTOSTART_FILE"
fi

echo "🧯 Unloading v4l2loopback (optional)..."
if lsmod | grep -q v4l2loopback; then
  sudo modprobe -r v4l2loopback && echo "   Module unloaded."
else
  echo "   v4l2loopback not currently loaded."
fi

echo "ℹ️  Note: PyQt5 package left installed (may be used by other applications)"
echo "✅ Uninstall complete."
