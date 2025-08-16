#!/bin/bash
set -e

echo "🛑 Uninstalling Elgato VirtualCam Desktop Application..."

# Stop running application
echo "🔄 Stopping running application..."
pkill -f "python3 virtualcam_app.py" || echo "   No running application found"

# Remove autostart entry
echo "🗑️  Removing autostart entry..."
AUTOSTART_FILE="$HOME/.config/autostart/elgato-virtualcam.desktop"
if [[ -f "$AUTOSTART_FILE" ]]; then
    rm -f "$AUTOSTART_FILE"
    echo "   ✅ Removed: $AUTOSTART_FILE"
else
    echo "   ⚠️  Autostart file not found"
fi

# Remove configuration directory (with confirmation)
CONFIG_DIR="$HOME/.config/elgato-virtualcam"
if [[ -d "$CONFIG_DIR" ]]; then
    read -p "❓ Remove configuration directory $CONFIG_DIR? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$CONFIG_DIR"
        echo "   ✅ Removed configuration directory"
    else
        echo "   ⚠️  Keeping configuration directory"
    fi
else
    echo "   ⚠️  Configuration directory not found"
fi

# Remove sudoers file
echo "🔒 Removing sudoers permissions..."
SUDOERS_FILE="/etc/sudoers.d/elgato-virtualcam"
if [[ -f "$SUDOERS_FILE" ]]; then
    sudo rm -f "$SUDOERS_FILE"
    echo "   ✅ Removed: $SUDOERS_FILE"
else
    echo "   ⚠️  Sudoers file not found"
fi

# Optionally remove user from video group
read -p "❓ Remove user from video group? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo gpasswd -d "$USER" video || echo "   ⚠️  User not in video group"
    echo "   ✅ Removed from video group"
else
    echo "   ⚠️  Keeping video group membership"
fi

# Unload v4l2loopback module
echo "🧯 Stopping virtual camera..."
if lsmod | grep -q v4l2loopback; then
    sudo modprobe -r v4l2loopback && echo "   ✅ v4l2loopback module unloaded"
else
    echo "   ⚠️  v4l2loopback module not loaded"
fi

# Optional: Remove Python dependencies
read -p "❓ Remove Python dependencies (PyQt5)? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip3 uninstall -y PyQt5 || echo "   ⚠️  PyQt5 not installed via pip"
    echo "   ✅ Python dependencies removed"
else
    echo "   ⚠️  Keeping Python dependencies (may be used by other apps)"
fi

echo ""
echo "✅ Uninstall complete!"
echo ""
echo "Note: System dependencies (ffmpeg, v4l2loopback-dkms) were not removed"
echo "      as they may be used by other applications."
echo ""
echo "To completely remove system dependencies:"
echo "  sudo apt remove v4l2loopback-dkms ffmpeg python3-pyqt5"