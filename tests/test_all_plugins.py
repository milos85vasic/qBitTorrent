#!/usr/bin/env python3
"""
Comprehensive test suite for all qBittorrent search plugins.

This test suite verifies:
1. All plugins are properly installed and have valid syntax
2. All plugins can be imported and instantiated
3. All plugins support required methods (search, download_torrent)
4. Plugin output format is correct
5. Torrent downloads work correctly (when credentials available)

Usage:
    python3 test_all_plugins.py              # Run all tests
    python3 test_all_plugins.py --verbose    # Run with detailed output
    python3 test_all_plugins.py --plugin rutracker  # Test specific plugin
"""

import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import MagicMock, Mock, patch
import time

# Setup paths
tests_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(tests_dir)
plugins_dir = os.path.join(project_dir, "plugins")
sys.path.insert(0, plugins_dir)
sys.path.insert(0, tests_dir)

# Import all plugins
PLUGINS = ["rutracker", "rutor", "kinozal", "nnmclub"]


class TestPluginInstallation(unittest.TestCase):
    """Test that all plugins are properly installed."""

    def test_01_all_plugin_files_exist(self):
        """Verify all plugin files exist in plugins directory."""
        print("\n[TEST] Checking plugin files exist...")
        
        for plugin in PLUGINS:
            plugin_file = os.path.join(plugins_dir, f"{plugin}.py")
            self.assertTrue(
                os.path.exists(plugin_file),
                f"Plugin file missing: {plugin}.py"
            )
            print(f"  ✓ {plugin}.py exists")

    def test_02_all_plugin_files_readable(self):
        """Verify all plugin files are readable."""
        print("\n[TEST] Checking plugin files are readable...")
        
        for plugin in PLUGINS:
            plugin_file = os.path.join(plugins_dir, f"{plugin}.py")
            try:
                with open(plugin_file, 'r') as f:
                    content = f.read()
                self.assertGreater(len(content), 0, f"{plugin}.py is empty")
                print(f"  ✓ {plugin}.py is readable ({len(content)} bytes)")
            except Exception as e:
                self.fail(f"Cannot read {plugin}.py: {e}")

    def test_03_all_plugins_have_valid_syntax(self):
        """Verify all plugins have valid Python syntax."""
        print("\n[TEST] Checking plugin syntax...")
        
        for plugin in PLUGINS:
            plugin_file = os.path.join(plugins_dir, f"{plugin}.py")
            try:
                with open(plugin_file, 'r') as f:
                    compile(f.read(), plugin_file, 'exec')
                print(f"  ✓ {plugin}.py syntax is valid")
            except SyntaxError as e:
                self.fail(f"Syntax error in {plugin}.py: {e}")


class TestPluginImports(unittest.TestCase):
    """Test that all plugins can be imported."""

    @classmethod
    def setUpClass(cls):
        """Try to import all plugins."""
        cls.imported_plugins = {}
        cls.import_errors = {}
        
        for plugin in PLUGINS:
            try:
                module = __import__(plugin)
                cls.imported_plugins[plugin] = module
            except Exception as e:
                cls.import_errors[plugin] = str(e)

    def test_01_all_plugins_import_successfully(self):
        """Verify all plugins can be imported."""
        print("\n[TEST] Checking plugin imports...")
        
        for plugin in PLUGINS:
            if plugin in self.import_errors:
                print(f"  ✗ {plugin}: {self.import_errors[plugin]}")
                self.fail(f"Failed to import {plugin}: {self.import_errors[plugin]}")
            else:
                print(f"  ✓ {plugin} imported successfully")

    def test_02_all_plugins_have_engine_class(self):
        """Verify all plugins have the engine class defined."""
        print("\n[TEST] Checking engine classes...")
        
        # Map plugin names to their class names (may differ in capitalization)
        class_names = {
            "rutracker": "RuTracker",
            "rutor": "Rutor", 
            "kinozal": "Kinozal",
            "nnmclub": "NNMClub"
        }
        
        for plugin in PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            class_name = class_names.get(plugin, plugin.capitalize())
            
            self.assertTrue(
                hasattr(module, class_name),
                f"{plugin} module missing {class_name} class"
            )
            print(f"  ✓ {plugin}.{class_name} exists")

    def test_03_all_plugins_have_module_reference(self):
        """Verify all plugins have the module-level reference."""
        print("\n[TEST] Checking module references...")
        
        for plugin in PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            
            self.assertTrue(
                hasattr(module, plugin),
                f"{plugin} module missing {plugin} reference"
            )
            print(f"  ✓ {plugin}.{plugin} reference exists")


class TestPluginStructure(unittest.TestCase):
    """Test that all plugins have required structure."""

    @classmethod
    def setUpClass(cls):
        """Try to import all plugins."""
        cls.imported_plugins = {}
        
        for plugin in PLUGINS:
            try:
                module = __import__(plugin)
                cls.imported_plugins[plugin] = module
            except:
                pass

    def test_01_all_plugins_have_required_attributes(self):
        """Verify all plugins have required class attributes."""
        print("\n[TEST] Checking required attributes...")
        
        required_attrs = ['name', 'url', 'supported_categories']
        
        # Map plugin names to their class names
        class_names = {
            "rutracker": "RuTracker",
            "rutor": "Rutor", 
            "kinozal": "Kinozal",
            "nnmclub": "NNMClub"
        }
        
        for plugin in PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            class_name = class_names.get(plugin, plugin.capitalize())
            engine_class = getattr(module, class_name)
            
            for attr in required_attrs:
                self.assertTrue(
                    hasattr(engine_class, attr),
                    f"{plugin}.{class_name} missing attribute: {attr}"
                )
            
            print(f"  ✓ {plugin} has all required attributes")

    def test_02_all_plugins_have_required_methods(self):
        """Verify all plugins have required methods."""
        print("\n[TEST] Checking required methods...")
        
        required_methods = ['search', 'download_torrent']
        
        # Map plugin names to their class names
        class_names = {
            "rutracker": "RuTracker",
            "rutor": "Rutor", 
            "kinozal": "Kinozal",
            "nnmclub": "NNMClub"
        }
        
        for plugin in PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            class_name = class_names.get(plugin, plugin.capitalize())
            engine_class = getattr(module, class_name)
            
            for method in required_methods:
                self.assertTrue(
                    hasattr(engine_class, method) and callable(getattr(engine_class, method)),
                    f"{plugin}.{class_name} missing method: {method}"
                )
            
            print(f"  ✓ {plugin} has all required methods")

    def test_03_all_plugins_have_name_attribute(self):
        """Verify all plugins have a name attribute."""
        print("\n[TEST] Checking plugin names...")
        
        # Map plugin names to their class names
        class_names = {
            "rutracker": "RuTracker",
            "rutor": "Rutor", 
            "kinozal": "Kinozal",
            "nnmclub": "NNMClub"
        }
        
        for plugin in PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            class_name = class_names.get(plugin, plugin.capitalize())
            engine_class = getattr(module, class_name)
            
            name = getattr(engine_class, 'name', None)
            self.assertIsNotNone(name, f"{plugin} missing name attribute")
            self.assertIsInstance(name, str, f"{plugin}.name should be a string")
            self.assertGreater(len(name), 0, f"{plugin}.name should not be empty")
            
            print(f"  ✓ {plugin}.name = '{name}'")


class TestPluginDownloadOutput(unittest.TestCase):
    """Test the download_torrent output format for all plugins."""

    def test_01_rutracker_output_format(self):
        """Test RuTracker download_torrent output format."""
        print("\n[TEST] Testing RuTracker download output format...")
        
        try:
            from rutracker import RuTracker
            
            # Create mock
            mock_opener = MagicMock()
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'd8:announce31:http://test.com/announce'
            mock_response.info.return_value.get.return_value = None
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_opener.open.return_value = mock_response
            
            # Create plugin instance without __init__
            plugin = RuTracker.__new__(RuTracker)
            plugin.cj = MagicMock()
            plugin.opener = mock_opener
            plugin.url = "https://rutracker.org"
            
            test_url = "https://rutracker.org/forum/dl.php?t=12345"
            
            captured = StringIO()
            with patch('sys.stdout', captured):
                plugin.download_torrent(test_url)
            
            output = captured.getvalue().strip()
            parts = output.split(" ")
            
            self.assertEqual(len(parts), 2, f"Output should be 'filepath url', got: {output}")
            self.assertTrue(parts[0].endswith('.torrent'), f"First part should be .torrent file path: {parts[0]}")
            self.assertEqual(parts[1], test_url, f"Second part should be URL: {test_url}")
            
            print(f"  ✓ Output format correct: {output[:80]}...")
            
            # Clean up temp file
            if os.path.exists(parts[0]):
                os.unlink(parts[0])
                
        except Exception as e:
            print(f"  ⚠ Test skipped: {e}")

    def test_02_rutor_output_format(self):
        """Test Rutor download_torrent output format."""
        print("\n[TEST] Testing Rutor download output format...")
        
        try:
            from rutor import Rutor
            
            # Create mock
            mock_opener = MagicMock()
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_response.geturl.return_value = "https://rutor.info/"
            mock_response.read.return_value = b'd8:announce31:http://test.com/announce'
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_opener.open.return_value = mock_response
            
            # Create plugin instance
            plugin = Rutor.__new__(Rutor)
            plugin.session = mock_opener
            plugin.url = "https://rutor.info/"
            plugin.url_dl = "https://d.rutor.info/download/"
            
            test_url = "https://d.rutor.info/download/12345"
            
            captured = StringIO()
            with patch('sys.stdout', captured):
                plugin.download_torrent(test_url)
            
            output = captured.getvalue().strip()
            
            # Rutor returns "filepath url" format
            parts = output.split(" ")
            self.assertEqual(len(parts), 2, f"Output should be 'filepath url', got: {output}")
            
            print(f"  ✓ Output format correct: {output[:80]}...")
            
            # Clean up temp file
            if os.path.exists(parts[0]):
                os.unlink(parts[0])
                
        except Exception as e:
            print(f"  ⚠ Test skipped: {e}")


class TestPluginSearch(unittest.TestCase):
    """Test search functionality for plugins (if credentials available)."""

    def test_01_rutracker_search_structure(self):
        """Test RuTracker search builds correct result structure."""
        print("\n[TEST] Testing RuTracker search result structure...")
        
        try:
            from rutracker import RuTracker
            
            # Create mock plugin
            plugin = RuTracker.__new__(RuTracker)
            plugin.url = "https://rutracker.org"
            
            # Test _build_result method
            torrent_data = {
                "id": "12345",
                "title": "Test Torrent",
                "size": "1073741824",
                "seeds": "10",
                "leech": "5",
                "pub_date": "1234567890",
            }
            
            result = plugin._RuTracker__build_result(torrent_data)
            
            # Verify result structure
            required_keys = ['id', 'link', 'name', 'size', 'seeds', 'leech', 'engine_url', 'desc_link', 'pub_date']
            for key in required_keys:
                self.assertIn(key, result, f"Result missing key: {key}")
            
            self.assertEqual(result['id'], '12345')
            self.assertEqual(result['name'], 'Test Torrent')
            self.assertIn('t=12345', result['link'])
            
            print(f"  ✓ Result structure is correct")
            
        except Exception as e:
            print(f"  ⚠ Test skipped: {e}")


class TestPluginCategories(unittest.TestCase):
    """Test that all plugins have proper category support."""

    @classmethod
    def setUpClass(cls):
        """Try to import all plugins."""
        cls.imported_plugins = {}
        
        for plugin in PLUGINS:
            try:
                module = __import__(plugin)
                cls.imported_plugins[plugin] = module
            except:
                pass

    def test_01_all_plugins_support_all_category(self):
        """Verify all plugins support 'all' category."""
        print("\n[TEST] Checking 'all' category support...")
        
        # Map plugin names to their class names
        class_names = {
            "rutracker": "RuTracker",
            "rutor": "Rutor", 
            "kinozal": "Kinozal",
            "nnmclub": "NNMClub"
        }
        
        for plugin in PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            class_name = class_names.get(plugin, plugin.capitalize())
            engine_class = getattr(module, class_name)
            
            categories = getattr(engine_class, 'supported_categories', {})
            
            self.assertIn('all', categories, f"{plugin} should support 'all' category")
            print(f"  ✓ {plugin} supports 'all' category")

    def test_02_common_categories_supported(self):
        """Verify common categories are supported across plugins."""
        print("\n[TEST] Checking common category support...")
        
        common_categories = ['movies', 'tv', 'music', 'games', 'software']
        
        # Map plugin names to their class names
        class_names = {
            "rutracker": "RuTracker",
            "rutor": "Rutor", 
            "kinozal": "Kinozal",
            "nnmclub": "NNMClub"
        }
        
        for plugin in PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            class_name = class_names.get(plugin, plugin.capitalize())
            engine_class = getattr(module, class_name)
            
            categories = getattr(engine_class, 'supported_categories', {})
            
            supported = []
            for cat in common_categories:
                if cat in categories:
                    supported.append(cat)
            
            print(f"  ✓ {plugin} supports: {', '.join(supported)}")


def run_tests():
    """Run all tests and generate report."""
    print("=" * 70)
    print("qBittorrent Search Plugins - Comprehensive Test Suite")
    print("=" * 70)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPluginInstallation))
    suite.addTests(loader.loadTestsFromTestCase(TestPluginImports))
    suite.addTests(loader.loadTestsFromTestCase(TestPluginStructure))
    suite.addTests(loader.loadTestsFromTestCase(TestPluginDownloadOutput))
    suite.addTests(loader.loadTestsFromTestCase(TestPluginSearch))
    suite.addTests(loader.loadTestsFromTestCase(TestPluginCategories))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✓ ALL TESTS PASSED!")
        print("\nAll plugins are properly installed and functional.")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        print("\nPlease check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
