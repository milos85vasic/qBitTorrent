#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EZTV search engine plugin for qBittorrent."""
# VERSION: 1.1
# AUTHORS: Diego de las Heras (ngosang@hotmail.es)

import json
import logging
import re
import sys
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    import novaprinter
except ImportError:
    pass

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class Eztv(object):
    """EZTV search engine plugin."""
    
    url = 'https://eztv.re'
    name = 'EZTV'
    supported_categories = {'all': 'all', 'tv': 'tv'}
    
    # Regex patterns
    re_result = re.compile(
        r'<tr.*?name="hover".*?>.*?'
        r'<td.*?>(?P<name>.*?)</td>.*?'
        r'href="(?P<link>magnet:.*?)".*?'
        r'<td.*?>(?P<size>.*?)</td>.*?'
        r'<td.*?>(?P<date>.*?)</td>.*?'
        r'<td.*?>(?P<seeds>\d+)</td>.*?'
        r'<td.*?>(?P<peers>\d+)</td>.*?'
        r'</tr>',
        re.S
    )
    
    def search(self, what, cat='all'):
        """Search for torrents."""
        what = quote(what)
        
        # Build search URL
        search_url = f'{self.url}/search/{what}'
        
        try:
            # Make request with enhanced headers to avoid 403
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            req = Request(search_url, headers=headers)
            with urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='ignore')
            
            # Parse results
            for match in self.re_result.finditer(html):
                result = match.groupdict()
                
                # Build result dict
                res = {
                    'link': result['link'],
                    'name': result['name'],
                    'size': result['size'],
                    'seeds': result['seeds'],
                    'leech': result['peers'],
                    'engine_url': self.url,
                    'desc_link': search_url,
                    'pub_date': int(time.time())
                }
                
                # Output result
                if 'novaprinter' in sys.modules:
                    novaprinter.prettyPrinter(res)
                else:
                    print(res)
                    
        except Exception as e:
            logger.error(f'Search failed: {e}')
            
    def download_torrent(self, url):
        """Download torrent (EZTV returns magnet links)."""
        # EZTV returns magnet links, which qBittorrent handles directly
        print(url + ' ' + url)


# Module reference
eztv = Eztv

if __name__ == '__main__':
    e = Eztv()
    e.search('test')
