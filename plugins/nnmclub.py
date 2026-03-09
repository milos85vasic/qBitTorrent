#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NNM-Club.me search engine plugin for qBittorrent with environment variable support."""
# VERSION: 2.22-modified  
# AUTHORS: imDMG [imdmgg@gmail.com]
# MODIFIED: Added environment variable support

import os
import sys
import tempfile
import time
from http.cookiejar import Cookie, MozillaCookieJar
from urllib.parse import quote, unquote
from urllib.request import HTTPCookieProcessor, build_opener

# Load environment variables
def _load_env():
    for path in [os.path.dirname(__file__), "/config"]:
        env_file = os.path.join(path, ".env") if path == "/config" else os.path.join(path, "..", ".env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        k, v = line.strip().split("=", 1)
                        if k not in os.environ:
                            os.environ[k] = v.strip('"').strip("'")

_load_env()

class Config:
    username = os.environ.get("NNMCLUB_USERNAME", "USERNAME")
    cookies = os.environ.get("NNMCLUB_COOKIES", "COOKIES")
    proxy_enabled = os.environ.get("NNMCLUB_PROXY_ENABLED", "false").lower() == "true"
    user_agent = os.environ.get("NNMCLUB_USER_AGENT", "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0")

CONFIG = Config()

try:
    import novaprinter
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    import novaprinter

class NNMClub:
    name = "NoNaMe-Club"
    url = "https://nnmclub.to/forum/"
    url_dl = "https://bulk.nnmclub.to/"
    supported_categories = {"all": "-1", "movies": "14", "tv": "27", "music": "16", "games": "17", "anime": "24", "software": "21"}
    
    def __init__(self):
        self.mcj = MozillaCookieJar()
        self.session = build_opener(HTTPCookieProcessor(self.mcj))
        self.session.addheaders = [("User-Agent", CONFIG.user_agent)]
        self._load_cookies()
    
    def _load_cookies(self):
        for cookie in CONFIG.cookies.split("; "):
            name, value = cookie.split("=", 1)
            self.mcj.set_cookie(Cookie(0, name, value, None, False, "nnmclub.to", True, False, "/", True, False, None, False, None, None, {}))
    
    def search(self, what, cat="all"):
        what = unquote(what)
        c = self.supported_categories[cat]
        query = f"{self.url}tracker.php?nm={quote(what)}&{'f=-1' if c == '-1' else 'c=' + c}"
        try:
            with self.session.open(query, None, 5) as r:
                page = r.read().decode("cp1251")
                # Parse results - simplified
                import re
                for match in re.finditer(r'topictitle"\shref="(.+?)"><b>(.+?)</b>', page):
                    novaprinter.prettyPrinter({
                        "link": self.url + match.group(1),
                        "name": match.group(2),
                        "size": "0",
                        "seeds": 0,
                        "leech": 0,
                        "engine_url": self.url,
                        "desc_link": self.url + match.group(1),
                        "pub_date": int(time.time())
                    })
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
    
    def download_torrent(self, url):
        try:
            with self.session.open(url, None, 5) as r:
                data = r.read()
            
            fd, path = tempfile.mkstemp(suffix=".torrent")
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            
            os.chmod(path, 0o644)
            print(f"{path} {url}")
            sys.stdout.flush()
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

nnmclub = NNMClub
