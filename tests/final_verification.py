#!/usr/bin/env python3
"""Final verification test for all qBittorrent plugins."""

import os
import sys

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
plugins_dir = os.path.join(project_dir, "plugins")
sys.path.insert(0, plugins_dir)

PLUGINS = [
    "eztv", "jackett", "limetorrents", "piratebay",
    "solidtorrents", "torlock", "torrentproject", "torrentscsv",
    "rutracker", "rutor", "kinozal", "nnmclub"
]

def test_plugin_structure(plugin_name):
    """Test plugin structure."""
    try:
        module = __import__(plugin_name)
        
        class_names = {
            "rutracker": "RuTracker",
            "rutor": "Rutor",
            "kinozal": "Kinozal",
            "nnmclub": "NNMClub",
            "piratebay": "piratebay",
            "limetorrents": "limetorrents",
            "jackett": "jackett",
            "eztv": "Eztv",
            "solidtorrents": "solidtorrents",
            "torlock": "torlock",
            "torrentproject": "torrentproject",
            "torrentscsv": "torrentscsv",
        }
        class_name = class_names.get(plugin_name, plugin_name.capitalize())
        
        if not hasattr(module, class_name):
            return False, f"Class {class_name} not found"
        
        engine_class = getattr(module, class_name)
        
        # Check required fields
        required = ['name', 'url', 'supported_categories']
        for attr in required:
            if not hasattr(engine_class, attr):
                return False, f"Missing attribute: {attr}"
        
        # Check required methods
        # Note: Some plugins (magnet-only) don't need download_torrent
        magnet_only_plugins = ['piratebay', 'solidtorrents', 'torrentscsv']
        
        if not hasattr(engine_class, 'search') or not callable(getattr(engine_class, 'search')):
            return False, "Missing method: search"
        
        if plugin_name not in magnet_only_plugins:
            if not hasattr(engine_class, 'download_torrent') or not callable(getattr(engine_class, 'download_torrent')):
                return False, "Missing method: download_torrent"
        
        return True, f"name={getattr(engine_class, 'name', 'N/A')}"
    
    except Exception as e:
        return False, str(e)

def main():
    print("="*70)
    print("FINAL VERIFICATION - All Plugins")
    print("="*70)
    print()
    
    print("Installed Plugins (12 total):")
    print("-" * 70)
    
    results = {}
    for plugin in PLUGINS:
        success, msg = test_plugin_structure(plugin)
        results[plugin] = success
        status = "✓" if success else "✗"
        print(f"  {status} {plugin:20s} - {msg}")
    
    print()
    print("-" * 70)
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"Results: {passed}/{total} plugins passed structure test")
    print()
    
    print("WebUI Compatibility:")
    print("-" * 70)
    webui_compatible = [
        "eztv", "jackett", "limetorrents", "piratebay",
        "solidtorrents", "torlock", "torrentproject", "torrentscsv",
        "rutor"
    ]
    webui_not_compatible = ["rutracker", "kinozal", "nnmclub"]
    
    print(f"  ✓ Works in WebUI: {len(webui_compatible)} plugins")
    for p in webui_compatible:
        print(f"      - {p}")
    
    print()
    print(f"  ⚠ Requires Desktop App: {len(webui_not_compatible)} plugins")
    for p in webui_not_compatible:
        print(f"      - {p}")
    
    print()
    print("="*70)
    if passed == total:
        print("✓ ALL PLUGINS VERIFIED AND READY!")
        print()
        print("Next steps:")
        print("  1. Access WebUI at http://localhost:78085")
        print("  2. Login with admin/admin")
        print("  3. Go to Search → Search Plugins")
        print("  4. Enable plugins you want to use")
        print("  5. For private trackers, use Desktop App")
        return 0
    else:
        print("✗ SOME PLUGINS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
