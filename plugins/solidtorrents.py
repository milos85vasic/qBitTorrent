# VERSION: 2.9
# AUTHORS: nKlido
# NOTE: Site currently experiencing issues (solidtorrents.to / bitsearch.to)

from datetime import datetime
from html.parser import HTMLParser
from typing import Dict, List, Mapping, Tuple, Union

from helpers import retrieve_url
from novaprinter import prettyPrinter


class solidtorrents:
    url = "https://solidtorrents.to"
    alt_url = "https://bitsearch.to"
    name = "Solid Torrents"
    supported_categories = {"all": "all", "music": "Audio", "books": "eBook"}

    class TorrentInfoParser(HTMLParser):
        def __init__(self, url: str) -> None:
            HTMLParser.__init__(self)
            self.url = url
            self.foundResult = False
            self.foundTitle = False
            self.parseTitle = False
            self.foundStats = False
            self.parseSeeders = False
            self.parseLeechers = False
            self.parseSize = False
            self.parseDate = False
            self.column = 0
            self.torrentReady = False
            self.totalResults = 0

            self.torrent_info = self.empty_torrent_info()

        def empty_torrent_info(self) -> Dict[str, object]:
            return {
                "link": "",
                "name": "",
                "size": "-1",
                "seeds": "-1",
                "leech": "-1",
                "engine_url": self.url,
                "desc_link": "",
                "pub_date": -1,
            }

        def handle_starttag(self, tag: str, attrs: List[Tuple[str, Union[str, None]]]) -> None:
            def getStr(d: Mapping[str, Union[str, None]], key: str) -> str:
                value = d.get(key, "")
                return value if value is not None else ""

            params = dict(attrs)

            if "search-result" in getStr(params, "class"):
                self.foundResult = True
                return

            if self.foundResult and ("title" in getStr(params, "class")) and (tag == "h5"):
                self.foundTitle = True

            if self.foundTitle and (tag == "a"):
                self.torrent_info["desc_link"] = self.url + getStr(params, "href")
                self.parseTitle = True

            if self.foundResult and ("stats" in getStr(params, "class")):
                self.foundStats = True
                self.column = -1

            if self.foundStats and (tag == "div"):
                self.column = self.column + 1

                if self.column == 2:
                    self.parseSize = True

            if self.foundStats and (tag == "font") and (self.column == 3):
                self.parseSeeders = True

            if self.foundStats and (tag == "font") and (self.column == 4):
                self.parseLeechers = True

            if self.foundStats and (tag == "div") and (self.column == 5):
                self.parseDate = True

            if self.foundResult and ("dl-magnet" in getStr(params, "class")) and (tag == "a"):
                self.torrent_info["link"] = params.get("href")
                self.foundResult = False
                self.torrentReady = True

        def handle_endtag(self, tag: str) -> None:
            if self.torrentReady:
                prettyPrinter(self.torrent_info)
                self.torrentReady = False
                self.torrent_info = self.empty_torrent_info()
                self.totalResults += 1

        def handle_data(self, data: str) -> None:

            if self.parseTitle:
                if bool(data.strip()) and data != "\n":
                    self.torrent_info["name"] = data
                self.parseTitle = False
                self.foundTitle = False

            if self.parseSize:
                self.torrent_info["size"] = data
                self.parseSize = False

            if self.parseSeeders:
                self.torrent_info["seeds"] = data
                self.parseSeeders = False

            if self.parseLeechers:
                self.torrent_info["leech"] = data
                self.parseLeechers = False

            if self.parseDate:
                try:
                    # I chose not to use strptime here because it depends on user's locale
                    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
                    [month, day, year] = data.replace(",", "").lower().split()
                    date = datetime(int(year), int(months.index(month) + 1), int(day))
                    self.torrent_info["pub_date"] = int(date.timestamp())
                except Exception:
                    self.torrent_info["pub_date"] = -1
                self.parseDate = False
                self.foundStats = False

    def request(self, searchTerm: str, category: str, page: int = 1) -> str:
        return retrieve_url(
            self.url + "/search?q=" + searchTerm + "&category=" + category + "&sort=seeders&sort=desc&page=" + str(page)
        )

    def search(self, what: str, cat: str = "all") -> None:
        category = self.supported_categories[cat]

        for page in range(1, 5):
            parser = self.TorrentInfoParser(self.url)
            try:
                html = self.request(what, category, page)
                parser.feed(html)
                parser.close()
            except Exception as e:
                # Site may be down, silently fail
                break
            if parser.totalResults < 15:
                break

    def download_torrent(self, url):
        """Handle magnet links - just pass through."""
        import sys

        if url.startswith("magnet:"):
            print(url + " " + url)
            sys.stdout.flush()
        else:
            # Fallback to direct download
            import tempfile
            import urllib.request
            import os

            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = response.read()

                fd, path = tempfile.mkstemp(suffix=".torrent")
                with os.fdopen(fd, "wb") as f:
                    f.write(data)

                os.chmod(path, 0o644)
                print(path + " " + url)
                sys.stdout.flush()
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
