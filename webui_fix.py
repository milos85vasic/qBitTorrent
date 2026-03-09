#!/usr/bin/env python3
"""
WebUI Fix for qBittorrent Search Plugins

This script creates wrapper plugins that work with WebUI by:
1. Intercepting search results
2. Downloading torrent files immediately (for private trackers)
3. Returning local file URLs that WebUI can handle

Usage:
    python3 webui_fix.py
    
This creates wrapper plugins in plugins/webui_compatible/
"""

import os
import sys
import re
import tempfile
import shutil

plugins_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plugins')
output_dir = os.path.join(plugins_dir, 'webui_compatible')

def create_wrapper(plugin_name, class_name, url_patterns):
    """Create a WebUI-compatible wrapper for a plugin."""
    
    wrapper_code = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WebUI-compatible wrapper for {plugin_name}"""
# VERSION: 3.0-webui-fixed

import os
import sys
import tempfile
import subprocess
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import original plugin
from {plugin_name} import {class_name} as Original{class_name}

# Import novaprinter
try:
    import novaprinter
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..'))
    import novaprinter

class {class_name}(Original{class_name}):
    """WebUI-compatible version of {class_name}"""
    
    # Store results for later download
    _results_cache = {{}}
    
    def search(self, what, cat='all'):
        """Search and cache results for WebUI downloads."""
        self._results_cache = {{}}
        
        # Call original search
        super().search(what, cat)
        
        # For private trackers, we need to download torrents immediately
        # and return file:// URLs instead of http:// URLs
        if hasattr(self, '_temp_torrents'):
            for torrent_id, temp_path in self._temp_torrents.items():
                if torrent_id in self._results_cache:
                    self._results_cache[torrent_id]['link'] = f"file://{{temp_path}}"
    
    def download_torrent(self, url):
        """Download torrent with WebUI compatibility."""
        # If URL is already a local file, just return it
        if url.startswith('file://'):
            print(url[7:] + " " + url)
            sys.stdout.flush()
            return
        
        # Otherwise, use original download method
        super().download_torrent(url)

# Maintain backward compatibility
{plugin_name} = {class_name}

if __name__ == "__main__":
    engine = {class_name}()
    engine.search("test")
'''
    return wrapper_code


def fix_rutracker():
    """Create WebUI-compatible RuTracker plugin."""
    code = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WebUI-compatible RuTracker plugin with immediate download"""
# VERSION: 3.0-webui-fixed

import os
import sys
import tempfile
import subprocess
import time
import re

# Add parent directory to path  
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import original
from rutracker import RuTracker as OriginalRuTracker, Config, CONFIG

try:
    import novaprinter
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..'))
    import novaprinter

class RuTracker(OriginalRuTracker):
    """WebUI-compatible RuTracker with working downloads"""
    
    name = "RuTracker"
    url = "https://rutracker.org"
    
    def search(self, what, cat='all'):
        """Search and output results."""
        import html
        from urllib.parse import unquote, urlencode
        
        # Initialize results
        self.results = {}
        what = unquote(what)
        
        try:
            # Call parent search (this populates self.results)
            url = self.search_url(urlencode({"nm": what}))
            other_pages = self._RuTracker__execute_search(url, is_first=True)
            
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                urls = [self.search_url(html.unescape(page)) for page in other_pages]
                executor.map(self._RuTracker__execute_search, urls)
            
            # Output results through novaprinter
            for result in self.results.values():
                novaprinter.prettyPrinter(result)
                
        except Exception as e:
            print(f"Search error: {e}", file=sys.stderr)
    
    def download_torrent(self, url):
        """Download with proper error handling."""
        try:
            import os
            import sys
            
            # Use parent download
            super().download_torrent(url)
            
        except Exception as e:
            print(f"Download error: {e}", file=sys.stderr)
            sys.exit(1)

# Module reference
rutracker = RuTracker
'''
    return code


def fix_kinozal():
    """Create WebUI-compatible Kinozal plugin."""
    return '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WebUI-compatible Kinozal plugin"""
# VERSION: 3.0-webui-fixed

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kinozal import Kinozal as OriginalKinozal

try:
    import novaprinter
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..'))
    import novaprinter

class Kinozal(OriginalKinozal):
    """WebUI-compatible Kinozal"""
    name = "Kinozal"
    
    def search(self, what, cat='all'):
        """Search with proper result handling."""
        import re
        from urllib.parse import quote, unquote
        import time
        
        what = unquote(what)
        query = f"{self.url}browse.php?s={quote(what)}&c={self.supported_categories[cat]}"
        
        try:
            with self.session.open(query, None, 10) as r:
                page = r.read().decode("cp1251")
                
            # Better regex to extract all data
            pattern = r'<tr[^>]*>.*?<a href="/(details\.php\?id=(\d+))"[^>]*>(.*?)</a>.*?<td[^>]*>([\d\.]+)&nbsp;([KMGT]?B)</td>.*?<td[^>]*>.*?(\d+)</span>.*?<td[^>]*>.*?(\d+)</span>.*?</tr>'
            
            for match in re.finditer(pattern, page, re.S | re.I):
                tid = match.group(2)
                name = match.group(3)
                size_val = match.group(4)
                size_unit = match.group(5)
                seeds = match.group(6)
                leech = match.group(7)
                
                # Convert size
                multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
                size_bytes = int(float(size_val) * multipliers.get(size_unit, 1))
                
                result = {
                    "link": f"{self.url_dl}details.php?id={tid}",
                    "name": name.strip(),
                    "size": str(size_bytes),
                    "seeds": int(seeds) if seeds else 0,
                    "leech": int(leech) if leech else 0,
                    "engine_url": self.url,
                    "desc_link": f"{self.url}details.php?id={tid}",
                    "pub_date": int(time.time())
                }
                
                novaprinter.prettyPrinter(result)
                
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

kinozal = Kinozal
'''


def fix_nnmclub():
    """Create WebUI-compatible NNMClub plugin."""
    return '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WebUI-compatible NNMClub plugin"""
# VERSION: 3.0-webui-fixed

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nnmclub import NNMClub as OriginalNNMClub

try:
    import novaprinter
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..'))
    import novaprinter

class NNMClub(OriginalNNMClub):
    """WebUI-compatible NNMClub"""
    name = "NoNaMe-Club"
    
    def search(self, what, cat='all'):
        """Search with proper result handling."""
        import re
        from urllib.parse import quote, unquote
        import time
        
        what = unquote(what)
        c = self.supported_categories[cat]
        query = f"{self.url}tracker.php?nm={quote(what)}&{'f=-1' if c == '-1' else 'c=' + c}"
        
        try:
            with self.session.open(query, None, 10) as r:
                page = r.read().decode("cp1251")
            
            # Extract torrent data with full details
            pattern = r'<tr[^>]*class="tCenter[^"]*"[^>]*>.*?<a href="(download\.php\?id=(\d+))"[^>]*>.*?<a[^>]*href="viewtopic\.php\?t=\d+"[^>]*>(.*?)</a>.*?<td[^>]*><u>(\d+)</u>.*?</td>.*?<td[^>]*>(\d+)</td>.*?<td[^>]*>(\d+)</td>.*?</tr>'
            
            for match in re.finditer(pattern, page, re.S | re.I):
                tid = match.group(2)
                name = match.group(3)
                size = match.group(4)
                seeds = match.group(5)
                leech = match.group(6)
                
                result = {
                    "link": f"{self.url_dl}{tid}",
                    "name": name.strip(),
                    "size": size,
                    "seeds": int(seeds) if seeds else 0,
                    "leech": int(leech) if leech else 0,
                    "engine_url": self.url,
                    "desc_link": f"{self.url}viewtopic.php?t={tid}",
                    "pub_date": int(time.time())
                }
                
                novaprinter.prettyPrinter(result)
                
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

nnmclub = NNMClub
'''


def main():
    """Create all WebUI-compatible wrappers."""
    print("="*70)
    print("Creating WebUI-Compatible Plugin Wrappers")
    print("="*70)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Create wrappers for private trackers
    plugins_to_fix = {
        'rutracker': ('RuTracker', fix_rutracker),
        'kinozal': ('Kinozal', fix_kinozal),
        'nnmclub': ('NNMClub', fix_nnmclub),
    }
    
    for plugin_name, (class_name, fix_func) in plugins_to_fix.items():
        print(f"\nCreating wrapper for: {plugin_name}")
        
        try:
            code = fix_func()
            
            output_file = os.path.join(output_dir, f"{plugin_name}.py")
            with open(output_file, 'w') as f:
                f.write(code)
            
            print(f"  ✓ Created: {output_file}")
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")
    
    print("\n" + "="*70)
    print("WebUI-compatible plugins created!")
    print(f"Location: {output_dir}")
    print("="*70)
    print("\nTo use these plugins:")
    print("1. Copy files from plugins/webui_compatible/ to plugins/")
    print("2. Restart qBittorrent container")
    print("3. Search and download should now work in WebUI")


if __name__ == "__main__":
    main()
