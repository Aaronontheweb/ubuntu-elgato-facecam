# Elgato VirtualCam for Linux

## Doesn't work - having permissions issues with `systemd`

This project provides a robust virtual webcam pipeline for the **Elgato Facecam** on Ubuntu Linux using `ffmpeg`, `v4l2loopback`, and `systemd`. It creates a virtual webcam device (e.g. `/dev/video10`) that can be used by Chrome, OBS, Zoom, and other video apps — even if the Elgato device itself is unsupported or unstable.

---

## 📦 Features

- **🎥 Auto-detection** of Elgato Facecam
- **🔄 Automatic transcoding** to browser-friendly `yuv420p` format
- **🚀 Resilient systemd service** to auto-start on login
- **🖱️ GUI tray controller** for easy on/off control
- **🎨 Theme-aware tray icons** (automatically adapts to light/dark mode)
- **📱 Desktop notifications** when service starts/stops
- **🔧 Graceful handling** of module reloads and stale processes

---

## 🚀 Installation

### 1. Clone this repository

```bash
git clone https://github.com/Aaronontheweb/ubuntu-elgato-facecam.git
cd ubuntu-elgato-facecam
```

### 2. Run the installer

```bash
chmod +x install.sh
./install.sh
```

The script will:
- Check for required dependencies (`v4l2loopback-dkms`, `ffmpeg`, `python3-pyqt5`, etc)
- Auto-install anything missing
- Copy the runtime script and systemd unit into the appropriate locations
- **Set up GUI tray controller with autostart**
- Start both the virtual webcam service and tray controller

**What you get immediately:**
- 🎥 Virtual webcam available in `/dev/video10`
- 🖱️ System tray icon for easy control (look for camera icon)
- 🚀 Both components auto-start on login

> If the Elgato Facecam is not plugged in at install time, the service will fall back to runtime detection.

---

## 🖱️ Using the Tray Controller

After installation, you'll see a **camera icon** in your system tray that provides easy control:

### 📱 Quick Actions
- **Left-click**: Toggle virtual camera on/off
- **Right-click**: Open context menu with options:
  - Start/Stop VirtualCam
  - Refresh Status  
  - View Logs
  - Quit

### 🎨 Status Indicators
- **🟢 Green icon**: VirtualCam is running
- **⚫ Black/White icon**: VirtualCam is stopped (theme-dependent)
- **🟡 Yellow icon**: VirtualCam status unclear
- **🔴 Red icon**: VirtualCam service unavailable

### 🔧 Manual Control (Alternative)
If you prefer command line:

```bash
# Start virtual camera
systemctl --user start elgato-virtualcam.service

# Stop virtual camera  
systemctl --user stop elgato-virtualcam.service

# Check status
systemctl --user status elgato-virtualcam.service
```

---

## 🧪 How to Test

### ✅ Check the virtual device

```bash
v4l2-ctl --list-devices
```

You should see an entry like:

```
VirtualCam: VirtualCam (platform:v4l2loopback-000)
    /dev/video10
```

### ✅ View with `cheese`

```bash
cheese -d /dev/video10
```

Or select it via the **menu > preferences > camera** dropdown in Cheese.

### ✅ Test in browser

Open:
- [https://webcamtests.com](https://webcamtests.com)
- Google Meet or Zoom settings

Then select **"VirtualCam"** as your webcam device.

---

## 🔧 Troubleshooting

### 🧱 "modprobe: Module v4l2loopback is in use"

The service may still be running. Run:

```bash
systemctl --user stop elgato-virtualcam.service
sudo modprobe -r v4l2loopback
```

Then restart:

```bash
sudo modprobe v4l2loopback video_nr=10 card_label="VirtualCam" exclusive_caps=1
systemctl --user start elgato-virtualcam.service
```

### 📉 FFmpeg crashes or fails to open device

Check logs:

```bash
tail -n 50 /tmp/elgato-virtualcam.err.log
```

Look for errors like `Device busy`, `Unable to open`, or `Broken pipe`.

### 🧵 Too many frame drops?

Lower the resolution or framerate in `elgato-virtualcam.sh`:

```bash
-video_size 960x540 -framerate 30
```

### 🖱️ Tray icon not visible?

**Desktop environment compatibility:**
- Ensure your desktop environment supports system tray icons
- GNOME users may need to install the "AppIndicator" extension
- Try running the tray controller manually: `./tray-controller/virtualcam-tray.py`

**Dependencies:**
- Verify PyQt5 is installed: `dpkg -s python3-pyqt5`
- Check for errors: `python3 ./tray-controller/virtualcam-tray.py`

---

## 🧼 Uninstallation

```bash
./uninstall.sh
```

**Complete cleanup removes:**
- 🛑 The systemd service (stops and disables)
- 📄 The background script
- 🖱️ Tray controller (stops process and removes autostart)
- 🔧 v4l2loopback kernel module (optional)

**What stays:**
- ✅ PyQt5 package (other applications might need it)

You can manually remove the module with:

```bash
sudo modprobe -r v4l2loopback
```

---

## 🤝 Credits

- Based on tools provided by the Linux UVC community
- Inspired by OBS + v4l2loopback setups

---

## 📬 License

MIT License — see `LICENSE` file for details.
