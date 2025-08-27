#!/bin/bash
set -e

echo "🚀 Installing Elgato VirtualCam Desktop Application..."

# Check for existing installation
if [[ -f "$HOME/.config/autostart/elgato-virtualcam.desktop" ]] || pgrep -f "python3 virtualcam_app.py" > /dev/null; then
    echo "⚠️  Existing installation detected!"
    read -p "❓ Reinstall? This will stop the current app and update files [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🔄 Stopping existing application..."
        pkill -f "python3 virtualcam_app.py" || echo "   No running application found"
        echo "✅ Proceeding with reinstall..."
    else
        echo "❌ Installation cancelled"
        exit 0
    fi
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt update
sudo apt install -y v4l2loopback-dkms ffmpeg python3 python3-pip python3-pyqt5

# Install Python package with dependencies
echo "🐍 Installing Python package..."
pip3 install --user -e .

# Set up permissions for v4l2loopback management
echo "🔒 Setting up permissions for virtual camera management..."
# Add current user to video group
sudo usermod -a -G video "$USER"

# Create sudoers rule for modprobe commands (no password required)
SUDOERS_FILE="/etc/sudoers.d/elgato-virtualcam"
sudo tee "$SUDOERS_FILE" > /dev/null <<EOF
# Allow users in video group to manage v4l2loopback module without password
%video ALL=(root) NOPASSWD: /sbin/modprobe v4l2loopback*, /sbin/modprobe -r v4l2loopback*
$USER ALL=(root) NOPASSWD: /sbin/modprobe v4l2loopback*, /sbin/modprobe -r v4l2loopback*
EOF

echo "✅ Permissions configured - virtual camera can auto-recover from device corruption"

# Setup USB power management to prevent device corruption
echo "🔌 Setting up USB power management..."
UDEV_RULE="/etc/udev/rules.d/99-elgato-nosuspend.rules"
echo 'ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="0fd9", ATTR{idProduct}=="0078", ATTR{power/autosuspend}="-1"' | sudo tee "$UDEV_RULE" > /dev/null
sudo udevadm control --reload-rules
echo "   ✅ USB autosuspend disabled for Elgato Facecam (prevents corruption)"

# Make application executable
chmod +x virtualcam_app.py

# Install autostart entry
echo "🔧 Setting up autostart..."
if command -v elgato-virtualcam >/dev/null 2>&1; then
    elgato-virtualcam --install-autostart
else
    python3 virtualcam_app.py --install-autostart
fi

# Test camera detection
echo "🎥 Testing camera detection..."
if elgato-virtualcam --test-camera 2>/dev/null || python3 virtualcam_app.py --test-camera; then
    echo "✅ Camera detection successful!"
else
    echo "⚠️  Camera not detected - make sure Elgato Facecam is connected"
fi

# Start the application
echo "🚀 Starting VirtualCam application..."
echo "ℹ️  Note: Group membership changes require a fresh shell session"
echo ""
echo "💡 Please run these commands to start the app:"
echo "   exec bash"
if command -v elgato-virtualcam >/dev/null 2>&1; then
    echo "   elgato-virtualcam &"
else
    echo "   python3 virtualcam_app.py &"
fi
echo ""
echo "📱 The camera icon will appear in your system tray when running"

echo ""
echo "✅ Installation complete!"
echo ""
echo "Usage:"
if command -v elgato-virtualcam >/dev/null 2>&1; then
    echo "  # Run the application (entry point)"
    echo "  elgato-virtualcam"
    echo ""
    echo "  # Or run directly"
    echo "  python3 virtualcam_app.py"
else
    echo "  # Run the application"
    echo "  python3 virtualcam_app.py"
fi
echo ""
echo "  # The application will also start automatically on login"
echo "  # Look for the camera icon in your system tray"
echo ""
echo "Commands:"
echo "  # Test camera detection"
if command -v elgato-virtualcam >/dev/null 2>&1; then
    echo "  elgato-virtualcam --test-camera"
    echo ""
    echo "  # Install/reinstall autostart"
    echo "  elgato-virtualcam --install-autostart"
else
    echo "  python3 virtualcam_app.py --test-camera"
    echo ""
    echo "  # Install/reinstall autostart"
    echo "  python3 virtualcam_app.py --install-autostart"
fi