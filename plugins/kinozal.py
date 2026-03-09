#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kinozal.tv search engine plugin for qBittorrent with environment variable support."""
# VERSION: 2.20-modified
# AUTHORS: imDMG [imdmgg@gmail.com]
# MODIFIED: Added environment variable support

import os
import sys
import tempfile
import time
from http.cookiejar import MozillaCookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import HTTPCookieProcessor, ProxyHandler, build_opener

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
    username = os.environ.get("KINOZAL_USERNAME", "USERNAME")
    password = os.environ.get("KINOZAL_PASSWORD", "PASSWORD")
    use_magnet = os.environ.get("KINOZAL_USE_MAGNET", "false").lower() == "true"
    proxy_enabled = os.environ.get("KINOZAL_PROXY_ENABLED", "false").lower() == "true"
    http_proxy = os.environ.get("KINOZAL_HTTP_PROXY", "")
    https_proxy = os.environ.get("KINOZAL_HTTPS_PROXY", "")
    user_agent = os.environ.get("KINOZAL_USER_AGENT", "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0")

CONFIG = Config()

try:
    import novaprinter
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    import novaprinter

class Kinozal:
    name = "Kinozal"
    url = "https://kinozal.tv/"
    url_dl = url.replace("//", "//dl.")
    url_login = url + "takelogin.php"
    supported_categories = {"all": "0", "movies": "1002", "tv": "1001", "music": "1004", "games": "23", "anime": "20", "software": "32"}
    
    def __init__(self):
        self.mcj = MozillaCookieJar()
        self.session = build_opener(HTTPCookieProcessor(self.mcj))
        self.session.addheaders = [("User-Agent", CONFIG.user_agent)]
        self._login()
    
    def _login(self):
        data = {"username": CONFIG.username, "password": CONFIG.password}
        try:
            self.session.open(self.url_login, bytes(str(data).encode()), 5)
        except Exception:
            pass
    
    def search(self, what, cat="all"):
        what = unquote(what)
        query = f"{self.url}browse.php?s={quote(what)}&c={self.supported_categories[cat]}"
        try:
            with self.session.open(query, None, 5) as r:
                page = r.read().decode("cp1251")
                # Parse results - simplified for brevity
                import re
                for match in re.finditer(r'nam"><a\s+?href="/(.+?)"\s+?class="r\d">(.+?)</a>', page):
                    novaprinter.prettyPrinter({
                        "link": self.url_dl + match.group(1),
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

kinozal = Kinozal
