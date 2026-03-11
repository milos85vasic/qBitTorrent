# VERSION: 4.15
# AUTHORS: Lima66
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)
# MODIFIED: Returns magnet links in search results for WebUI compatibility

import re
import logging
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Callable, Dict, List, Mapping, Match, Tuple, Union
from urllib.parse import quote

from helpers import retrieve_url, build_magnet_link
from novaprinter import prettyPrinter

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class limetorrents:
    url = "https://www.limetorrents.lol"
    name = "LimeTorrents"
    supported_categories = {
        "all": "all",
        "anime": "anime",
        "software": "applications",
        "games": "games",
        "movies": "movies",
        "music": "music",
        "tv": "tv",
    }

    TRACKERS = [
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://open.stealth.si:80/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://tracker.bittor.pw:1337/announce",
        "udp://exodus.desync.com:6969/announce",
    ]

    class MyHtmlParser(HTMLParser):
        """Sub-class for parsing results"""

        def error(self, message: str) -> None:
            pass

        A, TD, TR, HREF = ("a", "td", "tr", "href")

        def __init__(self, url: str, parent: "limetorrents") -> None:
            HTMLParser.__init__(self)
            self.url = url
            self.parent = parent
            self.current_item: Dict[str, object] = {}
            self.page_items = 0
            self.inside_table = False
            self.inside_tr = False
            self.column_index = -1
            self.column_name: Union[str, None] = None
            self.columns = ["name", "pub_date", "size", "seeds", "leech"]
            self.results: List[Dict] = []

            now = datetime.now()
            self.date_parsers: Mapping[str, Callable[[Match[str]], datetime]] = {
                r"yesterday": lambda m: now - timedelta(days=1),
                r"last\s+month": lambda m: now - timedelta(days=30),
                r"(\d+)\s+years?": lambda m: now - timedelta(days=int(m[1]) * 365),
                r"(\d+)\s+months?": lambda m: now - timedelta(days=int(m[1]) * 30),
                r"(\d+)\s+days?": lambda m: now - timedelta(days=int(m[1])),
                r"(\d+)\s+hours?": lambda m: now - timedelta(hours=int(m[1])),
                r"(\d+)\s+minutes?": lambda m: now - timedelta(minutes=int(m[1])),
            }

        def handle_starttag(
            self, tag: str, attrs: List[Tuple[str, Union[str, None]]]
        ) -> None:
            params = dict(attrs)

            if params.get("class") == "table2":
                self.inside_table = True
            elif not self.inside_table:
                return

            if tag == self.TR and (
                params.get("bgcolor") == "#F4F4F4" or params.get("bgcolor") == "#FFFFFF"
            ):
                self.inside_tr = True
                self.column_index = -1
                self.current_item = {"engine_url": self.url}
            elif not self.inside_tr:
                return

            if tag == self.TD:
                self.column_index += 1
                if self.column_index < len(self.columns):
                    self.column_name = self.columns[self.column_index]
                else:
                    self.column_name = None

            if self.column_name == "name" and tag == self.A and self.HREF in params:
                link = params["href"]
                if link is not None and link.endswith(".html"):
                    desc_link = self.url + link
                    self.current_item["desc_link"] = desc_link
                    self.current_item["_info_link"] = desc_link

        def handle_data(self, data: str) -> None:
            if self.column_name:
                if self.column_name in ["size", "seeds", "leech"]:
                    data = data.replace(",", "")
                elif self.column_name == "pub_date":
                    timestamp = -1
                    for pattern, calc in self.date_parsers.items():
                        m = re.match(pattern, data, re.IGNORECASE)
                        if m:
                            timestamp = int(calc(m).timestamp())
                            break
                    data = str(timestamp)
                self.current_item[self.column_name] = data.strip()
                self.column_name = None

        def handle_endtag(self, tag: str) -> None:
            if tag == "table":
                self.inside_table = False

            if self.inside_tr and tag == self.TR:
                self.inside_tr = False
                self.column_name = None
                if "desc_link" in self.current_item:
                    self.results.append(self.current_item.copy())
                    self.page_items += 1

    def _fetch_magnet_from_page(self, info_url: str) -> str:
        """Fetch magnet link from info page."""
        try:
            info_page = retrieve_url(info_url)
            magnet_match = re.search(r'href\s*=\s*"(magnet[^"]+)"', info_page)
            if magnet_match and magnet_match.groups():
                return magnet_match.groups()[0]
        except Exception as e:
            logger.warning(f"Failed to fetch magnet from {info_url}: {e}")
        return ""

    def search(self, query: str, cat: str = "all") -> None:
        """Performs search and returns magnet links"""
        query = query.replace("%20", "-")
        category = self.supported_categories[cat]

        for page in range(1, 5):
            page_url = f"{self.url}/search/{category}/{query}/seeds/{page}/"
            html = retrieve_url(page_url)
            parser = self.MyHtmlParser(self.url, self)
            parser.feed(html)
            parser.close()

            for result in parser.results:
                info_url = result.get("_info_link", "")
                magnet_link = ""

                if info_url:
                    magnet_link = self._fetch_magnet_from_page(info_url)

                if magnet_link:
                    result["link"] = magnet_link
                else:
                    result["link"] = info_url

                result.pop("_info_link", None)
                prettyPrinter(result)

            if parser.page_items < 20:
                break

    def download_torrent(self, info: str) -> None:
        """Handle magnet links and .torrent downloads."""
        import sys
        import os
        import tempfile
        import urllib.request

        if info.startswith("magnet:"):
            print(info + " " + info)
            sys.stdout.flush()
            return

        info_page = retrieve_url(info)
        magnet_match = re.search(r'href\s*=\s*"(magnet[^"]+)"', info_page)
        if magnet_match and magnet_match.groups():
            magnet = magnet_match.groups()[0]
            print(magnet + " " + info)
            sys.stdout.flush()
            return

        raise ValueError("Error: Could not find magnet link")
