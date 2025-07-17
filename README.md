# Elgato VirtualCam for Linux

This project provides a robust virtual webcam pipeline for the **Elgato Facecam** on Ubuntu Linux using `ffmpeg`, `v4l2loopback`, and `systemd`. It creates a virtual webcam device (e.g. `/dev/video10`) that can be used by Chrome, OBS, Zoom, and other video apps — even if the Elgato device itself is unsupported or unstable.

---

## 📦 Features

- Auto-detection of Elgato Facecam
- Automatic transcoding to browser-friendly `yuv420p` format
- Resilient `systemd` service to auto-start on login
- Graceful handling of module reloads and stale processes

---

## 🚀 Installation

### 1. Clone this repository

```bash
git clone https://github.com/YOUR_USERNAME/elgato-virtualcam.git
cd elgato-virtualcam
```

### 2. Run the installer

```bash
chmod +x install.sh
./install.sh
```

The script will:
- Check for required dependencies (`v4l2loopback-dkms`, `ffmpeg`, etc)
- Auto-install anything missing
- Copy the runtime script and systemd unit into the appropriate locations
- Start the virtual webcam service

> If the Elgato Facecam is not plugged in at install time, the service will fall back to runtime detection.

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

---

## 🧼 Uninstallation

```bash
./uninstall.sh
```

Removes:
- The systemd unit
- The background script
- Stops and disables the virtual cam service

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