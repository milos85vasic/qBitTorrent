#!/usr/bin/env python3
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
