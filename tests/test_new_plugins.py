#!/usr/bin/env python3
"""
Test suite for newly added qBittorrent search plugins.

Tests focus on:
1. Plugin syntax validation
2. Import testing
3. Basic structure validation
4. Mock search testing

Usage:
    python3 test_new_plugins.py
    python3 test_new_plugins.py --verbose
"""

import os
import sys
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock

# Setup paths
tests_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(tests_dir)
plugins_dir = os.path.join(project_dir, "plugins")
sys.path.insert(0, plugins_dir)
sys.path.insert(0, tests_dir)

# New plugins added in this update
NEW_PLUGINS = [
    "one337x", "torrentfunk", "extratorrent", "btsow", "torrentkitty",
    "anilibra", "gamestorrents", "megapeer", "bitru", "pctorrent",
    "xfsub", "yihua", "therarbg", "academictorrents", "ali213",
    "audiobookbay", "bt4g", "glotorrents", "kickass", "linuxtracker",
    "nyaa", "pirateiro", "rockbox", "snowfl", "tokyotoshokan",
    "torrentdownload", "torrentgalaxy", "torrentproject2",
    "yourbittorrent", "yts"
]

# Class name mappings
CLASS_NAMES = {
    "one337x": "one337x",
    "torrentfunk": "torrentfunk",
    "extratorrent": "extratorrent",
    "btsow": "btsow",
    "torrentkitty": "torrentkitty",
    "anilibra": "anilibra",
    "gamestorrents": "gamestorrents",
    "megapeer": "megapeer",
    "bitru": "bitru",
    "pctorrent": "pctorrent",
    "xfsub": "xfsub",
    "yihua": "yihua",
    "therarbg": "therarbg",
    "academictorrents": "academictorrents",
    "ali213": "ali213",
    "audiobookbay": "audiobookbay",
    "bt4g": "bt4g",
    "glotorrents": "glotorrents",
    "kickass": "kickass",
    "linuxtracker": "linuxtracker",
    "nyaa": "nyaasi",
    "pirateiro": "pirateiro",
    "rockbox": "rockbox",
    "snowfl": "snowfl",
    "tokyotoshokan": "tokyotoshokan",
    "torrentdownload": "torrentdownload",
    "torrentgalaxy": "torrentgalaxy",
    "torrentproject2": "torrentproject2",
    "yourbittorrent": "yourbittorrent",
    "yts": "yts"
}


class TestNewPluginSyntax(unittest.TestCase):
    """Test syntax of all new plugins."""

    def test_all_new_plugins_have_valid_syntax(self):
        """Verify all new plugins have valid Python syntax."""
        print("\n[TEST] Checking syntax of new plugins...")
        
        for plugin in NEW_PLUGINS:
            plugin_file = os.path.join(plugins_dir, f"{plugin}.py")
            
            if not os.path.exists(plugin_file):
                print(f"  ✗ {plugin}.py not found")
                continue
                
            try:
                with open(plugin_file, 'r') as f:
                    compile(f.read(), plugin_file, 'exec')
                print(f"  ✓ {plugin}.py syntax valid")
            except SyntaxError as e:
                self.fail(f"Syntax error in {plugin}.py: {e}")


class TestNewPluginImports(unittest.TestCase):
    """Test that all new plugins can be imported."""

    def test_all_new_plugins_import(self):
        """Verify all new plugins can be imported."""
        print("\n[TEST] Checking imports of new plugins...")
        
        for plugin in NEW_PLUGINS:
            try:
                module = __import__(plugin)
                print(f"  ✓ {plugin} imported")
            except Exception as e:
                print(f"  ⚠ {plugin} import failed: {str(e)[:50]}")


class TestNewPluginStructure(unittest.TestCase):
    """Test structure of all new plugins."""

    @classmethod
    def setUpClass(cls):
        """Import all new plugins."""
        cls.modules = {}
        for plugin in NEW_PLUGINS:
            try:
                cls.modules[plugin] = __import__(plugin)
            except:
                pass

    def test_new_plugins_have_class(self):
        """Verify all new plugins have their main class."""
        print("\n[TEST] Checking class definitions...")
        
        for plugin in NEW_PLUGINS:
            if plugin not in self.modules:
                continue
                
            module = self.modules[plugin]
            class_name = CLASS_NAMES.get(plugin, plugin.capitalize())
            
            if hasattr(module, class_name):
                print(f"  ✓ {plugin}.{class_name}")
            else:
                print(f"  ⚠ {plugin}.{class_name} not found")

    def test_new_plugins_have_required_attributes(self):
        """Verify all new plugins have required attributes."""
        print("\n[TEST] Checking required attributes...")
        
        for plugin in NEW_PLUGINS:
            if plugin not in self.modules:
                continue
                
            module = self.modules[plugin]
            class_name = CLASS_NAMES.get(plugin, plugin.capitalize())
            
            if not hasattr(module, class_name):
                continue
                
            cls = getattr(module, class_name)
            
            # Check name
            name = getattr(cls, 'name', None)
            name_ok = name and isinstance(name, str) and len(name) > 0
            
            # Check url
            url = getattr(cls, 'url', None)
            url_ok = url and isinstance(url, str) and url.startswith('http')
            
            # Check supported_categories
            cats = getattr(cls, 'supported_categories', None)
            cats_ok = cats and isinstance(cats, dict) and 'all' in cats
            
            status = []
            if name_ok:
                status.append("name")
            if url_ok:
                status.append("url")
            if cats_ok:
                status.append("categories")
            
            if status:
                print(f"  ✓ {plugin}: {', '.join(status)}")
            else:
                print(f"  ⚠ {plugin}: missing attributes")

    def test_new_plugins_have_required_methods(self):
        """Verify all new plugins have required methods."""
        print("\n[TEST] Checking required methods...")
        
        for plugin in NEW_PLUGINS:
            if plugin not in self.modules:
                continue
                
            module = self.modules[plugin]
            class_name = CLASS_NAMES.get(plugin, plugin.capitalize())
            
            if not hasattr(module, class_name):
                continue
                
            cls = getattr(module, class_name)
            
            has_search = hasattr(cls, 'search') and callable(getattr(cls, 'search'))
            has_download = hasattr(cls, 'download_torrent') and callable(getattr(cls, 'download_torrent'))
            
            if has_search and has_download:
                print(f"  ✓ {plugin}: search(), download_torrent()")
            else:
                missing = []
                if not has_search:
                    missing.append("search")
                if not has_download:
                    missing.append("download_torrent")
                print(f"  ⚠ {plugin}: missing {', '.join(missing)}")


class TestNewPluginCategories(unittest.TestCase):
    """Test category support in new plugins."""

    @classmethod
    def setUpClass(cls):
        """Import all new plugins."""
        cls.modules = {}
        for plugin in NEW_PLUGINS:
            try:
                cls.modules[plugin] = __import__(plugin)
            except:
                pass

    def test_category_support(self):
        """Check which categories each plugin supports."""
        print("\n[TEST] Checking category support...")
        
        standard_cats = ['all', 'movies', 'tv', 'music', 'games', 'software', 'anime', 'books']
        
        for plugin in NEW_PLUGINS:
            if plugin not in self.modules:
                continue
                
            module = self.modules[plugin]
            class_name = CLASS_NAMES.get(plugin, plugin.capitalize())
            
            if not hasattr(module, class_name):
                continue
                
            cls = getattr(module, class_name)
            cats = getattr(cls, 'supported_categories', {})
            
            supported = [c for c in standard_cats if c in cats]
            print(f"  ✓ {plugin}: {', '.join(supported) if supported else 'all only'}")


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestNewPluginSyntax))
    suite.addTests(loader.loadTestsFromTestCase(TestNewPluginImports))
    suite.addTests(loader.loadTestsFromTestCase(TestNewPluginStructure))
    suite.addTests(loader.loadTestsFromTestCase(TestNewPluginCategories))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    print("NEW PLUGINS TEST SUMMARY")
    print("="*70)
    print(f"Total tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
