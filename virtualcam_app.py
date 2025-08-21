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
    QDialog,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
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


class StatusDialog(QDialog):
    """Rich status dialog showing system information and troubleshooting tips"""
    
    def __init__(self, config: ConfigManager, camera: 'CameraManager', parent=None):
        super().__init__(parent)
        self.config = config
        self.camera = camera
        self.setWindowTitle("VirtualCam Status")
        self.setFixedSize(450, 600)
        self.setModal(False)  # Allow interaction with main app
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("🎥 Elgato VirtualCam Status")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px; background-color: #2d3142; color: white;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarNever)
        
        # Content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(15)
        
        # Status sections
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        content_layout.addWidget(self.status_label)
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Button layout
        button_layout = QVBoxLayout()
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Status")
        refresh_btn.clicked.connect(self.refresh_status)
        button_layout.addWidget(refresh_btn)
        
        # Action buttons
        self.action_buttons = []
        button_layout.addWidget(QLabel())  # Spacer
        
        layout.addLayout(button_layout)
        self.button_layout = button_layout
        
        # Initial refresh
        self.refresh_status()
    
    def create_section(self, title: str, items: list, status_color: str = "#666666") -> str:
        """Create a formatted section for the status display"""
        section = f'<div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid {status_color}; background-color: #f8f9fa;">'
        section += f'<h3 style="margin: 0 0 8px 0; color: {status_color};">{title}</h3>'
        
        for item in items:
            if item.startswith('✅'):
                section += f'<div style="color: #28a745; margin: 4px 0;">✅ {item[2:].strip()}</div>'
            elif item.startswith('❌'):
                section += f'<div style="color: #dc3545; margin: 4px 0;">❌ {item[2:].strip()}</div>'
            elif item.startswith('⚠️'):
                section += f'<div style="color: #ffc107; margin: 4px 0;">⚠️ {item[2:].strip()}</div>'
            else:
                section += f'<div style="color: #333; margin: 4px 0;">• {item}</div>'
        
        section += '</div>'
        return section
    
    def get_system_diagnostics(self):
        """Get comprehensive system diagnostics"""
        diagnostics = {
            'hardware': [],
            'virtual_device': [],
            'streaming': [],
            'suggestions': []
        }
        
        # Hardware checks
        try:
            result = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=5)
            if 'Elgato' in result.stdout:
                # Parse for Elgato devices
                for line in result.stdout.split('\n'):
                    if 'Elgato' in line:
                        diagnostics['hardware'].append(f"✅ Found: {line.split('ID ')[1] if 'ID ' in line else 'Elgato device'}")
            else:
                diagnostics['hardware'].append("❌ No Elgato devices found in USB")
                diagnostics['suggestions'].append("🔌 Check USB connection - try unplugging and reconnecting the camera")
                diagnostics['suggestions'].append("🔄 Try a different USB port (preferably USB 3.0)")
                diagnostics['suggestions'].append("💡 Ensure the camera is powered on")
        except Exception as e:
            diagnostics['hardware'].append(f"❌ Error checking USB devices: {e}")
        
        # Virtual device checks
        virtual_dev = self.config.get('virtual_device', '/dev/video10')
        if os.path.exists(virtual_dev):
            diagnostics['virtual_device'].append(f"✅ Virtual device exists: {virtual_dev}")
        else:
            diagnostics['virtual_device'].append(f"❌ Virtual device not found: {virtual_dev}")
            diagnostics['suggestions'].append("🔧 Click 'Reset Virtual Device' below to reload kernel module")
        
        # v4l2loopback module check
        try:
            result = subprocess.run(['lsmod'], capture_output=True, text=True, timeout=5)
            if 'v4l2loopback' in result.stdout:
                diagnostics['virtual_device'].append("✅ v4l2loopback kernel module loaded")
            else:
                diagnostics['virtual_device'].append("❌ v4l2loopback kernel module not loaded")
                diagnostics['suggestions'].append("🔧 Install v4l2loopback: sudo apt install v4l2loopback-dkms")
        except Exception as e:
            diagnostics['virtual_device'].append(f"❌ Error checking kernel modules: {e}")
        
        # Camera detection
        camera_device = self.camera.detect_elgato_camera()
        if camera_device:
            diagnostics['hardware'].append(f"✅ Camera detected at {camera_device}")
        else:
            diagnostics['hardware'].append("❌ Elgato Facecam not detected by v4l2")
            if not diagnostics['suggestions']:  # Only add if no USB suggestions
                diagnostics['suggestions'].append("🔍 Camera may be in use by another application")
                diagnostics['suggestions'].append("📱 Try closing other video apps (Zoom, OBS, etc.)")
        
        # Streaming status
        if self.camera.is_streaming():
            diagnostics['streaming'].append("✅ FFmpeg streaming process active")
            diagnostics['streaming'].append(f"✅ Streaming to {virtual_dev}")
        else:
            diagnostics['streaming'].append("❌ No active streaming")
            if camera_device and os.path.exists(virtual_dev):
                diagnostics['suggestions'].append("▶️ Ready to start streaming - click the tray icon")
        
        return diagnostics
    
    def refresh_status(self):
        """Refresh the status display"""
        diagnostics = self.get_system_diagnostics()
        
        # Build HTML content
        html_content = '<div style="font-family: Arial, sans-serif; font-size: 13px;">'
        
        # Overall status
        if diagnostics['hardware'] and any('✅' in item for item in diagnostics['hardware']):
            if self.camera.is_streaming():
                overall_status = "🟢 Streaming Active"
                status_color = "#28a745"
            elif any('✅ Camera detected' in item for item in diagnostics['hardware']):
                overall_status = "🟡 Ready to Stream"
                status_color = "#ffc107"
            else:
                overall_status = "🔴 Camera Issues"
                status_color = "#dc3545"
        else:
            overall_status = "🔴 Hardware Not Detected"
            status_color = "#dc3545"
        
        html_content += self.create_section(f"Status: {overall_status}", [], status_color)
        
        # Hardware section
        if diagnostics['hardware']:
            html_content += self.create_section("Hardware", diagnostics['hardware'], "#007bff")
        
        # Virtual device section
        if diagnostics['virtual_device']:
            html_content += self.create_section("Virtual Camera", diagnostics['virtual_device'], "#6610f2")
        
        # Streaming section
        if diagnostics['streaming']:
            html_content += self.create_section("Streaming", diagnostics['streaming'], "#20c997")
        
        # Suggestions section
        if diagnostics['suggestions']:
            html_content += self.create_section("💡 Suggestions", diagnostics['suggestions'], "#fd7e14")
        
        html_content += '</div>'
        
        self.status_label.setText(html_content)
        
        # Update action buttons
        self.update_action_buttons(diagnostics)
    
    def update_action_buttons(self, diagnostics):
        """Update action buttons based on current status"""
        # Clear existing action buttons
        for btn in self.action_buttons:
            btn.setParent(None)
        self.action_buttons.clear()
        
        # Add relevant action buttons
        if not any('✅ Virtual device exists' in item for item in diagnostics['virtual_device']):
            btn = QPushButton("🔧 Reset Virtual Device")
            btn.clicked.connect(self.reset_virtual_device)
            btn.setStyleSheet("background-color: #007bff; color: white; padding: 8px; border: none; border-radius: 4px;")
            self.button_layout.insertWidget(-1, btn)
            self.action_buttons.append(btn)
        
        if self.camera.is_streaming():
            btn = QPushButton("⏹️ Stop Streaming")
            btn.clicked.connect(self.stop_streaming)
            btn.setStyleSheet("background-color: #dc3545; color: white; padding: 8px; border: none; border-radius: 4px;")
            self.button_layout.insertWidget(-1, btn)
            self.action_buttons.append(btn)
        elif any('✅' in item for item in diagnostics['hardware']) and any('✅ Virtual device exists' in item for item in diagnostics['virtual_device']):
            btn = QPushButton("▶️ Start Streaming")
            btn.clicked.connect(self.start_streaming)
            btn.setStyleSheet("background-color: #28a745; color: white; padding: 8px; border: none; border-radius: 4px;")
            self.button_layout.insertWidget(-1, btn)
            self.action_buttons.append(btn)
    
    def reset_virtual_device(self):
        """Reset virtual device"""
        success = self.camera.reset_virtual_device()
        if success:
            self.refresh_status()
        
    def start_streaming(self):
        """Start streaming"""
        success = self.camera.start_streaming()
        self.refresh_status()
        
    def stop_streaming(self):
        """Stop streaming"""
        success = self.camera.stop_streaming()
        self.refresh_status()


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
        
        # Status dialog
        self.status_dialog = None

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

        # Show Status (rich interface)
        status_action = QAction("📊 Show Status", self.menu)
        status_action.triggered.connect(self.show_status_dialog)
        self.menu.addAction(status_action)
        
        # Diagnostics (simple logging)
        diagnostics_action = QAction("🔍 Run Diagnostics", self.menu)
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
    
    def show_status_dialog(self):
        """Show rich status dialog"""
        if self.status_dialog is None:
            self.status_dialog = StatusDialog(self.config, self.camera)
        
        # Refresh and show
        self.status_dialog.refresh_status()
        self.status_dialog.show()
        self.status_dialog.raise_()
        self.status_dialog.activateWindow()

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
