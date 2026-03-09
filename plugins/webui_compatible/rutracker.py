#!/usr/bin/env python3
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
