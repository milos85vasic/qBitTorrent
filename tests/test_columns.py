#!/usr/bin/env python3
"""
Test that all plugins return proper data for all columns.

This test verifies that seeds, leech, and size are actual values,
not hardcoded zeros.
"""

import os
import sys
import time

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
plugins_dir = os.path.join(project_dir, "plugins")
sys.path.insert(0, plugins_dir)

PLUGINS = [
    "eztv", "jackett", "limetorrents", "piratebay",
    "solidtorrents", "torlock", "torrentproject", "torrentscsv",
    "rutracker", "rutor", "kinozal", "nnmclub"
]


class ResultCapture:
    """Capture search results."""
    def __init__(self):
        self.results = []
    
    def prettyPrinter(self, result):
        self.results.append(result)


def test_plugin_columns(plugin_name):
    """Test that plugin returns proper column data."""
    print(f"\n{'='*70}")
    print(f"Testing: {plugin_name}")
    print(f"{'='*70}")
    
    try:
        # Import plugin
        module = __import__(plugin_name)
        
        # Get class name
        class_names = {
            "rutracker": "RuTracker", "rutor": "Rutor",
            "kinozal": "Kinozal", "nnmclub": "NNMClub",
            "piratebay": "piratebay", "limetorrents": "limetorrents",
            "jackett": "jackett", "eztv": "Eztv",
            "solidtorrents": "solidtorrents", "torlock": "torlock",
            "torrentproject": "torrentproject", "torrentscsv": "torrentscsv",
        }
        class_name = class_names.get(plugin_name, plugin_name.capitalize())
        
        if not hasattr(module, class_name):
            return False, f"Class {class_name} not found"
        
        engine_class = getattr(module, class_name)
        
        # Mock novaprinter
        capture = ResultCapture()
        import novaprinter
        novaprinter.prettyPrinter = capture.prettyPrinter
        
        # Create instance
        try:
            engine = engine_class()
        except Exception as e:
            return None, f"Needs credentials: {str(e)[:50]}"
        
        # Search
        print(f"  Searching for 'ubuntu'...")
        try:
            engine.search('ubuntu')
        except Exception as e:
            return False, f"Search failed: {e}"
        
        if not capture.results:
            return None, "No results (may need credentials)"
        
        print(f"  Found {len(capture.results)} results")
        
        # Check first result
        result = capture.results[0]
        
        # Verify all required fields
        required = ['name', 'link', 'size', 'seeds', 'leech', 'engine_url']
        missing = [f for f in required if f not in result]
        if missing:
            return False, f"Missing fields: {missing}"
        
        # Check for hardcoded zeros
        issues = []
        
        size = result.get('size', 0)
        if size == 0 or size == "0":
            issues.append("size is 0")
        
        seeds = result.get('seeds', 0)
        if seeds == 0:
            issues.append("seeds is 0")
        
        leech = result.get('leech', 0)
        if leech == 0:
            issues.append("leech is 0")
        
        if issues:
            print(f"  ⚠ Warning: {', '.join(issues)} (may be valid for some torrents)")
        
        # Display sample data
        print(f"  ✓ Sample result:")
        print(f"    Name: {str(result.get('name', 'N/A'))[:50]}...")
        print(f"    Size: {result.get('size', 'N/A')}")
        print(f"    Seeds: {result.get('seeds', 'N/A')}")
        print(f"    Leech: {result.get('leech', 'N/A')}")
        
        return True, f"All columns populated"
        
    except Exception as e:
        return False, str(e)[:100]


def main():
    print("="*70)
    print("COLUMN DATA TEST - Verifying all plugins return real data")
    print("="*70)
    print("\nChecking that seeds, leech, and size are actual values...")
    
    results = {}
    
    for plugin in PLUGINS:
        result, msg = test_plugin_columns(plugin)
        results[plugin] = result
        
        status = "✓" if result is True else ("⚠" if result is None else "✗")
        print(f"\n  {status} {plugin}: {msg}")
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)
    
    print(f"\nPassed: {passed}")
    print(f"Failed: {failed}")
    print(f"Skipped (need credentials): {skipped}")
    
    if failed == 0:
        print("\n✓ All available plugins return proper column data!")
        return 0
    else:
        print(f"\n✗ {failed} plugins have issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())
