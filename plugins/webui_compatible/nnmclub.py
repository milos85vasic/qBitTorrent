#!/usr/bin/env python3
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
