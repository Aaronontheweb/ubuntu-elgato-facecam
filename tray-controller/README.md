# Elgato VirtualCam Tray Icon Controller

A system tray utility for controlling the Elgato VirtualCam systemd user service on Linux with theme-aware icons and real-time status monitoring.

## Features

- ✅ **One-click toggle** - Left-click to start/stop the VirtualCam service
- 🎨 **Theme-aware icons** - Automatically switches between light/dark mode icons
- 🔄 **Real-time status** - Icons and tooltips update automatically every 5 seconds
- 📱 **Desktop notifications** - Get notified when the service starts/stops
- 📜 **Service logs** - View recent service logs via right-click menu
- 🎯 **Status indicators**:
  - **Green**: VirtualCam is running
  - **Black/White**: VirtualCam is stopped (theme-dependent)
  - **Yellow**: VirtualCam status unclear
  - **Red**: VirtualCam service unavailable

## Installation & Usage

### 1. Install Dependencies

```bash
sudo apt install python3 python3-pyqt5
```

### 2. Run the Tray Controller

```bash
cd tray-controller
python3 virtualcam-tray.py
```

### 3. Usage

- **Left-click** the tray icon to toggle the VirtualCam service on/off
- **Right-click** for the context menu with additional options:
  - Start/Stop VirtualCam
  - Refresh Status
  - View Logs
  - Quit

## Autostart (Optional)

To start the tray controller automatically on login, create:

```bash
~/.config/autostart/elgato-virtualcam-tray.desktop
```

With contents:
```ini
[Desktop Entry]
Type=Application
Exec=/path/to/tray-controller/virtualcam-tray.py
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=Elgato VirtualCam Tray
Comment=Tray icon controller for VirtualCam
```

## Requirements

- Ubuntu 20.04+ (or compatible Linux distribution)
- Python 3.6+
- PyQt5
- systemd (user services)
- The main `elgato-virtualcam.service` must be installed and configured

## Troubleshooting

- **No tray icon visible**: Ensure your desktop environment supports system tray icons
- **Service control fails**: Verify the `elgato-virtualcam.service` is properly installed
- **Icons not displaying**: Check that the `assets/` directory contains the icon files 