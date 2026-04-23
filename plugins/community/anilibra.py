# VERSION: 1.0
# AUTHORS: qBittorrent Community

import re
import time
from urllib.parse import quote, unquote
from novaprinter import prettyPrinter
from helpers import retrieve_url


class anilibra:
    """AniLibra anime torrent search engine plugin."""

    url = "https://anilibria.tv"
    name = "AniLibra"
    supported_categories = {"all": "0", "anime": "1"}

    def search(self, what, cat="all"):
        """Search for torrents."""
        what = unquote(what)

        # Build search URL
        search_term = quote(what)
        url = f"{self.url}/public/api/index.php?search={search_term}"

        try:
            html = retrieve_url(url)
            self._parse_results(html)
        except Exception as e:
            print(f"Search error: {e}", file=__import__("sys").stderr)

    def _parse_results(self, html):
        """Parse search results from API response."""
        import json

        try:
            data = json.loads(html)
            # Upstream occasionally returns {"data": null} on empty
            # search → `for item in None` would crash. Guard so the
            # plugin exits cleanly with 0 results instead of propagating
            # a NoneType iteration error up to our subprocess wrapper.
            if not isinstance(data, dict):
                return
            items = data.get("data") or []
            if not isinstance(items, list):
                return
            if items:
                for item in items:
                    try:
                        name = item.get("names", {}).get("ru", item.get("names", {}).get("en", "Unknown"))
                        series_id = item.get("id", "")

                        # Build magnet link from torrent data
                        torrents = item.get("torrents", [])
                        for torrent in torrents:
                            try:
                                quality = torrent.get("quality", "unknown")
                                series = torrent.get("series", "")
                                size = torrent.get("size", "0")
                                seeders = torrent.get("seeders", "0")
                                leechers = torrent.get("leechers", "0")
                                magnet = torrent.get("magnet", "")

                                if magnet:
                                    full_name = f"{name} [{quality}] {series}".strip()

                                    result = {
                                        "link": magnet,
                                        "name": full_name,
                                        "size": str(size),
                                        "seeds": str(seeders),
                                        "leech": str(leechers),
                                        "engine_url": self.url,
                                        "desc_link": f"{self.url}/release/{series_id}.html",
                                        "pub_date": str(int(time.time())),
                                    }
                                    prettyPrinter(result)
                            except Exception as e:
                                continue
                    except Exception as e:
                        continue
        except json.JSONDecodeError:
            # Fallback to HTML parsing if API fails
            pass

    def download_torrent(self, url):
        """AniLibra returns magnet links directly."""
        import sys

        print(url + " " + url)
        sys.stdout.flush()


# Module reference
anilibra = anilibra

if __name__ == "__main__":
    a = anilibra()
    a.search("naruto", "anime")
