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