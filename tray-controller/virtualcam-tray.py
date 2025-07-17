#!/usr/bin/env python3
"""
Elgato VirtualCam Tray Icon Controller

A system tray utility for controlling the elgato-virtualcam.service
with theme-aware icons and service status monitoring.
"""

import sys
import os
import subprocess
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox, QAction
from PyQt5.QtGui import QIcon, QPalette
from PyQt5.QtCore import QTimer


class VirtualCamTray:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        # Asset paths
        self.assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
        
        # Create system tray
        self.tray = QSystemTrayIcon()
        self.create_menu()
        
        # Timer for periodic status updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(5000)  # Update every 5 seconds
        
        # Initial status check
        self.refresh_status()
        self.tray.show()
    
    def get_icon_path(self, status):
        """Get the appropriate icon path based on status and theme"""
        # Detect if we're in dark mode
        palette = self.app.palette()
        is_dark = palette.color(QPalette.Window).lightness() < 128
        
        if status == 'off':
            icon_name = 'camera-off-white.png' if is_dark else 'camera-off-black.png'
        elif status == 'on':
            icon_name = 'camera-on.png'
        elif status == 'unsure':
            icon_name = 'camera-unsure.png'
        else:  # disconnected
            icon_name = 'camera-disconnected.png'
        
        return os.path.join(self.assets_dir, icon_name)
    
    def get_service_status(self):
        """Check the status of the elgato-virtualcam.service"""
        try:
            result = subprocess.run(
                ['systemctl', '--user', 'is-active', 'elgato-virtualcam.service'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip() == 'active':
                return 'on'
            elif result.returncode == 3:  # Service is inactive
                return 'off'
            else:
                return 'unsure'
                
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return 'disconnected'
    
    def start_service(self):
        """Start the elgato-virtualcam.service"""
        try:
            result = subprocess.run(
                ['systemctl', '--user', 'start', 'elgato-virtualcam.service'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                self.show_notification("VirtualCam started successfully")
            else:
                self.show_notification(f"Failed to start VirtualCam: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.show_notification("Timeout starting VirtualCam service")
        except subprocess.SubprocessError as e:
            self.show_notification(f"Error starting VirtualCam: {e}")
        
        self.refresh_status()
    
    def stop_service(self):
        """Stop the elgato-virtualcam.service"""
        try:
            result = subprocess.run(
                ['systemctl', '--user', 'stop', 'elgato-virtualcam.service'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                self.show_notification("VirtualCam stopped successfully")
            else:
                self.show_notification(f"Failed to stop VirtualCam: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.show_notification("Timeout stopping VirtualCam service")
        except subprocess.SubprocessError as e:
            self.show_notification(f"Error stopping VirtualCam: {e}")
        
        self.refresh_status()
    
    def toggle_service(self):
        """Toggle the service on/off based on current status"""
        status = self.get_service_status()
        if status == 'on':
            self.stop_service()
        else:
            self.start_service()
    
    def refresh_status(self):
        """Update the tray icon and tooltip based on current service status"""
        status = self.get_service_status()
        
        # Update icon
        icon_path = self.get_icon_path(status)
        if os.path.exists(icon_path):
            self.tray.setIcon(QIcon(icon_path))
        
        # Update tooltip
        status_messages = {
            'on': 'VirtualCam is ON',
            'off': 'VirtualCam is OFF',
            'unsure': 'VirtualCam status unclear',
            'disconnected': 'VirtualCam service unavailable'
        }
        self.tray.setToolTip(status_messages.get(status, 'VirtualCam status unknown'))
        
        # Update menu
        self.update_menu(status)
    
    def update_menu(self, status):
        """Update menu items based on current status"""
        # Clear and recreate menu
        self.create_menu(status)
    
    def create_menu(self, status=None):
        """Create the context menu"""
        if status is None:
            status = self.get_service_status()
        
        menu = QMenu()
        
        # Main toggle action
        if status == 'on':
            toggle_action = QAction("❌ Stop VirtualCam", menu)
            toggle_action.triggered.connect(self.stop_service)
        else:
            toggle_action = QAction("▶️ Start VirtualCam", menu)
            toggle_action.triggered.connect(self.start_service)
        menu.addAction(toggle_action)
        
        menu.addSeparator()
        
        # Refresh action
        refresh_action = QAction("🔄 Refresh Status", menu)
        refresh_action.triggered.connect(self.refresh_status)
        menu.addAction(refresh_action)
        
        # View logs action (optional)
        logs_action = QAction("📜 View Logs", menu)
        logs_action.triggered.connect(self.view_logs)
        menu.addAction(logs_action)
        
        menu.addSeparator()
        
        # Quit action
        quit_action = QAction("🚪 Quit", menu)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        
        self.tray.setContextMenu(menu)
        
        # Set up left-click action for toggle
        self.tray.activated.connect(self.on_tray_activated)
    
    def on_tray_activated(self, reason):
        """Handle tray icon clicks"""
        if reason == QSystemTrayIcon.Trigger:  # Left click
            self.toggle_service()
    
    def view_logs(self):
        """Show recent service logs"""
        try:
            result = subprocess.run(
                ['journalctl', '--user', '-u', 'elgato-virtualcam.service', '--no-pager', '-n', '20'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                logs = result.stdout or "No logs available"
            else:
                logs = f"Error retrieving logs: {result.stderr}"
                
        except subprocess.SubprocessError as e:
            logs = f"Error accessing logs: {e}"
        
        # Show logs in a message box (simple approach)
        msg = QMessageBox()
        msg.setWindowTitle("VirtualCam Service Logs")
        msg.setText(logs[-1000:])  # Limit to last 1000 chars
        msg.exec_()
    
    def show_notification(self, message):
        """Show a system tray notification"""
        if self.tray.supportsMessages():
            self.tray.showMessage("VirtualCam Controller", message, QSystemTrayIcon.Information, 3000)
    
    def quit_app(self):
        """Quit the application"""
        self.timer.stop()
        self.app.quit()
    
    def run(self):
        """Run the application"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "VirtualCam Tray", 
                               "System tray is not available on this system.")
            sys.exit(1)
        
        return self.app.exec_()


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        print("Elgato VirtualCam Tray Icon Controller")
        print("Usage: python3 virtualcam-tray.py")
        print("\nControls the elgato-virtualcam.service via system tray.")
        print("Left-click: Toggle service on/off")
        print("Right-click: Open context menu")
        return 0
    
    tray_app = VirtualCamTray()
    return tray_app.run()


if __name__ == '__main__':
    sys.exit(main()) 