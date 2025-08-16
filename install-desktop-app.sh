#!/bin/bash
set -e

echo "🚀 Installing Elgato VirtualCam Desktop Application..."

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt update
sudo apt install -y v4l2loopback-dkms ffmpeg python3 python3-pip python3-pyqt5

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip3 install --user -r requirements.txt

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

# Make application executable
chmod +x virtualcam_app.py

# Install autostart entry
echo "🔧 Setting up autostart..."
python3 virtualcam_app.py --install-autostart

# Test camera detection
echo "🎥 Testing camera detection..."
if python3 virtualcam_app.py --test-camera; then
    echo "✅ Camera detection successful!"
else
    echo "⚠️  Camera not detected - make sure Elgato Facecam is connected"
fi

# Launch the application in background
echo "🚀 Starting VirtualCam application..."

# Check if we need to use newgrp for group membership (first time setup)
if groups | grep -q video; then
    # User already in video group, start normally
    python3 virtualcam_app.py &> /dev/null &
    if [ $? -eq 0 ]; then
        echo "✅ VirtualCam started successfully in background"
        echo "📱 Look for the camera icon in your system tray"
    else
        echo "⚠️  Failed to start application automatically"
        echo "💡 You can start it manually with: python3 virtualcam_app.py"
    fi
else
    # User needs to refresh group membership
    echo "ℹ️  Group membership requires refresh for permissions to take effect"
    echo "💡 Please log out and log back in, then run: python3 virtualcam_app.py"
    echo "📱 Or start it now with: newgrp video -c 'python3 virtualcam_app.py &'"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Usage:"
echo "  # Run the application"
echo "  python3 virtualcam_app.py"
echo ""
echo "  # The application will also start automatically on login"
echo "  # Look for the camera icon in your system tray"
echo ""
echo "Commands:"
echo "  # Test camera detection"
echo "  python3 virtualcam_app.py --test-camera"
echo ""
echo "  # Install/reinstall autostart"
echo "  python3 virtualcam_app.py --install-autostart"