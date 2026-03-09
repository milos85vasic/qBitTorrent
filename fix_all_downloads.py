#!/usr/bin/env python3
"""
Fix download methods for all plugins
Ensures every plugin can properly handle downloads via nova2dl.py
"""

import os
import sys
import re

plugins_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plugins')

def fix_plugin_download_method(plugin_file, plugin_name):
    """Add or fix download_torrent method for a plugin."""
    
    with open(plugin_file, 'r') as f:
        content = f.read()
    
    # Check if download_torrent exists
    if 'def download_torrent' in content:
        print(f"  {plugin_name}: download_torrent already exists")
        return True
    
    # For magnet-only plugins, add a simple handler
    if plugin_name in ['piratebay', 'eztv', 'solidtorrents', 'torlock']:
        # These return magnet links
        method = '''
    def download_torrent(self, url):
        """Handle magnet links - just pass through."""
        import sys
        if url.startswith('magnet:'):
            # For magnet links, output as-is (qBittorrent handles them)
            print(url + " " + url)
            sys.stdout.flush()
        else:
            # Fallback to direct download
            import tempfile
            import urllib.request
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = response.read()
                
                fd, path = tempfile.mkstemp(suffix=".torrent")
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                
                import os
                os.chmod(path, 0o644)
                print(path + " " + url)
                sys.stdout.flush()
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
'''
    else:
        # For HTTP URL plugins
        method = '''
    def download_torrent(self, url):
        """Download torrent file from URL."""
        import os
        import sys
        import tempfile
        import urllib.request
        
        try:
            # Handle magnet links
            if url.startswith('magnet:'):
                print(url + " " + url)
                sys.stdout.flush()
                return
            
            # Download the file
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
            
            # Verify it's a torrent file (starts with 'd')
            if not data.startswith(b'd'):
                print(f"Error: Not a valid torrent file", file=sys.stderr)
                sys.exit(1)
            
            # Save to temp file
            fd, path = tempfile.mkstemp(suffix=".torrent")
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            
            os.chmod(path, 0o644)
            print(path + " " + url)
            sys.stdout.flush()
            
        except Exception as e:
            print(f"Error downloading torrent: {e}", file=sys.stderr)
            sys.exit(1)
'''
    
    # Find a good place to insert the method (before the last line or class end)
    lines = content.split('\n')
    
    # Find the last method or the end of class
    insert_index = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() and not lines[i].strip().startswith('#'):
            insert_index = i + 1
            break
    
    # Insert the method
    lines.insert(insert_index, method)
    
    with open(plugin_file, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"  {plugin_name}: Added download_torrent method")
    return True


def main():
    print("="*70)
    print("Fixing Download Methods for All Plugins")
    print("="*70)
    print()
    
    plugins_to_fix = [
        ('piratebay.py', 'piratebay'),
        ('eztv.py', 'eztv'),
        ('limetorrents.py', 'limetorrents'),
        ('solidtorrents.py', 'solidtorrents'),
        ('torlock.py', 'torlock'),
        ('torrentproject.py', 'torrentproject'),
        ('torrentscsv.py', 'torrentscsv'),
    ]
    
    fixed = 0
    for filename, name in plugins_to_fix:
        filepath = os.path.join(plugins_dir, filename)
        if os.path.exists(filepath):
            if fix_plugin_download_method(filepath, name):
                fixed += 1
        else:
            print(f"  {name}: File not found")
    
    print()
    print("="*70)
    print(f"Fixed {fixed} plugins")
    print("="*70)
    print("\nNext steps:")
    print("1. Copy updated plugins to container")
    print("2. Restart qBittorrent")
    print("3. Test downloads again")


if __name__ == "__main__":
    main()
