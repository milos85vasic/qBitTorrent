#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RuTracker search engine plugin for qBittorrent with environment variable support."""
# VERSION: 2.22-fixed
# AUTHORS: nbusseneau (https://github.com/nbusseneau/qBittorrent-RuTracker-plugin)
# MODIFIED: Added environment variable support and fixed download functionality

import os
import sys


def _load_env_file():
    """Load environment variables from .env files."""
    env_paths = [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        "/config/.env",
        os.path.expanduser("~/.qbit.env"),
        os.path.expanduser("~/.config/qbittorrent/.env"),
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
                            value = value.strip().strip('"').strip("'")
                            if key and key not in os.environ:
                                os.environ[key] = value
        except Exception:
            pass


_load_env_file()


def _get_env(key, default=""):
    """Get environment variable with fallback."""
    return os.environ.get(key, default)


def _get_mirrors_from_env():
    """Parse mirrors from environment variable."""
    mirrors_str = _get_env("RUTRACKER_MIRRORS", "")
    if mirrors_str:
        return [m.strip() for m in mirrors_str.split(",") if m.strip()]
    return None


class Config(object):
    username = _get_env(
        "RUTRACKER_USERNAME",
        os.environ.get("RUTRACKER_USER", "YOUR_USERNAME_HERE"),
    )
    password = _get_env(
        "RUTRACKER_PASSWORD",
        os.environ.get("RUTRACKER_PASS", "YOUR_PASSWORD_HERE"),
    )

    mirrors = _get_mirrors_from_env() or [
        "https://rutracker.org",
        "https://rutracker.net",
        "https://rutracker.nl",
    ]


CONFIG = Config()
DEFAULT_ENGINE_URL = CONFIG.mirrors[0]

if CONFIG.username == "YOUR_USERNAME_HERE" or CONFIG.password == "YOUR_PASSWORD_HERE":
    sys.stderr.write(
        "WARNING: RuTracker credentials not configured. "
        "Set RUTRACKER_USERNAME and RUTRACKER_PASSWORD environment variables.\n"
    )


import concurrent.futures
import html
import http.cookiejar as cookielib
import gzip
import logging
import re
import tempfile
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


# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RuTracker(object):
    """RuTracker search engine plugin for qBittorrent."""

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

    re_search_queries = re.compile(r'<a.+?href="tracker\.php\?(.*?start=\d+)"')
    re_threads = re.compile(r'<tr id="trs-tr-\d+.*?</tr>', re.S)
    re_torrent_data = re.compile(
        r'a data-topic_id="(?P<id>\d+?)".*?>(?P<title>.+?)<'
        r".+?"
        r'data-ts_text="(?P<size>\d+?)"'
        r".+?"
        r'data-ts_text="(?P<seeds>[-\d]+?)"'
        r".+?"
        r"leechmed.+?>(?P<leech>\d+?)<"
        r".+?"
        r'data-ts_text="(?P<pub_date>\d+?)"',
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
        """Initialize RuTracker search engine, signing in using given credentials."""
        self.cj = cookielib.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))
        self.opener.addheaders = [
            ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"),
            ("Accept-Encoding", "gzip, deflate"),
        ]
        self.__login()

    def __login(self) -> None:
        """Set up credentials and try to sign in."""
        self.credentials = {
            "login_username": CONFIG.username,
            "login_password": CONFIG.password,
            "login": "\u0412\u0445\u043e\u0434",
        }

        try:
            self._open_url(self.login_url, self.credentials, log_errors=False)
        except (URLError, HTTPError):
            logging.info("Checking for RuTracker mirrors...")
            self.url = self._check_mirrors(CONFIG.mirrors)
            self._open_url(self.login_url, self.credentials)

        if "bb_session" not in [cookie.name for cookie in self.cj]:
            logger.debug("cookiejar: {}".format(self.cj))
            e = ValueError("Unable to connect using given credentials.")
            logger.error(e)
            raise e
        else:
            logger.info("Login successful.")

    def search(self, what: str, cat: str = "all") -> None:
        """Search for what on the search engine."""
        self.results = {}
        what = unquote(what)
        
        # Handle category
        cat_id = self.supported_categories.get(cat, "-1")
        if cat != "all":
            query = urlencode({"nm": what, "f": cat_id})
        else:
            query = urlencode({"nm": what})
        
        logger.info("Searching for {}...".format(what))

        url = self.search_url(query)
        other_pages = self.__execute_search(url, is_first=True)
        logger.info("{} pages of results found.".format(len(other_pages) + 1))

        with concurrent.futures.ThreadPoolExecutor() as executor:
            urls = [self.search_url(html.unescape(page)) for page in other_pages]
            executor.map(self.__execute_search, urls)
        logger.info("{} torrents found.".format(len(self.results)))

    def __execute_search(self, url: str, is_first: bool = False) -> list:
        """Execute search query."""
        try:
            data = self._open_url(url).decode(self.encoding)
        except Exception as e:
            logger.error(f"Search failed for {url}: {e}")
            return []

        for thread in self.re_threads.findall(data):
            match = self.re_torrent_data.search(thread)
            if match:
                torrent_data = match.groupdict()
                logger.debug("Torrent data: {}".format(torrent_data))
                result = self.__build_result(torrent_data)
                self.results[result["id"]] = result
                if __name__ != "__main__":
                    novaprinter.prettyPrinter(result)

        if is_first:
            matches = self.re_search_queries.findall(data)
            other_pages = list(dict.fromkeys(matches))
            return other_pages

        return []

    def __build_result(self, torrent_data: dict) -> dict:
        """Map torrent data to result dict as expected by prettyPrinter."""
        query = urlencode({"t": torrent_data["id"]})
        result = {}
        result["id"] = torrent_data["id"]
        result["link"] = self.download_url(query)
        result["name"] = html.unescape(torrent_data["title"])
        result["size"] = torrent_data["size"]
        result["seeds"] = torrent_data["seeds"]
        result["leech"] = torrent_data["leech"]
        result["engine_url"] = DEFAULT_ENGINE_URL
        result["desc_link"] = self.topic_url(query)
        result["pub_date"] = torrent_data["pub_date"]
        return result

    def _open_url(
        self, url: str, post_params: dict[str, str] = None, log_errors: bool = True
    ) -> bytes:
        """URL request open wrapper returning response bytes if successful."""
        encoded_params = (
            urlencode(post_params, encoding=self.encoding).encode()
            if post_params
            else None
        )
        try:
            with self.opener.open(url, encoded_params or None) as response:
                logger.debug(
                    "HTTP request: {} | status: {}".format(url, response.getcode())
                )
                if response.getcode() != 200:
                    raise HTTPError(
                        response.geturl(),
                        response.getcode(),
                        "HTTP request to {} failed with status: {}".format(
                            url, response.getcode()
                        ),
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
            raise e

    def _check_mirrors(self, mirrors: list) -> str:
        """Try to find a reachable mirror in given list and return its URL."""
        errors = []
        for mirror in mirrors:
            try:
                self.opener.open(mirror)
                logger.info("Found reachable mirror: {}".format(mirror))
                return mirror
            except URLError as e:
                logger.warning("Could not resolve mirror: {}".format(mirror))
                errors.append(e)
        logger.error("Unable to resolve any mirror")
        raise RuntimeError("\n{}".format("\n".join([str(error) for error in errors])))

    def download_torrent(self, url: str) -> None:
        """Download torrent file using authenticated session.
        
        This method is called by nova2dl.py when downloading torrents.
        It uses the authenticated session to download the .torrent file.
        
        Args:
            url: The torrent download URL (e.g., https://rutracker.org/forum/dl.php?t=12345)
            
        Output format (required by qBittorrent):
            <filepath> <url>
            
        Example:
            /tmp/torrent_12345.torrent https://rutracker.org/forum/dl.php?t=12345
        """
        logger.info("Downloading torrent from: {}".format(url))

        try:
            # Use the authenticated opener to download
            data = self._open_url(url)

            if not data:
                raise ValueError("No data received from URL: {}".format(url))

            # Verify this looks like a torrent file (bencode format)
            if not data.startswith(b'd'):
                # Try to decode and check for HTML error page
                try:
                    decoded = data.decode('utf-8', errors='ignore')
                    if '<html' in decoded.lower() or '<!doctype' in decoded.lower():
                        raise ValueError("Received HTML page instead of torrent file - likely authentication error")
                except:
                    pass
                raise ValueError("Downloaded data is not a valid torrent file (does not start with 'd')")

            # Create temp file with proper permissions
            file_handle, temp_path = tempfile.mkstemp(suffix=".torrent", prefix="rutracker_")

            try:
                with os.fdopen(file_handle, "wb") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())

                # Set readable permissions
                os.chmod(temp_path, 0o644)

                logger.info("Torrent saved to: {}".format(temp_path))
                
                # Output format required by qBittorrent: "<filepath> <url>"
                print(temp_path + " " + url)
                sys.stdout.flush()

            except Exception as e:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except:
                    pass
                raise e

        except Exception as e:
            logger.error("Failed to download torrent: {}".format(e))
            print("", file=sys.stderr)
            sys.stderr.flush()
            raise


# Create the engine class reference
rutracker = RuTracker

if __name__ == "__main__":
    import time
    from timeit import timeit

    logging.basicConfig(level=logging.INFO)
    
    try:
        logging.info("Testing RuTracker plugin...")
        engine = RuTracker()
        
        # Test search
        logging.info("\n[Test] Search for 'ubuntu':")
        engine.results = {}
        engine.search("ubuntu")
        logging.info("Found {} results".format(len(engine.results)))
        
        if engine.results:
            # Test download first result
            first_result = list(engine.results.values())[0]
            download_url = first_result["link"]
            logging.info("\n[Test] Downloading: {}".format(download_url))
            engine.download_torrent(download_url)
        else:
            logging.warning("No search results to test download")
            
    except Exception as e:
        logging.error("Test failed: {}".format(e))
        import traceback
        traceback.print_exc()
