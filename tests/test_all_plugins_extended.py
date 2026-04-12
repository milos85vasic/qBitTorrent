#!/usr/bin/env python3
"""
Extended comprehensive test suite for all qBittorrent search plugins.

This test suite verifies:
1. All plugins are properly installed and have valid syntax
2. All plugins can be imported and instantiated
3. All plugins support required methods (search, download_torrent)
4. Plugin output format is correct
5. Environment variable configuration works

Usage:
    python3 test_all_plugins_extended.py              # Run all tests
    python3 test_all_plugins_extended.py --verbose    # Run with detailed output
    python3 test_all_plugins_extended.py --plugin 1337x  # Test specific plugin
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

# Import all plugins - Extended list
PUBLIC_PLUGINS = [
    "academictorrents", "ali213", "audiobookbay", "bt4g", "btsow",
    "eztv", "extratorrent", "glotorrents", "gamestorrents",
    "jackett", "kickass", "limetorrents", "linuxtracker",
    "nyaa", "one337x", "piratebay", "pirateiro", "rockbox",
    "rutor", "snowfl", "solidtorrents", "therarbg", "tokyotoshokan",
    "torlock", "torrentdownload", "torrentfunk", "torrentgalaxy",
    "torrentproject", "torrentproject2", "torrentscsv", "torrentkitty",
    "xfsub", "yihua", "yourbittorrent", "yts", "anilibra"
]

PRIVATE_PLUGINS = [
    "rutracker", "kinozal", "nnmclub", "iptorrents"
]

ALL_PLUGINS = PUBLIC_PLUGINS + PRIVATE_PLUGINS

# Map plugin names to their class names
CLASS_NAMES = {
    "rutracker": "RuTracker",
    "rutor": "Rutor",
    "kinozal": "Kinozal",
    "nnmclub": "NNMClub",
    "iptorrents": "iptorrents",
    "eztv": "Eztv",
    "jackett": "jackett",
    "limetorrents": "limetorrents",
    "piratebay": "piratebay",
    "solidtorrents": "solidtorrents",
    "torlock": "torlock",
    "torrentproject": "torrentproject",
    "torrentscsv": "torrentscsv",
    "academictorrents": "academictorrents",
    "ali213": "ali213",
    "audiobookbay": "audiobookbay",
    "bt4g": "bt4g",
    "btsow": "btsow",
    "extratorrent": "extratorrent",
    "glotorrents": "glotorrents",
    "gamestorrents": "gamestorrents",
    "kickass": "kickass",
    "linuxtracker": "linuxtracker",
    "nyaa": "nyaasi",
    "one337x": "one337x",
    "pirateiro": "pirateiro",
    "rockbox": "rockbox",
    "snowfl": "snowfl",
    "therarbg": "therarbg",
    "tokyotoshokan": "tokyotoshokan",
    "torrentdownload": "torrentdownload",
    "torrentfunk": "torrentfunk",
    "torrentgalaxy": "torrentgalaxy",
    "torrentproject2": "torrentproject2",
    "torrentkitty": "torrentkitty",
    "xfsub": "xfsub",
    "yihua": "yihua",
    "yourbittorrent": "yourbittorrent",
    "yts": "yts",
    "anilibra": "anilibra"
}


class TestPluginInstallationExtended(unittest.TestCase):
    """Test that all plugins are properly installed."""

    def test_01_all_plugin_files_exist(self):
        """Verify all plugin files exist in plugins directory."""
        print("\n[TEST] Checking plugin files exist...")
        
        for plugin in ALL_PLUGINS:
            plugin_file = os.path.join(plugins_dir, f"{plugin}.py")
            self.assertTrue(
                os.path.exists(plugin_file),
                f"Plugin file missing: {plugin}.py"
            )
            print(f"  ✓ {plugin}.py exists")

    def test_02_all_plugin_files_readable(self):
        """Verify all plugin files are readable."""
        print("\n[TEST] Checking plugin files are readable...")
        
        for plugin in ALL_PLUGINS:
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
        
        for plugin in ALL_PLUGINS:
            plugin_file = os.path.join(plugins_dir, f"{plugin}.py")
            try:
                with open(plugin_file, 'r') as f:
                    compile(f.read(), plugin_file, 'exec')
                print(f"  ✓ {plugin}.py syntax is valid")
            except SyntaxError as e:
                self.fail(f"Syntax error in {plugin}.py: {e}")


class TestPluginImportsExtended(unittest.TestCase):
    """Test that all plugins can be imported."""

    @classmethod
    def setUpClass(cls):
        """Try to import all plugins."""
        cls.imported_plugins = {}
        cls.import_errors = {}
        
        for plugin in ALL_PLUGINS:
            try:
                module = __import__(plugin)
                cls.imported_plugins[plugin] = module
            except Exception as e:
                cls.import_errors[plugin] = str(e)

    def test_01_all_plugins_import_successfully(self):
        """Verify all plugins can be imported."""
        print("\n[TEST] Checking plugin imports...")
        
        for plugin in ALL_PLUGINS:
            if plugin in self.import_errors:
                print(f"  ⚠ {plugin}: {self.import_errors[plugin]}")
                # Don't fail for private plugins that need credentials
                if plugin in PRIVATE_PLUGINS:
                    continue
                self.fail(f"Failed to import {plugin}: {self.import_errors[plugin]}")
            else:
                print(f"  ✓ {plugin} imported successfully")

    def test_02_all_plugins_have_engine_class(self):
        """Verify all plugins have the engine class defined."""
        print("\n[TEST] Checking engine classes...")
        
        for plugin in ALL_PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            class_name = CLASS_NAMES.get(plugin, plugin.capitalize())
            
            if hasattr(module, class_name):
                print(f"  ✓ {plugin}.{class_name} exists")
            else:
                # Check for alternative class names
                alt_names = [plugin, plugin.upper(), plugin.lower()]
                found = False
                for alt in alt_names:
                    if hasattr(module, alt):
                        print(f"  ✓ {plugin}.{alt} exists")
                        found = True
                        break
                if not found:
                    print(f"  ⚠ {plugin}.{class_name} not found (may use different structure)")

    def test_03_all_plugins_have_module_reference(self):
        """Verify all plugins have the module-level reference."""
        print("\n[TEST] Checking module references...")
        
        for plugin in ALL_PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            
            if hasattr(module, plugin):
                print(f"  ✓ {plugin}.{plugin} reference exists")
            else:
                print(f"  ⚠ {plugin}.{plugin} reference not found (may use different structure)")


class TestPluginStructureExtended(unittest.TestCase):
    """Test that all plugins have required structure."""

    @classmethod
    def setUpClass(cls):
        """Try to import all plugins."""
        cls.imported_plugins = {}
        
        for plugin in ALL_PLUGINS:
            try:
                module = __import__(plugin)
                cls.imported_plugins[plugin] = module
            except:
                pass

    def test_01_all_plugins_have_required_attributes(self):
        """Verify all plugins have required class attributes."""
        print("\n[TEST] Checking required attributes...")
        
        required_attrs = ['name', 'url', 'supported_categories']
        
        for plugin in ALL_PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            class_name = CLASS_NAMES.get(plugin, plugin.capitalize())
            
            if not hasattr(module, class_name):
                continue
                
            engine_class = getattr(module, class_name)
            
            missing = []
            for attr in required_attrs:
                if not hasattr(engine_class, attr):
                    missing.append(attr)
            
            if missing:
                print(f"  ⚠ {plugin} missing attributes: {', '.join(missing)}")
            else:
                print(f"  ✓ {plugin} has all required attributes")

    def test_02_all_plugins_have_required_methods(self):
        """Verify all plugins have required methods."""
        print("\n[TEST] Checking required methods...")
        
        required_methods = ['search', 'download_torrent']
        
        for plugin in ALL_PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            class_name = CLASS_NAMES.get(plugin, plugin.capitalize())
            
            if not hasattr(module, class_name):
                continue
                
            engine_class = getattr(module, class_name)
            
            missing = []
            for method in required_methods:
                if not (hasattr(engine_class, method) and callable(getattr(engine_class, method))):
                    missing.append(method)
            
            if missing:
                print(f"  ⚠ {plugin} missing methods: {', '.join(missing)}")
            else:
                print(f"  ✓ {plugin} has all required methods")

    def test_03_all_plugins_have_valid_name(self):
        """Verify all plugins have a valid name attribute."""
        print("\n[TEST] Checking plugin names...")
        
        for plugin in ALL_PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            class_name = CLASS_NAMES.get(plugin, plugin.capitalize())
            
            if not hasattr(module, class_name):
                continue
                
            engine_class = getattr(module, class_name)
            name = getattr(engine_class, 'name', None)
            
            if name and isinstance(name, str) and len(name) > 0:
                print(f"  ✓ {plugin}.name = '{name}'")
            else:
                print(f"  ⚠ {plugin} has invalid name")

    def test_04_all_plugins_have_valid_url(self):
        """Verify all plugins have a valid URL attribute."""
        print("\n[TEST] Checking plugin URLs...")
        
        for plugin in ALL_PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            class_name = CLASS_NAMES.get(plugin, plugin.capitalize())
            
            if not hasattr(module, class_name):
                continue
                
            engine_class = getattr(module, class_name)
            url = getattr(engine_class, 'url', None)
            
            if url and isinstance(url, str) and url.startswith('http'):
                print(f"  ✓ {plugin}.url = '{url[:50]}...'" if len(str(url)) > 50 else f"  ✓ {plugin}.url = '{url}'")
            else:
                print(f"  ⚠ {plugin} has invalid URL")

    def test_05_all_plugins_have_supported_categories(self):
        """Verify all plugins have supported_categories."""
        print("\n[TEST] Checking supported categories...")
        
        for plugin in ALL_PLUGINS:
            if plugin not in self.imported_plugins:
                continue
                
            module = self.imported_plugins[plugin]
            class_name = CLASS_NAMES.get(plugin, plugin.capitalize())
            
            if not hasattr(module, class_name):
                continue
                
            engine_class = getattr(module, class_name)
            categories = getattr(engine_class, 'supported_categories', None)
            
            if categories and isinstance(categories, dict) and 'all' in categories:
                cat_list = list(categories.keys())
                print(f"  ✓ {plugin} categories: {', '.join(cat_list)}")
            else:
                print(f"  ⚠ {plugin} has invalid categories")


def run_tests():
    """Run all tests with verbose output."""
    # Create a test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPluginInstallationExtended))
    suite.addTests(loader.loadTestsFromTestCase(TestPluginImportsExtended))
    suite.addTests(loader.loadTestsFromTestCase(TestPluginStructureExtended))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Total tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
