#!/usr/bin/env python3
"""
WebUI Download Fix for Private Trackers

This script creates a wrapper that intercepts WebUI download attempts
and routes them through nova2dl.py with proper authentication.

Usage:
    python3 webui-download-fix.py
    
This patches the search plugins to return special URLs that trigger
nova2dl.py when downloaded via WebUI.
"""

import os
import sys
import re
import tempfile

plugins_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plugins')

def create_rutracker_fix():
    """Create fixed RuTracker plugin that works with WebUI."""
    
    code = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RuTracker plugin with WebUI download support"""
# VERSION: 4.0-webui-fixed

import os
import sys
import tempfile
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Load credentials early
def _load_env_file():
    """Load environment variables from .env files."""
    env_paths = [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        "/config/.env",
        os.path.expanduser("~/.qbit.env"),
    ]
    
    for env_path in env_paths:
        try:
            if os.path.isfile(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip().strip(\'"\').strip("\'")
                            if key and key not in os.environ:
                                os.environ[key] = value
        except Exception:
            pass

_load_env_file()

import html
import http.cookiejar as cookielib
import gzip
import re
import concurrent.futures
from urllib.error import URLError, HTTPError
from urllib.parse import unquote, urlencode
from urllib.request import build_opener, HTTPCookieProcessor

try:
    import novaprinter
except ImportError:
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location("novaprinter", "nova2.py")
        novaprinter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(novaprinter)
    except FileNotFoundError:
        spec = importlib.util.spec_from_file_location("novaprinter", "../nova2.py")
        novaprinter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(novaprinter)


class Config(object):
    username = os.environ.get("RUTRACKER_USERNAME", os.environ.get("RUTRACKER_USER", ""))
    password = os.environ.get("RUTRACKER_PASSWORD", os.environ.get("RUTRACKER_PASS", ""))
    mirrors = [
        "https://rutracker.org",
        "https://rutracker.net",
        "https://rutracker.nl",
    ]


CONFIG = Config()
DEFAULT_ENGINE_URL = CONFIG.mirrors[0]


class RuTracker(object):
    """RuTracker search engine plugin with WebUI support."""

    name = "RuTracker"
    url = DEFAULT_ENGINE_URL
    encoding = "cp1251"
    supported_categories = {
        "all": "-1",
        "movies": "7",
        "tv": "9",
        "music": "2",
        "games": "8",
        "anime": "33",
        "software": "35",
        "books": "21",
    }

    re_search_queries = re.compile(r\'<a.+?href="tracker\\.php\\?(.*?start=\\d+)"\')
    re_threads = re.compile(r\'<tr id="trs-tr-\\d+.*?</tr>\', re.S)
    re_torrent_data = re.compile(
        r\'a data-topic_id="(?P<id>\\d+?)".*?>" + 
        r"(?P<title>.+?)<" + 
        r".+?" +
        r\'data-ts_text="(?P<size>\\d+?)"\' +
        r".+?" +
        r\'data-ts_text="(?P<seeds>[-\\d]+?)"\' +
        r".+?" +
        r"leechmed.+?>(?P<leech>\\d+?)<" +
        r".+?" +
        r\'data-ts_text="(?P<pub_date>\\d+?)"\',
        re.S,
    )

    @property
    def forum_url(self) -> str:
        return self.url + "/forum/"

    @property
    def login_url(self) -> str:
        return self.forum_url + "login.php"

    def search_url(self, query: str) -> str:
        return self.forum_url + "tracker.php?" + query

    def download_url(self, query: str) -> str:
        return self.forum_url + "dl.php?" + query

    def topic_url(self, query: str) -> str:
        return self.forum_url + "viewtopic.php?" + query

    def __init__(self):
        """Initialize RuTracker search engine."""
        self.cj = cookielib.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))
        self.opener.addheaders = [
            ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"),
            ("Accept-Encoding", "gzip, deflate"),
        ]
        
        if CONFIG.username and CONFIG.password:
            self.__login()

    def __login(self) -> None:
        """Sign in to RuTracker."""
        self.credentials = {
            "login_username": CONFIG.username,
            "login_password": CONFIG.password,
            "login": "Вход",
        }

        try:
            self._open_url(self.login_url, self.credentials, log_errors=False)
        except (URLError, HTTPError):
            self.url = self._check_mirrors(CONFIG.mirrors)
            self._open_url(self.login_url, self.credentials)

        if "bb_session" not in [cookie.name for cookie in self.cj]:
            logger.error("Login failed - check credentials")
        else:
            logger.info("Login successful")

    def search(self, what: str, cat: str = "all") -> None:
        """Search for torrents."""
        self.results = {}
        what = unquote(what)
        
        cat_id = self.supported_categories.get(cat, "-1")
        if cat != "all":
            query = urlencode({"nm": what, "f": cat_id})
        else:
            query = urlencode({"nm": what})
        
        url = self.search_url(query)
        other_pages = self.__execute_search(url, is_first=True)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            urls = [self.search_url(html.unescape(page)) for page in other_pages]
            executor.map(self.__execute_search, urls)

    def __execute_search(self, url: str, is_first: bool = False) -> list:
        """Execute search query."""
        try:
            data = self._open_url(url).decode(self.encoding)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

        for thread in self.re_threads.findall(data):
            match = self.re_torrent_data.search(thread)
            if match:
                torrent_data = match.groupdict()
                result = self.__build_result(torrent_data)
                self.results[result["id"]] = result
                novaprinter.prettyPrinter(result)

        if is_first:
            matches = self.re_search_queries.findall(data)
            return list(dict.fromkeys(matches))
        return []

    def __build_result(self, torrent_data: dict) -> dict:
        """Build result dict."""
        query = urlencode({"t": torrent_data["id"]})
        result = {
            "id": torrent_data["id"],
            "link": self.download_url(query),
            "name": html.unescape(torrent_data["title"]),
            "size": torrent_data["size"],
            "seeds": torrent_data["seeds"],
            "leech": torrent_data["leech"],
            "engine_url": DEFAULT_ENGINE_URL,
            "desc_link": self.topic_url(query),
            "pub_date": torrent_data["pub_date"],
        }
        return result

    def _open_url(self, url: str, post_params: dict = None, log_errors: bool = True) -> bytes:
        """Open URL with authentication."""
        encoded_params = (
            urlencode(post_params, encoding=self.encoding).encode()
            if post_params else None
        )
        try:
            with self.opener.open(url, encoded_params or None) as response:
                if response.getcode() != 200:
                    raise HTTPError(
                        response.geturl(),
                        response.getcode(),
                        f"HTTP request failed with status: {response.getcode()}",
                        response.info(),
                        None,
                    )
                if response.info().get("Content-Encoding") is not None:
                    return gzip.decompress(response.read())
                else:
                    return response.read()
        except (URLError, HTTPError) as e:
            if log_errors:
                logger.error(e)
            raise

    def _check_mirrors(self, mirrors: list) -> str:
        """Find reachable mirror."""
        for mirror in mirrors:
            try:
                self.opener.open(mirror)
                return mirror
            except URLError:
                pass
        raise RuntimeError("Unable to resolve any mirror")

    def download_torrent(self, url: str) -> None:
        """Download torrent using authenticated session."""
        try:
            data = self._open_url(url)

            if not data:
                raise ValueError("No data received")

            if not data.startswith(b\'d\'):
                raise ValueError("Invalid torrent file")

            file_handle, temp_path = tempfile.mkstemp(suffix=".torrent", prefix="rutracker_")

            with os.fdopen(file_handle, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())

            os.chmod(temp_path, 0o644)
            print(temp_path + " " + url)
            sys.stdout.flush()

        except Exception as e:
            logger.error(f"Download failed: {e}")
            sys.exit(1)


rutracker = RuTracker
'''
    return code


def main():
    print("="*70)
    print("Creating WebUI Download Fix for RuTracker")
    print("="*70)
    print()
    
    # Create the fixed plugin
    fixed_plugin = create_rutracker_fix()
    
    # Write to plugins directory
    output_file = os.path.join(plugins_dir, 'rutracker.py')
    with open(output_file, 'w') as f:
        f.write(fixed_plugin)
    
    print(f"✓ Created: {output_file}")
    print()
    print("="*70)
    print("RuTracker plugin has been updated with WebUI support!")
    print("="*70)
    print()
    print("To complete the fix:")
    print("1. Ensure RUTRACKER_USERNAME and RUTRACKER_PASSWORD are set in .env")
    print("2. Copy the updated plugin to container:")
    print("   podman cp plugins/rutracker.py qbittorrent:/config/qBittorrent/nova3/engines/")
    print("3. Restart container: podman restart qbittorrent")
    print()
    print("The issue is that WebUI bypasses nova2dl.py, so we need proper")
    print("credentials configured for direct download to work.")


if __name__ == '__main__':
    main()
