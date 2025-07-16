#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
SERVICE_NAME="elgato-virtualcam.service"
INSTALL_DIR="$HOME/.config/systemd/user"
TARGET_SERVICE="$INSTALL_DIR/$SERVICE_NAME"
TARGET_SCRIPT="$HOME/.local/bin/elgato-virtualcam.sh"

echo "🔍 Checking and installing required packages..."

REQUIRED_PKGS=(v4l2loopback-dkms v4l2loopback-utils ffmpeg)

check_and_install_pkg() {
  local pkg="$1"
  dpkg -s "$pkg" &>/dev/null && {
    echo "✅ $pkg is already installed"
    return 0
  }

  echo "📦 Installing missing package: $pkg"
  if ! sudo apt-get install -y "$pkg"; then
    echo "⚠️  Warning: failed to install $pkg — continuing..."
  fi

  # Final verification
  if ! dpkg -s "$pkg" &>/dev/null; then
    echo "❌ $pkg is still not installed. You may need to fix this manually."
    return 1
  fi
}

apt_update_once=false
for pkg in "${REQUIRED_PKGS[@]}"; do
  if ! dpkg -s "$pkg" &>/dev/null; then
    if [ "$apt_update_once" = false ]; then
      echo "🔄 Running apt update..."
      sudo apt-get update || echo "⚠️  apt update failed, continuing..."
      apt_update_once=true
    fi
    check_and_install_pkg "$pkg"
  else
    echo "✅ $pkg already installed"
  fi
done

echo "📁 Creating user systemd directory (if missing)..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$(dirname "$TARGET_SCRIPT")"

echo "📄 Copying service and script..."
cp "$SRC_DIR/elgato-virtualcam.sh" "$TARGET_SCRIPT"
chmod +x "$TARGET_SCRIPT"

# Detect Elgato device path at install time
ELGATO_DEV=$(v4l2-ctl --list-devices 2>/dev/null | awk '/Elgato Facecam/{getline; print $1}' | head -n 1)

if [[ -z "$ELGATO_DEV" ]]; then
  echo "⚠️  Warning: Could not detect Elgato Facecam now. Will fall back to autodetect at runtime."
  SERVICE_EXEC="$TARGET_SCRIPT"
else
  echo "📸 Detected Elgato Facecam at $ELGATO_DEV"
  SERVICE_EXEC="$TARGET_SCRIPT $ELGATO_DEV"
fi

# Inject ExecStart line with optional device path
sed "s|ExecStart=.*|ExecStart=$SERVICE_EXEC|" "$SRC_DIR/$SERVICE_NAME" > "$TARGET_SERVICE"

echo "🔄 Reloading systemd user services..."
systemctl --user daemon-reexec
systemctl --user daemon-reload

# Ensure lingering is enabled (so user services can run at boot)
if ! loginctl show-user "$USER" | grep -q "Linger=yes"; then
  echo "🔐 Enabling systemd user lingering..."
  sudo loginctl enable-linger "$USER"
fi

echo "🚀 Enabling and starting elgato-virtualcam service..."
systemctl --user enable --now "$SERVICE_NAME"

echo "✅ Install complete! The virtual webcam should now be available at /dev/video10."
