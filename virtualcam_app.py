#!/usr/bin/env python3
"""
Elgato VirtualCam Desktop Application

A unified desktop application for managing Elgato Facecam virtual camera streaming.
Replaces the systemd service approach with a single Python application.

Based on the Witticism project model for robust desktop application architecture.
"""

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QMenu,
    QSystemTrayIcon,
)


class ConfigManager:
    """Manages application configuration with reasonable defaults"""

    def __init__(self, app_name="elgato-virtualcam"):
        self.config_dir = Path.home() / '.config' / app_name
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / 'config.json'

        self.default_config = {
            "virtual_device": "/dev/video10",
            "virtual_device_label": "VirtualCam",
            "ffmpeg_params": {
                "framerate": 30,
                "input_format": "uyvy422",
                "video_size": "1280x720",
                "output_format": "yuv420p"
            },
            "ui": {
                "show_notifications": True,
                "start_minimized": True,
                "update_interval": 5000
            },
            "logging": {
                "level": "INFO",
                "file": str(self.config_dir / 'virtualcam.log')
            }
        }

        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load configuration with fallback to defaults"""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    user_config = json.load(f)
                # Deep merge with defaults
                config = self.default_config.copy()
                self._deep_merge(config, user_config)
                return config
            except Exception as e:
                logging.warning(f"Failed to load config: {e}, using defaults")

        return self.default_config.copy()

    def save_config(self):
        """Save current configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

    def get(self, key: str, default=None):
        """Get config value using dot notation"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value):
        """Set config value using dot notation"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()

    def _deep_merge(self, base: dict, update: dict):
        """Deep merge update dict into base dict"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value


class CameraManager:
    """Manages Elgato Facecam detection and ffmpeg streaming"""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.ffmpeg_process: Optional[subprocess.Popen] = None
        self.elgato_device: Optional[str] = None

    def detect_elgato_camera(self) -> Optional[str]:
        """Auto-detect Elgato Facecam device"""
        try:
            result = subprocess.run(
                ['v4l2-ctl', '--list-devices'],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for i, line in enumerate(lines):
                    if 'Elgato Facecam' in line:
                        # Next line should contain the device path
                        if i + 1 < len(lines):
                            device_line = lines[i + 1].strip()
                            if device_line.startswith('/dev/video'):
                                device = device_line.split()[0]
                                logging.info(f"Detected Elgato Facecam at {device}")
                                return device

            logging.warning("Elgato Facecam not detected")
            return None

        except Exception as e:
            logging.error(f"Error detecting camera: {e}")
            return None

    def ensure_v4l2loopback_loaded(self) -> bool:
        """Ensure v4l2loopback module is loaded"""
        try:
            # Check if module is already loaded
            result = subprocess.run(['lsmod'], capture_output=True, text=True)
            if 'v4l2loopback' in result.stdout:
                logging.info("v4l2loopback module already loaded")
                return True

            # Load module with parameters
            virtual_device_nr = self.config.get('virtual_device', '/dev/video10').replace('/dev/video', '')
            label = self.config.get('virtual_device_label', 'VirtualCam')

            cmd = [
                'sudo', 'modprobe', 'v4l2loopback',
                f'video_nr={virtual_device_nr}',
                f'card_label={label}',
                'exclusive_caps=1'
            ]

            logging.info("Loading v4l2loopback module...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                logging.info("v4l2loopback module loaded successfully")
                return True
            else:
                logging.error(f"Failed to load v4l2loopback: {result.stderr}")
                return False

        except Exception as e:
            logging.error(f"Error loading v4l2loopback: {e}")
            return False

    def verify_virtual_device(self) -> bool:
        """Verify that virtual camera device exists"""
        virtual_dev = self.config.get('virtual_device', '/dev/video10')
        if os.path.exists(virtual_dev):
            logging.info(f"Virtual device {virtual_dev} is available")
            return True
        else:
            logging.error(f"Virtual device {virtual_dev} not found")
            return False

    def reset_virtual_device(self) -> bool:
        """Reset v4l2loopback device to clear corruption"""
        try:
            virtual_device_nr = self.config.get('virtual_device', '/dev/video10').replace('/dev/video', '')
            label = self.config.get('virtual_device_label', 'VirtualCam')

            logging.info("Resetting v4l2loopback device to clear corruption...")

            # Remove module
            result = subprocess.run(['sudo', 'modprobe', '-r', 'v4l2loopback'],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logging.error(f"Failed to remove v4l2loopback module: {result.stderr}")
                return False

            # Reload module with parameters
            cmd = [
                'sudo', 'modprobe', 'v4l2loopback',
                f'video_nr={virtual_device_nr}',
                f'card_label={label}',
                'exclusive_caps=1'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logging.info("v4l2loopback device reset successfully")
                return True
            else:
                logging.error(f"Failed to reload v4l2loopback: {result.stderr}")
                return False

        except Exception as e:
            logging.error(f"Error resetting virtual device: {e}")
            return False

    def is_streaming(self) -> bool:
        """Check if ffmpeg process is running and healthy"""
        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            return True
        elif self.ffmpeg_process and self.ffmpeg_process.poll() is not None:
            # Process has exited, clean up
            logging.warning(f"FFmpeg process exited with code {self.ffmpeg_process.returncode}")
            self.ffmpeg_process = None
        return False

    def start_streaming(self) -> bool:
        """Start ffmpeg streaming process"""
        if self.is_streaming():
            logging.warning("Streaming already active")
            return True

        # Detect camera
        self.elgato_device = self.detect_elgato_camera()
        if not self.elgato_device:
            logging.error("Cannot start streaming: Elgato Facecam not detected")
            return False

        # Ensure v4l2loopback is loaded
        if not self.ensure_v4l2loopback_loaded():
            logging.error("Cannot start streaming: v4l2loopback module not available")
            return False

        # Verify virtual device exists
        if not self.verify_virtual_device():
            logging.error("Cannot start streaming: virtual device not available")
            return False

        # Build ffmpeg command
        params = self.config.get('ffmpeg_params', {})
        virtual_dev = self.config.get('virtual_device', '/dev/video10')

        cmd = [
            'ffmpeg',
            '-f', 'v4l2',
            '-framerate', str(params.get('framerate', 30)),
            '-input_format', params.get('input_format', 'uyvy422'),
            '-video_size', params.get('video_size', '1280x720'),
            '-i', self.elgato_device,
            '-f', 'v4l2',
            '-pix_fmt', params.get('output_format', 'yuv420p'),
            virtual_dev
        ]

        try:
            # Start ffmpeg process (match original bash script approach)
            log_file = self.config.get('logging.file', '/tmp/elgato-virtualcam.log')
            stderr_log = log_file.replace('.log', '.err.log')

            logging.info(f"Starting FFmpeg with command: {' '.join(cmd)}")
            logging.info(f"Error log will be at: {stderr_log}")

            stderr_file = open(stderr_log, 'a')

            self.ffmpeg_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                preexec_fn=os.setsid  # Create new process group
            )

            # Give it a moment to start
            time.sleep(1)

            if self.ffmpeg_process.poll() is None:
                logging.info(f"Streaming started: {self.elgato_device} → {virtual_dev}")
                return True
            else:
                logging.error("FFmpeg process failed to start - attempting device reset")

                # Attempt auto-recovery by resetting virtual device
                if self.reset_virtual_device():
                    logging.info("Device reset successful, retrying FFmpeg...")

                    # Retry FFmpeg with fresh device
                    stderr_file = open(stderr_log, 'a')
                    self.ffmpeg_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=stderr_file,
                        preexec_fn=os.setsid
                    )

                    time.sleep(1)

                    if self.ffmpeg_process.poll() is None:
                        logging.info(f"Streaming started after device reset: {self.elgato_device} → {virtual_dev}")
                        return True
                    else:
                        logging.error("FFmpeg failed again after device reset")
                        return False
                else:
                    logging.error("Device reset failed")
                    return False

        except Exception as e:
            logging.error(f"Error starting streaming: {e}")
            return False

    def stop_streaming(self) -> bool:
        """Stop ffmpeg streaming process"""
        if not self.ffmpeg_process:
            return True

        try:
            # Terminate the process group
            os.killpg(os.getpgid(self.ffmpeg_process.pid), signal.SIGTERM)

            # Wait for process to end
            try:
                self.ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                os.killpg(os.getpgid(self.ffmpeg_process.pid), signal.SIGKILL)
                self.ffmpeg_process.wait()

            self.ffmpeg_process = None
            logging.info("Streaming stopped")
            return True

        except Exception as e:
            logging.error(f"Error stopping streaming: {e}")
            return False


class SystemTray:
    """System tray interface with status indication"""

    def __init__(self, app):
        print("DEBUG: SystemTray.__init__ starting...")
        self.app = app
        self.config = app.config
        self.camera = app.camera
        print("DEBUG: SystemTray variables set")

        # Create tray icon
        print("DEBUG: Creating QSystemTrayIcon...")
        self.tray = QSystemTrayIcon()
        print("DEBUG: QSystemTrayIcon created")

        print("DEBUG: Connecting activated signal...")
        self.tray.activated.connect(self.on_tray_activated)
        print("DEBUG: Signal connected")

        # Create menu
        print("DEBUG: Creating menu...")
        self.create_menu()
        print("DEBUG: Menu created")

        # Timer for status updates
        print("DEBUG: Creating timer...")
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(self.config.get('ui.update_interval', 5000))
        print("DEBUG: Timer started")

        # Track previous status for automatic recovery
        self._consecutive_errors = 0
        self._max_consecutive_errors = 3

        # Initial status update
        print("DEBUG: Updating initial status...")
        self.update_status()
        print("DEBUG: Status updated")

        print("DEBUG: Showing tray icon...")
        self.tray.show()
        print("DEBUG: SystemTray.__init__ complete")

    def create_dynamic_icon(self, status: str) -> QIcon:
        """Create status-based tray icon using proper camera images"""
        try:
            # Map status to icon files
            icon_map = {
                'on': 'camera-on.png',
                'off': 'camera-off-black.png',
                'error': 'camera-disconnected.png',
                'starting': 'camera-unsure.png'
            }

            icon_file = icon_map.get(status, 'camera-off-black.png')
            icon_path = Path(__file__).parent / 'tray-controller' / 'assets' / icon_file

            if icon_path.exists():
                return QIcon(str(icon_path))
            else:
                # Fallback to simple colored circle if icon file missing
                pixmap = QPixmap(64, 64)
                pixmap.fill(Qt.transparent)

                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.Antialiasing)

                colors = {
                    'on': QColor(76, 175, 80),
                    'off': QColor(158, 158, 158),
                    'error': QColor(244, 67, 54),
                    'starting': QColor(255, 193, 7)
                }

                color = colors.get(status, colors['off'])
                painter.setBrush(color)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(16, 16, 32, 32)
                painter.end()

                return QIcon(pixmap)

        except Exception as e:
            logging.error(f"Error creating icon: {e}")
            return QIcon()

    def create_menu(self):
        """Create context menu"""
        self.menu = QMenu()

        # Toggle action
        self.toggle_action = QAction("Start VirtualCam", self.menu)
        self.toggle_action.triggered.connect(self.toggle_streaming)
        self.menu.addAction(self.toggle_action)

        self.menu.addSeparator()

        # Refresh
        refresh_action = QAction("Refresh", self.menu)
        refresh_action.triggered.connect(self.update_status)
        self.menu.addAction(refresh_action)

        # Diagnostics
        diagnostics_action = QAction("Run Diagnostics", self.menu)
        diagnostics_action.triggered.connect(self.run_diagnostics)
        self.menu.addAction(diagnostics_action)

        # Reset virtual device (for recovery)
        reset_action = QAction("Reset Virtual Device", self.menu)
        reset_action.triggered.connect(self.reset_virtual_device)
        self.menu.addAction(reset_action)

        self.menu.addSeparator()

        # Quit
        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

        self.tray.setContextMenu(self.menu)

    def get_status(self) -> Tuple[str, str]:
        """Get current streaming status with detailed message"""
        # Check if streaming first (fastest check)
        if self.camera.is_streaming():
            return 'on', 'VirtualCam is streaming'

        # Check virtual device availability
        virtual_dev = self.config.get('virtual_device', '/dev/video10')
        if not os.path.exists(virtual_dev):
            return 'error', f'Virtual device {virtual_dev} not found (v4l2loopback not loaded?)'

        # Check camera availability (only if not streaming to avoid interference)
        camera_device = self.camera.elgato_device or self.camera.detect_elgato_camera()
        if camera_device:
            return 'off', f'VirtualCam ready (camera: {camera_device})'
        else:
            return 'error', 'Elgato Facecam not detected or in use'

    def update_status(self):
        """Update tray icon and tooltip"""
        status, message = self.get_status()

        # Update icon
        self.tray.setIcon(self.create_dynamic_icon(status))

        # Update tooltip with detailed message
        self.tray.setToolTip(message)

        # Update menu
        if status == 'on':
            self.toggle_action.setText("Stop VirtualCam")
        else:
            self.toggle_action.setText("Start VirtualCam")

        # Log status for debugging (but throttle logging)
        if not hasattr(self, '_last_status') or self._last_status != (status, message):
            logging.info(f"Status: {status} - {message}")
            self._last_status = (status, message)

        # Automatic recovery logic
        if status == 'error':
            self._consecutive_errors += 1
            if self._consecutive_errors >= self._max_consecutive_errors:
                logging.warning(f"Too many consecutive errors ({self._consecutive_errors}), attempting automatic recovery")
                self.attempt_recovery()
                self._consecutive_errors = 0  # Reset counter after recovery attempt
        else:
            self._consecutive_errors = 0  # Reset counter on success

    def toggle_streaming(self):
        """Toggle streaming on/off"""
        if self.camera.is_streaming():
            success = self.camera.stop_streaming()
            message = "VirtualCam stopped" if success else "Failed to stop VirtualCam"
        else:
            success = self.camera.start_streaming()
            message = "VirtualCam started" if success else "Failed to start VirtualCam"

        self.show_notification(message)
        self.update_status()

    def show_notification(self, message: str):
        """Show system notification"""
        if self.config.get('ui.show_notifications', True) and self.tray.supportsMessages():
            self.tray.showMessage("Elgato VirtualCam", message, QSystemTrayIcon.Information, 3000)

    def run_diagnostics(self):
        """Run system diagnostics and show results"""
        diagnostics = []

        # Check v4l2loopback module
        try:
            result = subprocess.run(['lsmod'], capture_output=True, text=True, timeout=5)
            if 'v4l2loopback' in result.stdout:
                diagnostics.append("✅ v4l2loopback module loaded")
            else:
                diagnostics.append("❌ v4l2loopback module not loaded")
        except Exception as e:
            diagnostics.append(f"❌ Error checking kernel modules: {e}")

        # Check virtual device
        virtual_dev = self.config.get('virtual_device', '/dev/video10')
        if os.path.exists(virtual_dev):
            diagnostics.append(f"✅ Virtual device {virtual_dev} exists")
        else:
            diagnostics.append(f"❌ Virtual device {virtual_dev} not found")

        # Check camera detection
        camera_device = self.camera.detect_elgato_camera()
        if camera_device:
            diagnostics.append(f"✅ Elgato Facecam detected at {camera_device}")
        else:
            diagnostics.append("❌ Elgato Facecam not detected")

        # Check FFmpeg process
        if self.camera.is_streaming():
            diagnostics.append("✅ FFmpeg streaming process running")
        else:
            diagnostics.append("❌ FFmpeg streaming not active")

        # Show notification with results
        message = "Diagnostics:\n" + "\n".join(diagnostics)
        logging.info(f"Diagnostics results:\n{message}")
        self.show_notification("Diagnostics complete - check logs for details")

    def reset_virtual_device(self):
        """Reset virtual device for recovery"""
        logging.info("User requested virtual device reset")
        if self.camera.is_streaming():
            self.camera.stop_streaming()

        success = self.camera.reset_virtual_device()
        message = "Virtual device reset successfully" if success else "Failed to reset virtual device"
        self.show_notification(message)
        self.update_status()

    def attempt_recovery(self):
        """Attempt automatic system recovery"""
        logging.info("Attempting automatic recovery...")

        # Stop any existing processes
        if self.camera.is_streaming():
            self.camera.stop_streaming()

        # Try to reset virtual device
        if self.camera.reset_virtual_device():
            logging.info("Virtual device reset successful during recovery")
            self.show_notification("Automatic recovery: Virtual device reset")
        else:
            logging.warning("Virtual device reset failed during recovery")
            self.show_notification("Automatic recovery failed - manual intervention may be needed")

    def on_tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.Trigger:  # Left click
            self.toggle_streaming()



class VirtualCamApp:
    """Main application class"""

    def __init__(self):
        print("DEBUG: Initializing VirtualCamApp...")

        # Setup logging
        print("DEBUG: Setting up logging...")
        self.setup_logging()
        logging.info("DEBUG: Logging setup complete")

        # Initialize components
        print("DEBUG: Creating ConfigManager...")
        self.config = ConfigManager()
        logging.info("DEBUG: ConfigManager created")

        print("DEBUG: Creating CameraManager...")
        self.camera = CameraManager(self.config)
        logging.info("DEBUG: CameraManager created")

        # SystemTray will be created later after checking availability
        self.tray = None

        # Handle signals for graceful shutdown
        print("DEBUG: Setting up signal handlers...")
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        logging.info("DEBUG: Signal handlers set up")

        logging.info("Elgato VirtualCam application initialized successfully")

    def create_system_tray(self):
        """Create system tray after verifying availability"""
        print("DEBUG: Creating SystemTray...")
        self.tray = SystemTray(self)
        logging.info("DEBUG: SystemTray created")

    def setup_logging(self):
        """Configure logging"""
        log_level = logging.INFO
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(Path.home() / '.config/elgato-virtualcam/virtualcam.log')
            ]
        )

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logging.info(f"Received signal {signum}, shutting down...")
        self.quit()

    def quit(self):
        """Quit application gracefully"""
        logging.info("Shutting down application...")

        # Stop streaming
        if self.camera.is_streaming():
            self.camera.stop_streaming()

        # Stop timer
        if self.tray and hasattr(self.tray, 'timer'):
            self.tray.timer.stop()

        # Quit application
        QApplication.quit()


def install_autostart():
    """Install desktop autostart entry"""
    autostart_dir = Path.home() / '.config/autostart'
    autostart_dir.mkdir(parents=True, exist_ok=True)

    # Prefer entry point if available, fallback to direct script execution
    entry_point_cmd = shutil.which('elgato-virtualcam')
    if entry_point_cmd:
        exec_cmd = entry_point_cmd
    else:
        # Fallback to direct script execution
        python_exec = shutil.which('python3') or sys.executable
        exec_cmd = f"{python_exec} {os.path.abspath(__file__)}"

    desktop_entry = f"""[Desktop Entry]
Type=Application
Name=Elgato VirtualCam
Exec={exec_cmd}
StartupNotify=false
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=10
Comment=Elgato Facecam Virtual Camera Controller
"""

    autostart_file = autostart_dir / 'elgato-virtualcam.desktop'
    autostart_file.write_text(desktop_entry)
    print(f"✅ Autostart entry installed: {autostart_file}")


def main():
    """Main entry point"""
    print("DEBUG: main() function started")
    import argparse
    print("DEBUG: argparse imported")

    parser = argparse.ArgumentParser(description='Elgato VirtualCam Desktop Application')
    print("DEBUG: ArgumentParser created")
    parser.add_argument('--install-autostart', action='store_true',
                        help='Install desktop autostart entry')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--test-camera', action='store_true',
                        help='Test camera detection and exit')
    parser.add_argument('--start', action='store_true',
                        help='Start streaming (command-line mode)')
    parser.add_argument('--stop', action='store_true',
                        help='Stop streaming (command-line mode)')
    parser.add_argument('--status', action='store_true',
                        help='Check streaming status')

    args = parser.parse_args()

    if args.install_autostart:
        install_autostart()
        return 0

    if args.test_camera:
        config = ConfigManager()
        camera = CameraManager(config)
        device = camera.detect_elgato_camera()
        if device:
            print(f"✅ Elgato Facecam detected: {device}")
            return 0
        else:
            print("❌ Elgato Facecam not detected")
            return 1

    if args.start:
        config = ConfigManager()
        camera = CameraManager(config)
        print("🎥 Starting VirtualCam streaming...")
        if camera.start_streaming():
            print("✅ VirtualCam started successfully!")
            print("📱 Virtual camera available at /dev/video10")
            print("🛑 Use 'python3 virtualcam_app.py --stop' to stop streaming")
            return 0
        else:
            print("❌ Failed to start VirtualCam")
            return 1

    if args.stop:
        import subprocess
        try:
            subprocess.run(['pkill', '-f', 'ffmpeg.*video10'], check=False)
            print("✅ VirtualCam streaming stopped")
            return 0
        except Exception as e:
            print(f"❌ Error stopping VirtualCam: {e}")
            return 1

    if args.status:
        import subprocess
        try:
            result = subprocess.run(['pgrep', '-f', 'ffmpeg.*video10'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ VirtualCam is streaming")
                return 0
            else:
                print("❌ VirtualCam is not streaming")
                return 1
        except Exception as e:
            print(f"❌ Error checking status: {e}")
            return 1

    # Create Qt application first (following Witticism pattern)
    print("DEBUG: Creating QApplication...")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    print("DEBUG: QApplication created successfully")

    # Check if system tray is available (after QApplication creation)
    print("DEBUG: About to check system tray availability...")
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("❌ System tray is not available on this system")
        return 1
    print("DEBUG: System tray is available")

    # Initialize components
    print("DEBUG: About to create VirtualCamApp...")
    virtualcam_app = VirtualCamApp()
    print("DEBUG: VirtualCamApp created")

    # Create system tray
    print("DEBUG: Creating system tray...")
    virtualcam_app.create_system_tray()
    print("DEBUG: System tray created")

    print("DEBUG: About to exec...")
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())
