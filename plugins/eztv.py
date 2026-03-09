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
            # Make request
            req = Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
            
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
