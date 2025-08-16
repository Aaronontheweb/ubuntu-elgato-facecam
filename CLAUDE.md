# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Elgato Facecam virtual webcam solution for Ubuntu Linux that creates a virtual webcam pipeline using ffmpeg, v4l2loopback, and a unified desktop application. **The project has been successfully refactored from a problematic systemd approach to a reliable desktop application following the Witticism project model.**

### Current Architecture (NEW - Working)
1. **Unified Desktop Application** - Single Python application (`virtualcam_app.py`) that manages everything
2. **Integrated System Tray** - Built-in PyQt5 tray interface with real-time status
3. **Direct Process Management** - FFmpeg subprocess control instead of systemd
4. **Desktop Integration** - Standard autostart via `.desktop` files

### Previous Issues (RESOLVED)
- ✅ **systemd permission issues** - Eliminated by removing systemd dependency
- ✅ **Complex hardware access** - Now handled directly in user context
- ✅ **Environment complications** - Natural desktop environment inheritance
- ✅ **Timing issues** - Application starts when needed, not at boot
- ✅ **Debugging difficulties** - Standard Python logging and direct execution

## Commands

### Installation & Setup (NEW Desktop App)
```bash
# Install the unified desktop application
./install-desktop-app.sh

# Test the system before running
./test-desktop-app.sh

# Run the application
python3 virtualcam_app.py

# Install autostart integration
python3 virtualcam_app.py --install-autostart
```

### Application Management
```bash
# Test camera detection
python3 virtualcam_app.py --test-camera

# Run in debug mode
python3 virtualcam_app.py --debug

# View logs
tail -f ~/.config/elgato-virtualcam/virtualcam.log
tail -f ~/.config/elgato-virtualcam/virtualcam.err.log
```

### Legacy Commands (Systemd - Deprecated)
```bash
# Old systemd approach (has permission issues)
./install.sh              # Legacy installer
systemctl --user start elgato-virtualcam.service
systemctl --user stop elgato-virtualcam.service
./uninstall.sh           # Legacy uninstaller
```

### Testing & Verification
```bash
# List video devices to verify virtual camera exists
v4l2-ctl --list-devices

# Test virtual camera with cheese
cheese -d /dev/video10

# Check if v4l2loopback module is loaded
lsmod | grep v4l2loopback

# Manually load v4l2loopback module
sudo modprobe v4l2loopback video_nr=10 card_label="VirtualCam" exclusive_caps=1
```

### Tray Controller
```bash
# Run tray controller manually
./tray-controller/virtualcam-tray.py

# Install Python dependencies
pip3 install -r tray-controller/requirements.txt --user
```

## Architecture

### Current Components (NEW - Working)

**virtualcam_app.py** - Unified desktop application that:
- **ConfigManager**: JSON configuration with reasonable defaults and GUI settings
- **CameraManager**: Auto-detects Elgato Facecam and manages FFmpeg subprocess directly
- **SystemTray**: Integrated PyQt5 tray with dynamic status icons and context menu
- **VirtualCamApp**: Main application class with proper signal handling and graceful shutdown
- Auto-loads v4l2loopback module with natural sudo prompts in desktop context
- Uses standard Python logging to `~/.config/elgato-virtualcam/virtualcam.log`
- Desktop autostart via `~/.config/autostart/elgato-virtualcam.desktop`

**Supporting Files**:
- **pyproject.toml**: Professional Python packaging for PyPI distribution
- **requirements.txt**: Minimal dependencies (just PyQt5)
- **install-desktop-app.sh**: Clean installation script
- **test-desktop-app.sh**: Comprehensive testing suite

### Legacy Components (Deprecated - Permission Issues)

**src/elgato-virtualcam.sh** - Bash script with systemd service
**src/elgato-virtualcam.service** - Systemd user service (problematic)
**tray-controller/virtualcam-tray.py** - Separate tray application
**install.sh** - Legacy installer with systemd setup

### Benefits of New Architecture

- ✅ **No systemd dependencies** - Eliminates all permission issues
- ✅ **Single process** - Easier debugging and management
- ✅ **Direct hardware access** - Natural device detection and module loading
- ✅ **Professional packaging** - Ready for PyPI distribution
- ✅ **Standard desktop integration** - Uses proven patterns from Witticism project

## Key Technical Details

- **Video Pipeline**: Elgato Facecam (uyvy422) → ffmpeg subprocess → v4l2loopback (/dev/video10, yuv420p)
- **Dependencies**: v4l2loopback-dkms, ffmpeg, python3-pyqt5
- **Virtual Device**: Always created at /dev/video10 with label "VirtualCam"
- **Configuration**: JSON config at `~/.config/elgato-virtualcam/config.json`
- **Logging**: Application logs to `~/.config/elgato-virtualcam/virtualcam.log`

## Implementation Status

### ✅ COMPLETED: Desktop Application Refactoring
Following the [Witticism project](https://github.com/Aaronontheweb/witticism) model:

1. ✅ **Single Python Application**: Combined service logic and tray interface into `virtualcam_app.py`
2. ✅ **Subprocess Management**: FFmpeg runs as managed subprocess with proper cleanup
3. ✅ **Desktop Autostart**: Uses `~/.config/autostart/elgato-virtualcam.desktop`
4. ✅ **Direct Hardware Access**: Sudo operations work naturally in desktop context
5. ✅ **Integrated Debugging**: Standard Python logging with clear output

### Benefits Achieved
- ✅ Eliminated all systemd permission issues
- ✅ Simplified debugging and development
- ✅ Better hardware integration with natural device detection
- ✅ Natural environment variable inheritance
- ✅ Professional packaging ready for PyPI distribution

## Important File Locations

### NEW Desktop Application
- **Main application**: `virtualcam_app.py` (unified desktop app)
- **Configuration**: `~/.config/elgato-virtualcam/config.json`
- **Application logs**: `~/.config/elgato-virtualcam/virtualcam.log`
- **FFmpeg logs**: `~/.config/elgato-virtualcam/virtualcam.err.log`
- **Autostart entry**: `~/.config/autostart/elgato-virtualcam.desktop`
- **Install script**: `install-desktop-app.sh`
- **Test script**: `test-desktop-app.sh`

### Legacy Files (Deprecated)
- Virtual camera script: `~/.local/bin/elgato-virtualcam.sh` (legacy)
- Systemd service: `~/.config/systemd/user/elgato-virtualcam.service` (deprecated)
- Old service logs: `/tmp/elgato-virtualcam.log` and `/tmp/elgato-virtualcam.err.log`
- Separate tray app: `tray-controller/virtualcam-tray.py` (deprecated)

## Development Notes

- **Build process**: Standard Python packaging with `pyproject.toml`
- **Testing**: Comprehensive test suite in `test-desktop-app.sh`
- **Hardware requirement**: Physical Elgato Facecam for full testing
- **Module requirement**: v4l2loopback-dkms must be compiled for current kernel
- **✅ RESOLVED**: All systemd permission issues eliminated
- **✅ COMPLETED**: Successfully refactored to Witticism desktop application model