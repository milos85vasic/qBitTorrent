"""
Core data models for the merge service.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ContentType(Enum):
    MOVIE = "movie"
    TV_SHOW = "tv_show"
    MUSIC = "music"
    GAME = "game"
    SOFTWARE = "software"
    BOOK = "book"
    OTHER = "other"


class QualityTier(Enum):
    SD = "sd"
    HD = "hd"
    FULL_HD = "full_hd"
    UHD_4K = "uhd_4k"
    UHD_8K = "uhd_8k"
    UNKNOWN = "unknown"


@dataclass
class TrackerSource:
    name: str
    url: str
    enabled: bool = True
    last_checked: Optional[datetime] = None
    health_status: str = "unknown"
    scrape_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
            "last_checked": self.last_checked.isoformat()
            if self.last_checked
            else None,
            "health_status": self.health_status,
            "scrape_url": self.scrape_url,
        }


@dataclass
class CanonicalIdentity:
    infohash: Optional[str] = None
    title: Optional[str] = None
    year: Optional[int] = None
    content_type: Optional[ContentType] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    resolution: Optional[str] = None
    codec: Optional[str] = None
    group: Optional[str] = None
    metadata_source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "infohash": self.infohash,
            "title": self.title,
            "year": self.year,
            "content_type": self.content_type.value if self.content_type else None,
            "season": self.season,
            "episode": self.episode,
            "resolution": self.resolution,
            "codec": self.codec,
            "group": self.group,
            "metadata_source": self.metadata_source,
        }


@dataclass
class SearchResult:
    name: str
    link: str
    size: str
    seeds: int
    leechers: int
    engine_url: str
    desc_link: Optional[str] = None
    pub_date: Optional[str] = None
    tracker: Optional[str] = None
    category: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "link": self.link,
            "size": self.size,
            "seeds": self.seeds,
            "leechers": self.leechers,
            "engine_url": self.engine_url,
            "desc_link": self.desc_link,
            "pub_date": self.pub_date,
            "tracker": self.tracker,
            "category": self.category,
        }


@dataclass
class MergedResult:
    canonical_identity: CanonicalIdentity
    original_results: List[SearchResult] = field(default_factory=list)
    total_seeds: int = 0
    total_leechers: int = 0
    best_quality: Optional[QualityTier] = None
    download_urls: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_source(self, result: SearchResult):
        self.original_results.append(result)
        self.total_seeds += result.seeds
        self.total_leechers += result.leechers
        if result.link not in self.download_urls:
            self.download_urls.append(result.link)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canonical_identity": self.canonical_identity.to_dict(),
            "sources": [
                {"tracker": r.tracker, "seeds": r.seeds, "leechers": r.leechers}
                for r in self.original_results
            ],
            "total_seeds": self.total_seeds,
            "total_leechers": self.total_leechers,
            "best_quality": self.best_quality.value if self.best_quality else None,
            "download_urls": self.download_urls,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SearchMetadata:
    search_id: str
    query: str
    category: str = "all"
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    total_results: int = 0
    merged_results: int = 0
    trackers_searched: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    status: str = "running"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "search_id": self.search_id,
            "query": self.query,
            "category": self.category,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "total_results": self.total_results,
            "merged_results": self.merged_results,
            "trackers_searched": self.trackers_searched,
            "errors": self.errors,
            "status": self.status,
        }


class SearchOrchestrator:
    def __init__(self):
        from .deduplicator import Deduplicator
        from .validator import TrackerValidator

        self.deduplicator = Deduplicator()
        self.validator = TrackerValidator()
        self._active_searches: Dict[str, SearchMetadata] = {}

    def _load_env(self):
        import os

        for path in [
            "/config/.env",
            os.path.expanduser("~/.qbit.env"),
            "/root/.qbit.env",
        ]:
            if os.path.isfile(path):
                try:
                    with open(path) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                k, v = k.strip(), v.strip().strip('"').strip("'")
                                if k and k not in os.environ:
                                    os.environ[k] = v
                except Exception:
                    pass

    async def search(
        self,
        query: str,
        category: str = "all",
        enable_metadata: bool = True,
        validate_trackers: bool = True,
    ) -> SearchMetadata:
        import uuid

        search_id = str(uuid.uuid4())
        metadata = SearchMetadata(search_id=search_id, query=query, category=category)
        self._active_searches[search_id] = metadata

        try:
            trackers = self._get_enabled_trackers()
            metadata.trackers_searched = [t.name for t in trackers]

            all_results = []
            for tracker in trackers:
                try:
                    results = await self._search_tracker(tracker, query, category)
                    all_results.extend(results)
                    metadata.total_results += len(results)
                except Exception as e:
                    metadata.errors.append(f"{tracker.name}: {str(e)}")

            merged = self.deduplicator.merge_results(all_results)
            metadata.merged_results = len(merged)
            metadata.status = "completed"
            metadata.completed_at = datetime.utcnow()
        except Exception as e:
            metadata.status = "failed"
            metadata.errors.append(str(e))
            metadata.completed_at = datetime.utcnow()

        return metadata

    def _get_enabled_trackers(self) -> List[TrackerSource]:
        import os

        trackers = []
        if os.getenv("RUTRACKER_USERNAME") and os.getenv("RUTRACKER_PASSWORD"):
            trackers.append(
                TrackerSource(
                    name="rutracker", url="https://rutracker.org", enabled=True
                )
            )
        if os.getenv("KINOZAL_USERNAME") and os.getenv("KINOZAL_PASSWORD"):
            trackers.append(
                TrackerSource(name="kinozal", url="https://kinozal.tv", enabled=True)
            )
        if os.getenv("NNMCLUB_COOKIES"):
            trackers.append(
                TrackerSource(name="nnmclub", url="https://nnmclub.to", enabled=True)
            )
        if not trackers:
            trackers = [
                TrackerSource(
                    name="rutracker", url="https://rutracker.org", enabled=True
                ),
                TrackerSource(name="kinozal", url="https://kinozal.tv", enabled=True),
                TrackerSource(name="nnmclub", url="https://nnmclub.to", enabled=True),
            ]
        return trackers

    async def _search_tracker(
        self, tracker: TrackerSource, query: str, category: str
    ) -> List[SearchResult]:
        import logging

        logger = logging.getLogger(__name__)
        results = []

        try:
            self._load_env()
            if tracker.name == "rutracker":
                results = await self._search_rutracker(query, category)
            elif tracker.name == "kinozal":
                results = await self._search_kinozal(query, category)
            elif tracker.name == "nnmclub":
                results = await self._search_nnmclub(query, category)
        except Exception as e:
            logger.error(f"Error searching {tracker.name}: {e}")

        return results

    async def _search_rutracker(self, query: str, category: str) -> List[SearchResult]:
        import os
        import aiohttp
        import re
        import html
        from urllib.parse import urlencode

        results = []
        username = os.getenv("RUTRACKER_USERNAME")
        password = os.getenv("RUTRACKER_PASSWORD")

        if not username or not password:
            return results

        try:
            base_url = (
                os.getenv("RUTRACKER_MIRRORS", "https://rutracker.org")
                .split(",")[0]
                .strip()
            )
            search_url = (
                f"{base_url}/forum/tracker.php?{urlencode({'nm': query, 'fo': 1})}"
            )

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/forum/login.php",
                    data={
                        "login_username": username,
                        "login_password": password,
                        "login": "Вход",
                    },
                ) as resp:
                    cookies = resp.cookies

                async with session.get(search_url, cookies=cookies) as resp:
                    html_content = await resp.text()

                results = self._parse_rutracker_html(html_content, base_url)
        except Exception:
            pass

        return results

    def _parse_rutracker_html(
        self, html_content: str, base_url: str
    ) -> List[SearchResult]:
        import re
        import html

        results = []
        row_pattern = re.compile(r'<tr[^>]*data-topic_id="(\d+)"[^>]*>(.*?)</tr>', re.S)

        for row_match in row_pattern.finditer(html_content):
            try:
                topic_id = row_match.group(1)
                row_html = row_match.group(2)

                title_match = re.search(
                    r'<a[^>]*href="[^"]*viewtopic\.php\?t=\d+[^"]*"[^>]*>([^<]+)</a>',
                    row_html,
                )
                if not title_match:
                    title_match = re.search(
                        r'class="tTitle"[^>]*>([^<]+)</a>', row_html
                    )
                if title_match:
                    title = html.unescape(title_match.group(1).strip())
                else:
                    title = f"Topic {topic_id}"

                size_val = 0
                size_match = re.search(r">([\d.]+\s*[KMGT]?B?)<", row_html)
                if size_match:
                    size_val = self._parse_size_string(size_match.group(1).strip())

                seeds = 0
                seeds_match = re.search(r"sdTorrent.*?>(\d+)", row_html)
                if seeds_match:
                    seeds = int(seeds_match.group(1))

                leechers = 0
                leech_match = re.search(r"leechmed.*?>(\d+)", row_html)
                if leech_match:
                    leechers = int(leech_match.group(1))

                results.append(
                    SearchResult(
                        name=title,
                        size=self._format_size(size_val),
                        seeds=seeds,
                        leechers=leechers,
                        link=f"{base_url}/forum/dl.php?t={topic_id}",
                        desc_link=f"{base_url}/forum/viewtopic.php?t={topic_id}",
                        tracker="rutracker",
                        engine_url=base_url,
                    )
                )
            except Exception:
                continue

        return results

    def _parse_size_string(self, size_str: str) -> int:
        import re

        size_str = size_str.strip().upper()
        multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        match = re.match(r"([\d.]+)\s*([KMGT]?B)", size_str)
        if match:
            mult = multipliers.get(match.group(2), 1)
        return int(float(match.group(1)) * mult)
        return 0

    def _format_size(self, bytes_size: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} PB"

    async def _search_kinozal(self, query: str, category: str) -> List[SearchResult]:
        import os
        import aiohttp
        from urllib.parse import urlencode

        results = []
        username = os.getenv("KINOZAL_USERNAME")
        password = os.getenv("KINOZAL_PASSWORD")

        if not username or not password:
            return results

        try:
            base_url = (
                os.getenv("KINOZAL_MIRRORS", "https://kinozal.tv").split(",")[0].strip()
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/browse.php", data={"s": query}
                ) as resp:
                    html = await resp.text()
            results = self._parse_kinozal_html(html, base_url)
        except Exception:
            pass

        return results

    def _parse_kinozal_html(
        self, html_content: str, base_url: str
    ) -> List[SearchResult]:
        import re
        import html

        results = []
        row_pattern = re.compile(
            r'<tr[^>]*class="tRow"[^>]*id="tr_\d+"[^>]*>(.*?)</tr>', re.S
        )

        for row_match in row_pattern.finditer(html_content):
            try:
                row_html = row_match.group(1)
                title_match = re.search(
                    r'<a[^>]*href="[^"]*?t=(\d+)[^"]*"[^>]*>([^<]+)</a>', row_html
                )
                if not title_match:
                    continue

                topic_id = title_match.group(1)
                title = html.unescape(title_match.group(2).strip())

                size_match = re.search(r"<td[^>]*>([\d.]+\s*[KMGT]B?)</td>", row_html)
                size = size_match.group(1) if size_match else "0 B"

                seeds = 0
                seeds_match = re.search(r"<td[^>]*>(\d+)</td>.*?seed", row_html, re.S)
                if seeds_match:
                    seeds = int(seeds_match.group(1))

                results.append(
                    SearchResult(
                        name=title,
                        size=size,
                        seeds=seeds,
                        leechers=0,
                        link=f"{base_url}/get/torrent/{topic_id}.torrent",
                        desc_link=f"{base_url}/description.php?p={topic_id}",
                        tracker="kinozal",
                        engine_url=base_url,
                    )
                )
            except Exception:
                continue

        return results

    async def _search_nnmclub(self, query: str, category: str) -> List[SearchResult]:
        import os
        import aiohttp
        from urllib.parse import urlencode

        results = []
        cookies = os.getenv("NNMCLUB_COOKIES")

        if not cookies:
            return results

        try:
            base_url = (
                os.getenv("NNMCLUB_MIRRORS", "https://nnmclub.to").split(",")[0].strip()
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{base_url}/forum/tracker.php?{urlencode({'nm': query})}",
                    cookies={"cookies": cookies},
                ) as resp:
                    html = await resp.text()
            results = self._parse_nnmclub_html(html, base_url)
        except Exception:
            pass

        return results

    def _parse_nnmclub_html(
        self, html_content: str, base_url: str
    ) -> List[SearchResult]:
        import re
        import html

        results = []
        row_pattern = re.compile(r'<tr[^>]*id="tr_\d+"[^>]*>(.*?)</tr>', re.S)

        for row_match in row_pattern.finditer(html_content):
            try:
                row_html = row_match.group(1)
                title_match = re.search(
                    r'<a[^>]*href="[^"]*viewtopic\.php\?t=(\d+)[^"]*"[^>]*>([^<]+)</a>',
                    row_html,
                )
                if not title_match:
                    continue

                topic_id = title_match.group(1)
                title = html.unescape(title_match.group(2).strip())

                size_match = re.search(r"<td[^>]*>([\d.]+\s*[KMGT]?B?)</td>", row_html)
                size = size_match.group(1) if size_match else "0 B"

                seeds = 0
                seeds_match = re.search(r"seed.*?>(\d+)", row_html)
                if seeds_match:
                    seeds = int(seeds_match.group(1))

                results.append(
                    SearchResult(
                        name=title,
                        size=size,
                        seeds=seeds,
                        leechers=0,
                        link=f"{base_url}/forum/dl.php?t={topic_id}",
                        desc_link=f"{base_url}/forum/viewtopic.php?t={topic_id}",
                        tracker="nnmclub",
                        engine_url=base_url,
                    )
                )
            except Exception:
                continue

        return results

    def get_search_status(self, search_id: str) -> Optional[SearchMetadata]:
        return self._active_searches.get(search_id)

    def get_active_searches(self) -> List[SearchMetadata]:
        return list(self._active_searches.values())
