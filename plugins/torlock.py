# VERSION: 2.29
# AUTHORS: Douman (custparasite@gmx.se)
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)
# MODIFIED: Returns magnet links in search results for WebUI compatibility

import re
import logging
import sys
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Any, Dict, List, Tuple, Union

from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class torlock:
    url = "https://www.torlock.com"
    name = "TorLock"
    supported_categories = {
        "all": "all",
        "anime": "anime",
        "software": "software",
        "games": "game",
        "movies": "movie",
        "music": "music",
        "tv": "television",
        "books": "ebooks",
    }

    def download_torrent(self, info: str) -> None:
        """Handle magnet links and .torrent downloads."""
        if info.startswith("magnet:"):
            print(info + " " + info)
            sys.stdout.flush()
            return

        print(download_file(info))

    class MyHtmlParser(HTMLParser):
        """Sub-class for parsing results"""

        def __init__(self, url: str, parent: "torlock") -> None:
            HTMLParser.__init__(self)
            self.url = url
            self.parent = parent
            self.article_found = False
            self.item_found = False
            self.item_bad = False
            self.current_item: Dict[str, Any] = {}
            self.item_name: Union[str, None] = None
            self.page_items = 0
            self.parser_class = {
                "td": "pub_date",
                "ts": "size",
                "tul": "seeds",
                "tdl": "leech",
            }

        def handle_starttag(
            self, tag: str, attrs: List[Tuple[str, Union[str, None]]]
        ) -> None:
            params = dict(attrs)

            if self.item_found:
                if tag == "td":
                    param_class = params.get("class")
                    if param_class is not None:
                        self.item_name = self.parser_class.get(param_class)
                        if self.item_name:
                            self.current_item[self.item_name] = ""

            elif self.article_found and tag == "a":
                link = params.get("href")
                if link is not None:
                    if link.startswith("/torrent"):
                        self.current_item["desc_link"] = "".join((self.url, link))
                        self.current_item["_info_link"] = self.url + link
                        self.current_item["_torrent_id"] = link.split("/")[2]
                        self.current_item["engine_url"] = self.url
                        self.item_found = True
                        self.item_name = "name"
                        self.current_item["name"] = ""
                        self.item_bad = "rel" in params and params["rel"] == "nofollow"

            elif tag == "article":
                self.article_found = True
                self.current_item = {}

        def handle_data(self, data: str) -> None:
            if self.item_name:
                self.current_item[self.item_name] += data

        def handle_endtag(self, tag: str) -> None:
            if tag == "article":
                self.article_found = False
            elif self.item_name and (tag in ("a", "td")):
                self.item_name = None
            elif self.item_found and tag == "tr":
                self.item_found = False
                if not self.item_bad:
                    try:
                        if self.current_item["pub_date"] == "Today":
                            date = datetime.now()
                        elif self.current_item["pub_date"] == "Yesterday":
                            date = datetime.now() - timedelta(days=1)
                        else:
                            date = datetime.strptime(
                                self.current_item["pub_date"], "%m/%d/%Y"
                            )
                        date = date.replace(hour=0, minute=0, second=0, microsecond=0)
                        self.current_item["pub_date"] = int(date.timestamp())
                    except Exception:
                        self.current_item["pub_date"] = -1

                    info_link = self.current_item.pop("_info_link", "")
                    torrent_id = self.current_item.pop("_torrent_id", "")

                    magnet_link = ""
                    if info_link:
                        magnet_link = self.parent._fetch_magnet_from_page(info_link)

                    if magnet_link:
                        self.current_item["link"] = magnet_link
                    else:
                        self.current_item["link"] = "".join(
                            (self.url, "/tor/", torrent_id, ".torrent")
                        )

                    prettyPrinter(self.current_item)
                    self.page_items += 1
                self.current_item = {}

    def _fetch_magnet_from_page(self, info_url: str) -> str:
        """Fetch magnet link from torrent info page."""
        try:
            html = retrieve_url(info_url)
            magnet_match = re.search(r'href\s*=\s*"(magnet:\?[^"]+)"', html)
            if magnet_match and magnet_match.groups():
                return magnet_match.groups()[0]
        except Exception as e:
            logger.debug(f"Failed to fetch magnet from {info_url}: {e}")
        return ""

    def search(self, query: str, cat: str = "all") -> None:
        """Performs search and returns magnet links"""
        query = query.replace("%20", "-")
        category = self.supported_categories[cat]

        for page in range(1, 5):
            parser = self.MyHtmlParser(self.url, self)
            page_url = (
                f"{self.url}/{category}/torrents/{query}.html?sort=seeds&page={page}"
            )
            html = retrieve_url(page_url)
            parser.feed(html)
            parser.close()
            if parser.page_items < 20:
                break
