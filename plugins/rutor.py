#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rutor.org search engine plugin for qBittorrent with environment variable support."""
# VERSION: 1.17-modified
# AUTHORS: imDMG [imdmgg@gmail.com]
# MODIFIED: Added environment variable support

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


def _get_proxy_from_env():
    """Parse proxy from environment variable."""
    http_proxy = _get_env("RUTOR_PROXY_HTTP", _get_env("HTTP_PROXY", ""))
    https_proxy = _get_env("RUTOR_PROXY_HTTPS", _get_env("HTTPS_PROXY", ""))

    if http_proxy or https_proxy:
        return {"http": http_proxy, "https": https_proxy}
    return {"http": "", "https": ""}


class Config:
    use_magnet = _get_env("RUTOR_USE_MAGNET", "false").lower() == "true"
    proxy_enabled = _get_env("RUTOR_PROXY_ENABLED", "false").lower() == "true"
    proxies = _get_proxy_from_env()
    user_agent = _get_env(
        "RUTOR_USER_AGENT",
        "Mozilla/5.0 (X11; Linux i686; rv:38.0) Gecko/20100101 Firefox/38.0",
    )


CONFIG = Config()

import base64
import json
import logging
import re
import socket
import time
import tempfile
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import ProxyHandler, build_opener

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


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

RE_TORRENTS = re.compile(
    r'(?:gai|tum)"><td>(?P<pub_date>.+?)</td.+?href="(?P<mag_link>magnet:'
    r'.+?)".+?href="/(?P<desc_link>torrent/(?P<tor_id>\d+).+?)">(?P<name>.+?)'
    r'</a.+?right">(?P<size>[.\d]+?&nbsp;\w+?)</td.+?<span.+?(?P<seeds>\d+?)'
    r"</span>.+?<span.+?(?P<leech>\d+?)</span>",
    re.S,
)
RE_RESULTS = re.compile(r"</b>\sРезультатов\sпоиска\s(\d{1,4})\s", re.S)
PATTERNS = ("%ssearch/%i/%i/000/0/%s",)

PAGES = 100


def rng(t: int) -> range:
    return range(1, -(-t // PAGES))


def date_normalize(date_str: str) -> int:
    months = (
        "Янв",
        "Фев",
        "Мар",
        "Апр",
        "Май",
        "Июн",
        "Июл",
        "Авг",
        "Сен",
        "Окт",
        "Ноя",
        "Дек",
    )
    date_str = [
        date_str.replace(m, f"{i:02d}")
        for i, m in enumerate(months, 1)
        if m in date_str
    ][0]
    return int(time.mktime(time.strptime(date_str, "%d %m %y")))


class EngineError(Exception):
    pass


class Rutor:
    name = "Rutor"
    url = "https://rutor.info/"
    url_dl = url.replace("//", "//d.") + "download/"
    supported_categories = {
        "all": 0,
        "movies": 1,
        "tv": 6,
        "music": 2,
        "games": 8,
        "anime": 10,
        "software": 9,
        "pictures": 3,
        "books": 11,
    }

    session = build_opener()

    def __init__(self):
        self._init()

    def search(self, what: str, cat: str = "all") -> None:
        self._catch_errors(self._search, what, cat)

    def download_torrent(self, url: str) -> None:
        self._catch_errors(self._download_torrent, url)

    def searching(self, query: str, first: bool = False) -> int:
        page = self._request(query).decode()
        torrents_found = -1

        if first:
            match = RE_RESULTS.search(page)
            if match is None:
                logger.debug(f"Unexpected page content:\n {page}")
                raise EngineError("Unexpected page content")
            torrents_found = int(match[1])
            if torrents_found <= 0:
                return 0

        self.draw(page)
        return torrents_found

    def draw(self, html: str) -> None:
        for tor in RE_TORRENTS.finditer(html):
            novaprinter.prettyPrinter(
                {
                    "link": (
                        tor.group("mag_link")
                        if CONFIG.use_magnet
                        else self.url_dl + tor.group("tor_id")
                    ),
                    "name": unescape(tor.group("name")),
                    "size": tor.group("size").replace("&nbsp;", " "),
                    "seeds": int(tor.group("seeds")),
                    "leech": int(tor.group("leech")),
                    "engine_url": self.url,
                    "desc_link": self.url + tor.group("desc_link"),
                    "pub_date": date_normalize(unescape(tor.group("pub_date"))),
                }
            )

    def _catch_errors(self, handler, *args):
        try:
            handler(*args)
        except EngineError as ex:
            logger.exception(ex)
            self.pretty_error(args[0], str(ex))
        except Exception as ex:
            self.pretty_error(args[0], "Unexpected error, please check logs")
            logger.exception(ex)

    def _init(self) -> None:
        if CONFIG.proxy_enabled:
            if not any(CONFIG.proxies.values()):
                raise EngineError("Proxy enabled, but not set!")

            for proxy_str in CONFIG.proxies.values():
                if not proxy_str.lower().startswith("socks"):
                    continue
                try:
                    import socks

                    url = urlparse(proxy_str)
                    socks.set_default_proxy(
                        socks.PROXY_TYPE_SOCKS5,
                        url.hostname,
                        url.port,
                        True,
                        url.username,
                        url.password,
                    )
                    socket.socket = socks.socksocket
                    break
                except ImportError:
                    pass
            else:
                self.session.add_handler(ProxyHandler(CONFIG.proxies))
            logger.debug("Proxy is set!")

        self.session.addheaders = [("User-Agent", CONFIG.user_agent)]

    def _search(self, what: str, cat: str = "all") -> None:
        query = PATTERNS[0] % (
            self.url,
            0,
            self.supported_categories[cat],
            quote(unquote(what)),
        )

        t0 = time.time()
        total = self.searching(query, True)

        if total > PAGES:
            query = query.replace("h/0", "h/{}")
            qrs = [query.format(x) for x in rng(total)]
            with ThreadPoolExecutor(len(qrs)) as executor:
                executor.map(self.searching, qrs, timeout=30)

        logger.debug(f"--- {time.time() - t0} seconds ---")
        logger.info(f"Found torrents: {total}")

    def _download_torrent(self, url: str) -> None:
        response = self._request(url)

        file_handle, temp_path = tempfile.mkstemp(suffix=".torrent")

        try:
            with os.fdopen(file_handle, "wb") as f:
                f.write(response)
                f.flush()
                os.fsync(f.fileno())

            os.chmod(temp_path, 0o644)

            logger.info("Torrent file saved to: {}".format(temp_path))
            print(temp_path + " " + url)
            sys.stdout.flush()

        except Exception as e:
            try:
                os.unlink(temp_path)
            except:
                pass
            raise e

    def _request(self, url: str, data=None, repeated: bool = False) -> bytes:
        try:
            with self.session.open(url, data, 5) as r:
                if r.geturl().startswith((self.url, self.url_dl)):
                    return r.read()
                raise EngineError(f"{url} is blocked. Try another proxy.")
        except (URLError, HTTPError) as err:
            error = str(err.reason)
            reason = f"{url} is not response! Maybe it is blocked."
            if "timed out" in error and not repeated:
                logger.debug("Request timed out. Repeating...")
                return self._request(url, data, True)
            if "no host given" in error:
                reason = "Proxy is bad, try another!"
            elif isinstance(err, HTTPError):
                reason = f"Request to {url} failed with status: {err.code}"
            raise EngineError(reason)

    def pretty_error(self, what: str, error: str) -> None:
        novaprinter.prettyPrinter(
            {
                "engine_url": self.url,
                "desc_link": self.url,
                "name": f"[{unquote(what)}][Error]: {error}",
                "link": self.url + "error",
                "size": "1 TB",
                "seeds": 100,
                "leech": 100,
                "pub_date": int(time.time()),
            }
        )


rutor = Rutor

if __name__ == "__main__":
    from timeit import timeit

    logging.info("Testing Rutor...")
    engine = Rutor()
    logging.info("[timeit] %s", timeit(lambda: engine.search("ubuntu"), number=1))
    logging.info("[timeit] %s", timeit(lambda: engine.search("doctor"), number=1))
