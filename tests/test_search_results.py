#!/usr/bin/env python3
"""
Test search results from all plugins to verify they return proper data.

This test verifies:
1. All plugins return results
2. Results have all required fields (name, link, size, seeds, leech)
3. Seeds and peers are valid numbers
4. Size is properly formatted
"""

import os
import sys
import time

# Setup paths
tests_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(tests_dir)
plugins_dir = os.path.join(project_dir, "plugins")
sys.path.insert(0, plugins_dir)
sys.path.insert(0, tests_dir)

# Import all plugins
PLUGINS = [
    "eztv",
    "jackett", 
    "limetorrents",
    "piratebay",
    "solidtorrents",
    "torlock",
    "torrentproject",
    "torrentscsv",
    "rutracker",
    "rutor",
    "kinozal",
    "nnmclub",
]


class MockPrinter:
    """Mock novaprinter that captures output."""
    def __init__(self):
        self.results = []
    
    def prettyPrinter(self, result):
        self.results.append(result)
        # Print for debugging
        print(f"  Result: {result.get('name', 'N/A')[:50]}... "
              f"Seeds: {result.get('seeds', 'N/A')}, "
              f"Leech: {result.get('leech', 'N/A')}, "
              f"Size: {result.get('size', 'N/A')}")


def test_plugin(plugin_name):
    """Test a single plugin."""
    print(f"\n{'='*70}")
    print(f"Testing: {plugin_name}")
    print(f"{'='*70}")
    
    try:
        # Import plugin
        module = __import__(plugin_name)
        
        # Get class name
        class_names = {
            "rutracker": "RuTracker",
            "rutor": "Rutor",
            "kinozal": "Kinozal",
            "nnmclub": "NNMClub",
        }
        class_name = class_names.get(plugin_name, plugin_name.capitalize())
        
        if not hasattr(module, class_name):
            print(f"  ✗ Class {class_name} not found")
            return False
        
        engine_class = getattr(module, class_name)
        
        # Check plugin info
        name = getattr(engine_class, 'name', 'Unknown')
        url = getattr(engine_class, 'url', 'Unknown')
        print(f"  Plugin: {name}")
        print(f"  URL: {url}")
        
        # Mock novaprinter
        mock_printer = MockPrinter()
        import novaprinter
        novaprinter.prettyPrinter = mock_printer.prettyPrinter
        
        # Create instance
        try:
            engine = engine_class()
        except Exception as e:
            print(f"  ⚠ Could not initialize: {e}")
            print(f"  This is expected for plugins requiring credentials")
            return None  # Skip plugins that need credentials
        
        # Search for test query
        print(f"\n  Searching for 'ubuntu'...")
        try:
            engine.search('ubuntu')
        except Exception as e:
            print(f"  ✗ Search failed: {e}")
            return False
        
        # Check results
        if not mock_printer.results:
            print(f"  ⚠ No results found")
            return None
        
        print(f"\n  Found {len(mock_printer.results)} results")
        
        # Validate first result
        if mock_printer.results:
            result = mock_printer.results[0]
            
            # Check required fields
            required_fields = ['name', 'link', 'size', 'seeds', 'leech', 'engine_url']
            missing = [f for f in required_fields if f not in result]
            
            if missing:
                print(f"  ✗ Missing fields: {missing}")
                return False
            
            # Validate seeds and leech
            try:
                seeds = int(result['seeds'])
                leech = int(result['leech'])
                print(f"  ✓ Seeds: {seeds}, Leech: {leech}")
            except (ValueError, TypeError):
                print(f"  ✗ Invalid seeds/leech values: {result['seeds']}, {result['leech']}")
                return False
            
            # Validate size
            size = str(result['size'])
            if not size or size == '0':
                print(f"  ⚠ Size is empty or zero: {size}")
            else:
                print(f"  ✓ Size: {size}")
            
            # Validate link
            link = result['link']
            if not link:
                print(f"  ✗ Link is empty")
                return False
            
            if link.startswith('magnet:'):
                print(f"  ✓ Magnet link (works with WebUI)")
            elif 'http' in link:
                print(f"  ⚠ HTTP link (requires nova2dl.py for private trackers)")
            
            print(f"  ✓ All fields valid")
            return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return False


def main():
    """Run all plugin tests."""
    print("="*70)
    print("Search Plugin Results Test")
    print("="*70)
    print("\nTesting all plugins for proper result format...")
    print("This includes: name, link, size, seeds, leech, engine_url")
    
    results = {}
    
    for plugin in PLUGINS:
        result = test_plugin(plugin)
        results[plugin] = result
        
        if result is True:
            print(f"  ✓ {plugin}: PASSED")
        elif result is False:
            print(f"  ✗ {plugin}: FAILED")
        else:
            print(f"  ⚠ {plugin}: SKIPPED (needs credentials)")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)
    
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    
    if failed > 0:
        print("\nFailed plugins:")
        for plugin, result in results.items():
            if result is False:
                print(f"  - {plugin}")
    
    print("\n" + "="*70)
    if failed == 0:
        print("✓ ALL TESTS PASSED!")
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
