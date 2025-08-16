#!/usr/bin/env python3
"""
Elgato VirtualCam Desktop Application

A unified desktop application for managing Elgato Facecam virtual camera streaming.
Replaces the systemd service approach with a single Python application.

Based on the Witticism project model for robust desktop application architecture.
"""

import sys
import os
import subprocess
import signal
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any
from PyQt5.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QMessageBox, 
                             QAction, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QComboBox, QCheckBox)
from PyQt5.QtGui import QIcon, QPalette, QPixmap, QPainter, QColor, QFont
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt


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
                with open(self.config_file, 'r') as f:
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
    
    def is_streaming(self) -> bool:
        """Check if ffmpeg process is running"""
        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            return True
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
            # Start ffmpeg process
            log_file = self.config.get('logging.file', '/tmp/elgato-virtualcam.log')
            with open(log_file.replace('.log', '.err.log'), 'a') as stderr_file:
                self.ffmpeg_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=stderr_file,
                    preexec_fn=os.setsid  # Create new process group
                )
            
            # Give it a moment to start
            time.sleep(1)
            
            if self.ffmpeg_process.poll() is None:
                logging.info(f"Streaming started: {self.elgato_device} → {virtual_dev}")
                return True
            else:
                logging.error("FFmpeg process failed to start")
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
        self.app = app
        self.config = app.config
        self.camera = app.camera
        
        # Create tray icon
        self.tray = QSystemTrayIcon()
        self.tray.activated.connect(self.on_tray_activated)
        
        # Create menu
        self.create_menu()
        
        # Timer for status updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(self.config.get('ui.update_interval', 5000))
        
        # Initial status update
        self.update_status()
        self.tray.show()
    
    def create_dynamic_icon(self, status: str) -> QIcon:
        """Create status-based tray icon"""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Status-based colors
        colors = {
            'on': QColor(76, 175, 80),      # Green
            'off': QColor(158, 158, 158),   # Gray
            'error': QColor(244, 67, 54),   # Red
            'starting': QColor(255, 193, 7) # Amber
        }
        
        color = colors.get(status, colors['off'])
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(8, 8, 48, 48)
        
        # Add camera icon text
        painter.setPen(Qt.white)
        font = QFont("Arial", 16, QFont.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "📹")
        
        painter.end()
        return QIcon(pixmap)
    
    def create_menu(self):
        """Create context menu"""
        self.menu = QMenu()
        
        # Toggle action
        self.toggle_action = QAction("Start VirtualCam", self.menu)
        self.toggle_action.triggered.connect(self.toggle_streaming)
        self.menu.addAction(self.toggle_action)
        
        self.menu.addSeparator()
        
        # Settings
        settings_action = QAction("Settings", self.menu)
        settings_action.triggered.connect(self.show_settings)
        self.menu.addAction(settings_action)
        
        # Status
        status_action = QAction("Status & Logs", self.menu)
        status_action.triggered.connect(self.show_status)
        self.menu.addAction(status_action)
        
        # Refresh
        refresh_action = QAction("Refresh", self.menu)
        refresh_action.triggered.connect(self.update_status)
        self.menu.addAction(refresh_action)
        
        self.menu.addSeparator()
        
        # Quit
        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)
        
        self.tray.setContextMenu(self.menu)
    
    def get_status(self) -> str:
        """Get current streaming status"""
        if self.camera.is_streaming():
            return 'on'
        elif self.camera.detect_elgato_camera():
            return 'off'
        else:
            return 'error'
    
    def update_status(self):
        """Update tray icon and tooltip"""
        status = self.get_status()
        
        # Update icon
        self.tray.setIcon(self.create_dynamic_icon(status))
        
        # Update tooltip
        status_messages = {
            'on': 'VirtualCam is streaming',
            'off': 'VirtualCam is ready',
            'error': 'Camera not detected',
            'starting': 'VirtualCam is starting...'
        }
        self.tray.setToolTip(status_messages.get(status, 'VirtualCam status unknown'))
        
        # Update menu
        if status == 'on':
            self.toggle_action.setText("Stop VirtualCam")
        else:
            self.toggle_action.setText("Start VirtualCam")
    
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
    
    def on_tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.Trigger:  # Left click
            self.toggle_streaming()
    
    def show_settings(self):
        """Show settings dialog"""
        # TODO: Implement settings dialog
        QMessageBox.information(None, "Settings", "Settings dialog coming soon!")
    
    def show_status(self):
        """Show status and logs dialog"""
        # TODO: Implement status dialog
        QMessageBox.information(None, "Status", "Status dialog coming soon!")


class VirtualCamApp(QApplication):
    """Main application class"""
    
    def __init__(self):
        super().__init__(sys.argv)
        self.setQuitOnLastWindowClosed(False)
        
        # Setup logging
        self.setup_logging()
        
        # Initialize components
        self.config = ConfigManager()
        self.camera = CameraManager(self.config)
        self.tray = SystemTray(self)
        
        # Handle signals for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logging.info("Elgato VirtualCam application started")
    
    def setup_logging(self):
        """Configure logging"""
        log_level = getattr(logging, 'INFO')
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
        if hasattr(self.tray, 'timer'):
            self.tray.timer.stop()
        
        # Quit application
        super().quit()


def install_autostart():
    """Install desktop autostart entry"""
    autostart_dir = Path.home() / '.config/autostart'
    autostart_dir.mkdir(parents=True, exist_ok=True)
    
    desktop_entry = f"""[Desktop Entry]
Type=Application
Name=Elgato VirtualCam
Exec={sys.executable} {os.path.abspath(__file__)}
StartupNotify=false
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
Comment=Elgato Facecam Virtual Camera Controller
"""
    
    autostart_file = autostart_dir / 'elgato-virtualcam.desktop'
    autostart_file.write_text(desktop_entry)
    print(f"✅ Autostart entry installed: {autostart_file}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Elgato VirtualCam Desktop Application')
    parser.add_argument('--install-autostart', action='store_true',
                        help='Install desktop autostart entry')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--test-camera', action='store_true',
                        help='Test camera detection and exit')
    
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
    
    # Check if system tray is available
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("❌ System tray is not available on this system")
        return 1
    
    # Create and run application
    app = VirtualCamApp()
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())