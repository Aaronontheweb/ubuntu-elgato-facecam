#!/usr/bin/env python3
"""
Basic unit tests for Elgato VirtualCam application.
Tests that don't require hardware or GUI components.
"""

import unittest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import components to test
from virtualcam_app import ConfigManager


class TestConfigManager(unittest.TestCase):
    """Test ConfigManager functionality"""
    
    def setUp(self):
        """Set up test environment with temporary directory"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.original_home = Path.home()
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)
    
    def test_default_config_creation(self):
        """Test that default configuration is created properly"""
        with patch('pathlib.Path.home', return_value=self.test_dir):
            config = ConfigManager()
            
            # Check default values exist
            self.assertEqual(config.get('virtual_device'), '/dev/video10')
            self.assertEqual(config.get('virtual_device_label'), 'VirtualCam')
            self.assertEqual(config.get('ffmpeg_params.framerate'), 30)
            self.assertEqual(config.get('ffmpeg_params.input_format'), 'uyvy422')
            self.assertEqual(config.get('ui.show_notifications'), True)
    
    def test_config_file_persistence(self):
        """Test that configuration is saved and loaded correctly"""
        with patch('pathlib.Path.home', return_value=self.test_dir):
            # Create config and modify a value
            config1 = ConfigManager()
            config1.set('ui.show_notifications', False)
            config1.set('virtual_device', '/dev/video20')
            
            # Create new config instance (should load from file)
            config2 = ConfigManager()
            
            # Check values were persisted
            self.assertEqual(config2.get('ui.show_notifications'), False)
            self.assertEqual(config2.get('virtual_device'), '/dev/video20')
            # Default values should still be there
            self.assertEqual(config2.get('ffmpeg_params.framerate'), 30)
    
    def test_dot_notation_get_set(self):
        """Test dot notation for nested configuration access"""
        with patch('pathlib.Path.home', return_value=self.test_dir):
            config = ConfigManager()
            
            # Test setting nested values
            config.set('ffmpeg_params.video_size', '1920x1080')
            config.set('logging.level', 'DEBUG')
            
            # Test getting nested values
            self.assertEqual(config.get('ffmpeg_params.video_size'), '1920x1080')
            self.assertEqual(config.get('logging.level'), 'DEBUG')
            
            # Test non-existent keys with defaults
            self.assertEqual(config.get('nonexistent.key', 'default'), 'default')
            self.assertIsNone(config.get('nonexistent.key'))
    
    def test_config_merge_with_partial_file(self):
        """Test that partial config files merge with defaults"""
        with patch('pathlib.Path.home', return_value=self.test_dir):
            # Create partial config file manually
            config_dir = self.test_dir / '.config/elgato-virtualcam'
            config_dir.mkdir(parents=True)
            config_file = config_dir / 'config.json'
            
            partial_config = {
                'virtual_device': '/dev/video15',
                'ui': {'show_notifications': False}
            }
            
            with open(config_file, 'w') as f:
                json.dump(partial_config, f)
            
            # Load config
            config = ConfigManager()
            
            # Check that custom values are loaded
            self.assertEqual(config.get('virtual_device'), '/dev/video15')
            self.assertEqual(config.get('ui.show_notifications'), False)
            
            # Check that defaults are still present
            self.assertEqual(config.get('ffmpeg_params.framerate'), 30)
            self.assertEqual(config.get('virtual_device_label'), 'VirtualCam')


class TestBasicImports(unittest.TestCase):
    """Test that basic imports work without hardware dependencies"""
    
    def test_import_main_module(self):
        """Test that main module imports successfully"""
        try:
            import virtualcam_app
            self.assertTrue(hasattr(virtualcam_app, 'main'))
            self.assertTrue(hasattr(virtualcam_app, 'ConfigManager'))
            self.assertTrue(hasattr(virtualcam_app, 'CameraManager'))
        except ImportError as e:
            self.fail(f"Failed to import virtualcam_app: {e}")
    
    def test_pyqt5_availability(self):
        """Test that PyQt5 is available for GUI components"""
        try:
            from PyQt5.QtWidgets import QApplication, QSystemTrayIcon
            from PyQt5.QtCore import QTimer
            from PyQt5.QtGui import QIcon
            self.assertTrue(True)  # If we get here, imports worked
        except ImportError as e:
            self.fail(f"PyQt5 components not available: {e}")


class TestCameraManagerBasics(unittest.TestCase):
    """Test CameraManager methods that don't require hardware"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)
    
    def test_camera_manager_initialization(self):
        """Test that CameraManager can be initialized"""
        with patch('pathlib.Path.home', return_value=self.test_dir):
            from virtualcam_app import CameraManager, ConfigManager
            
            config = ConfigManager()
            camera = CameraManager(config)
            
            self.assertIsNone(camera.ffmpeg_process)
            self.assertIsNone(camera.elgato_device)
            self.assertEqual(camera.config, config)
    
    def test_is_streaming_when_no_process(self):
        """Test is_streaming returns False when no process exists"""
        with patch('pathlib.Path.home', return_value=self.test_dir):
            from virtualcam_app import CameraManager, ConfigManager
            
            config = ConfigManager()
            camera = CameraManager(config)
            
            self.assertFalse(camera.is_streaming())


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions"""
    
    def test_install_autostart_function_exists(self):
        """Test that install_autostart function exists and is callable"""
        from virtualcam_app import install_autostart
        self.assertTrue(callable(install_autostart))
    
    def test_main_function_exists(self):
        """Test that main function exists and is callable"""
        from virtualcam_app import main
        self.assertTrue(callable(main))


if __name__ == '__main__':
    # Run tests
    unittest.main()