"""
Core data models for the merge service.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class ContentType(Enum):
    MOVIE = "movie"
    TV_SHOW = "tv"
    ANIME = "anime"
    MUSIC = "music"
    AUDIOBOOK = "audiobook"
    GAME = "game"
    SOFTWARE = "software"
    EBOOK = "ebook"
    OTHER = "other"
    UNKNOWN = "unknown"


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
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
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
    freeleech: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = {
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
            "freeleech": self.freeleech,
        }
        if self.freeleech and self.tracker:
            d["tracker_display"] = f"{self.tracker} [free]"
        elif self.tracker:
            d["tracker_display"] = self.tracker
        else:
            d["tracker_display"] = None
        return d


@dataclass
class MergedResult:
    canonical_identity: CanonicalIdentity
    original_results: List[SearchResult] = field(default_factory=list)
    total_seeds: int = 0
    total_leechers: int = 0
    best_quality: Optional[QualityTier] = None
    download_urls: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

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
                {"tracker": r.tracker, "seeds": r.seeds, "leechers": r.leechers} for r in self.original_results
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
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
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
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_results": self.total_results,
            "merged_results": self.merged_results,
            "trackers_searched": self.trackers_searched,
            "errors": self.errors,
            "status": self.status,
        }


PUBLIC_TRACKERS = {
    "academictorrents": "https://academictorrents.com/",
    "ali213": "http://down.ali213.net/",
    "anilibra": "https://anilibria.tv",
    "audiobookbay": "http://theaudiobookbay.se/",
    "bitru": "https://bitru.org",
    "bt4g": "https://bt4gprx.com/",
    "btsow": "https://btsow.motorcycles",
    "extratorrent": "https://extratorrent.st",
    "eztv": "https://eztv.re",
    "gamestorrents": "https://www.gamestorrents.fm",
    "glotorrents": "https://glodls.to/",
    "kickass": "https://katcr.to/",
    "limetorrents": "https://www.limetorrents.lol",
    "linuxtracker": "http://linuxtracker.org",
    "megapeer": "https://megapeer.vip",
    "nyaa": "https://nyaa.si",
    "one337x": "https://1337x.to",
    "pctorrent": "https://pctorrent.ru",
    "piratebay": "https://thepiratebay.org",
    "pirateiro": "https://pirateiro.io/",
    "rockbox": "https://rawkbawx.rocks/",
    "rutor": "https://rutor.info/",
    "snowfl": "https://snowfl.com/",
    "solidtorrents": "https://solidtorrents.to",
    "therarbg": "https://therarbg.com",
    "tokyotoshokan": "http://tokyotosho.info",
    "torlock": "https://www.torlock.com",
    "torrentdownload": "https://www.torrentdownload.info/",
    "torrentfunk": "https://www.torrentfunk.com",
    "torrentgalaxy": "https://torrentgalaxy.to",
    "torrentkitty": "https://www.torrentkitty.tv",
    "torrentproject": "https://torrentproject.com.se",
    "torrentscsv": "https://torrents-csv.com",
    "xfsub": "https://www.xfsub.com",
    "yihua": "https://www.yihua.biz",
    "yourbittorrent": "https://yourbittorrent.com/",
    "yts": "https://movies-api.accel.li",
}

PRIVATE_TRACKERS = {
    "rutracker": "https://rutracker.org",
    "kinozal": "https://kinozal.tv",
    "nnmclub": "https://nnm-club.me",
    "iptorrents": "https://iptorrents.com",
}


class SearchOrchestrator:
    def __init__(self):
        import asyncio
        from .deduplicator import Deduplicator
        from .validator import TrackerValidator

        self.deduplicator = Deduplicator()
        self.validator = TrackerValidator()

        # Bounded, self-expiring stores so long-running processes don't leak
        # memory.  Previously these were plain dicts that grew without bound
        # and kept entries forever.
        from cachetools import TTLCache as _TTLCache
        import os as _os_ttl

        _max_searches = max(1, int(_os_ttl.getenv("MAX_ACTIVE_SEARCHES", "256")))
        _ttl = max(1, int(_os_ttl.getenv("ACTIVE_SEARCH_TTL_SECONDS", "3600")))
        self._active_searches: "TTLCache[str, SearchMetadata]" = _TTLCache(
            maxsize=_max_searches, ttl=_ttl
        )
        self._tracker_sessions: Dict[str, Any] = {}
        self._last_merged_results: "TTLCache[str, tuple]" = _TTLCache(
            maxsize=_max_searches, ttl=_ttl
        )
        self._tracker_results: Dict[str, Dict[str, List[Any]]] = {}
        # Bounded tracker fan-out.  Without this, asyncio.gather spawned one
        # task per tracker (~40+) with no backpressure, which let subprocess
        # spawns and aiohttp sessions starve the event loop under load.
        import os as _os

        self._max_concurrent_trackers: int = max(
            1, int(_os.getenv("MAX_CONCURRENT_TRACKERS", "5"))
        )
        # `_inflight_count` is an instrument for tests and Phase 6 metrics.
        # It is only meaningful while a search is running.
        self._inflight_count: int = 0

    def _load_env(self):
        import logging

        logger = logging.getLogger(__name__)
        from config import load_env

        try:
            load_env()
        except Exception as e:
            logger.debug(f"config.load_env() failed, falling back to manual parsing: {e}")
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
                    except Exception as e:
                        logger.debug(f"Could not load env from {path}: {e}")

    def start_search(
        self,
        query: str,
        category: str = "all",
        enable_metadata: bool = True,
        validate_trackers: bool = True,
    ) -> SearchMetadata:
        """Kick off a search and return metadata synchronously.

        This does NOT block on tracker fan-out — use ``_run_search`` as an
        asyncio task to populate results as they stream in.  The returned
        metadata is immediately available at ``get_search_status`` and in
        ``_active_searches`` so SSE consumers can attach before any
        tracker completes.
        """
        import uuid

        search_id = str(uuid.uuid4())
        metadata = SearchMetadata(search_id=search_id, query=query, category=category)
        metadata.status = "running"
        self._active_searches[search_id] = metadata
        self._tracker_results[search_id] = {}
        # Seed a mutable placeholder so SSE clients can read partial
        # merged/all_results as trackers complete.
        self._last_merged_results[search_id] = ([], [])
        return metadata

    async def _run_search(
        self,
        search_id: str,
        query: str,
        category: str = "all",
    ) -> None:
        """Execute the tracker fan-out for a previously-started search.

        This is the body of the old monolithic ``search()`` method, but
        it pushes per-tracker results into ``_tracker_results[search_id]``
        immediately as each tracker finishes so SSE streams them in real
        time.  At the end it runs a single dedup pass and flips the
        metadata to ``completed``/``failed``.
        """
        import asyncio
        import logging

        logger = logging.getLogger(__name__)
        metadata = self._active_searches.get(search_id)
        if metadata is None:
            return

        try:
            trackers = self._get_enabled_trackers()
            metadata.trackers_searched = [t.name for t in trackers]

            async def _search_one(tracker):
                try:
                    results = await self._search_tracker(tracker, query, category)
                    logger.info(f"Tracker {tracker.name}: {len(results)} results for '{query}'")
                    # Push as soon as the tracker is done so SSE can see it.
                    self._tracker_results[search_id][tracker.name] = results
                    # Bump running totals for SSE results_update event.
                    metadata.total_results += len(results)
                    return tracker.name, results, None
                except Exception as e:
                    logger.error(f"Tracker {tracker.name} error: {e}")
                    return tracker.name, [], str(e)

            semaphore = asyncio.Semaphore(self._max_concurrent_trackers)

            async def _bounded(tracker):
                async with semaphore:
                    self._inflight_count += 1
                    try:
                        return await _search_one(tracker)
                    finally:
                        self._inflight_count -= 1

            search_results = await asyncio.gather(*[_bounded(t) for t in trackers])

            all_results = []
            for name, results, error in search_results:
                all_results.extend(results)
                if error:
                    metadata.errors.append(f"{name}: {error}")

            merged = self.deduplicator.merge_results(all_results)
            metadata.merged_results = len(merged)
            self._last_merged_results[search_id] = (merged, all_results)
            metadata.status = "completed"
            metadata.completed_at = datetime.now(timezone.utc)
        except Exception as e:
            metadata.status = "failed"
            metadata.errors.append(str(e))
            metadata.completed_at = datetime.now(timezone.utc)

    async def search(
        self,
        query: str,
        category: str = "all",
        enable_metadata: bool = True,
        validate_trackers: bool = True,
    ) -> SearchMetadata:
        """Blocking variant (legacy entry-point) — runs start + run in one
        call and waits for full completion.  Kept for the scheduler and
        for tests that expect the old synchronous-looking behaviour.
        """
        metadata = self.start_search(
            query=query,
            category=category,
            enable_metadata=enable_metadata,
            validate_trackers=validate_trackers,
        )
        # total_results is bumped incrementally inside _run_search now, so
        # reset it first — the legacy callers expect the final number.
        metadata.total_results = 0
        await self._run_search(metadata.search_id, query, category)
        return metadata

    def _get_enabled_trackers(self) -> List[TrackerSource]:
        import os

        trackers = []
        if os.getenv("RUTRACKER_USERNAME") and os.getenv("RUTRACKER_PASSWORD"):
            trackers.append(TrackerSource(name="rutracker", url="https://rutracker.org", enabled=True))
        if os.getenv("KINOZAL_USERNAME") and os.getenv("KINOZAL_PASSWORD"):
            trackers.append(TrackerSource(name="kinozal", url="https://kinozal.tv", enabled=True))
        if os.getenv("NNMCLUB_COOKIES"):
            trackers.append(TrackerSource(name="nnmclub", url="https://nnm-club.me", enabled=True))
        if os.getenv("IPTORRENTS_USERNAME") and os.getenv("IPTORRENTS_PASSWORD"):
            trackers.append(TrackerSource(name="iptorrents", url="https://iptorrents.com", enabled=True))

        for name, url in sorted(PUBLIC_TRACKERS.items()):
            trackers.append(TrackerSource(name=name, url=url, enabled=True))

        return trackers

    async def _search_tracker(self, tracker: TrackerSource, query: str, category: str) -> List[SearchResult]:
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
            elif tracker.name == "iptorrents":
                results = await self._search_iptorrents(query, category)
            elif tracker.name in PUBLIC_TRACKERS:
                results = await self._search_public_tracker(tracker.name, query, category)
        except Exception as e:
            logger.error(f"Error searching {tracker.name}: {e}")

        return results

    async def _search_public_tracker(self, tracker_name: str, query: str, category: str) -> List[SearchResult]:
        import asyncio
        import json
        import logging

        logger = logging.getLogger(__name__)
        results = []

        script = (
            "import sys, os, json as _json\n"
            "sys.path.insert(0, '/config/qBittorrent/nova3')\n"
            "os.chdir('/config/qBittorrent/nova3')\n"
            "import importlib\n"
            "_results = []\n"
            "try:\n"
            "    import engines.novaprinter as _np\n"
            "    def _capture(d):\n"
            "        _results.append(d)\n"
            "    _np.prettyPrinter = _capture\n"
            f"    _mod = importlib.import_module('engines.{tracker_name}')\n"
            f"    _cls = getattr(_mod, '{tracker_name}')\n"
            "    _engine = _cls()\n"
            f"    _engine.search({query!r}, {category!r})\n"
            "except Exception as _e:\n"
            "    print(_json.dumps({'error': str(_e)}), file=sys.stderr)\n"
            "print(_json.dumps(_results))\n"
        )

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                "-c",
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

            if proc.returncode != 0:
                err = stderr.decode(errors="replace").strip()
                if err:
                    logger.debug(f"Plugin {tracker_name} stderr: {err}")
                return results

            raw = stdout.decode(errors="replace").strip()
            if not raw:
                return results

            plugin_results = json.loads(raw)
            if isinstance(plugin_results, dict) and "error" in plugin_results:
                logger.debug(f"Plugin {tracker_name} error: {plugin_results['error']}")
                return results

            for r in plugin_results:
                try:
                    results.append(
                        SearchResult(
                            name=r.get("name", ""),
                            size=r.get("size", "0 B"),
                            seeds=int(r.get("seeds", 0)),
                            leechers=int(r.get("leech", 0)),
                            link=r.get("link", ""),
                            desc_link=r.get("desc_link", ""),
                            tracker=tracker_name,
                            engine_url=PUBLIC_TRACKERS.get(tracker_name, ""),
                        )
                    )
                except Exception as e:
                    logger.debug(f"Skipping malformed {tracker_name} result: {e}")
                    continue

        except asyncio.TimeoutError:
            logger.debug(f"Plugin {tracker_name} timed out")
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Plugin {tracker_name} execution error: {e}")
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass

        return results

    async def _search_rutracker(self, query: str, category: str) -> List[SearchResult]:
        import os
        import aiohttp
        import re
        import html
        import logging
        from urllib.parse import urlencode

        logger = logging.getLogger(__name__)
        results = []
        username = os.getenv("RUTRACKER_USERNAME")
        password = os.getenv("RUTRACKER_PASSWORD")

        if not username or not password:
            return []

        try:
            base_url = os.getenv("RUTRACKER_MIRRORS", "https://rutracker.org").split(",")[0].strip()
            search_url = f"{base_url}/forum/tracker.php?{urlencode({'nm': query, 'fo': 1})}"

            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{base_url}/forum/login.php",
                    data={
                        "login_username": username,
                        "login_password": password,
                        "login": "Вход",
                    },
                ) as resp:
                    cookies = resp.cookies

                cookie_dict = {c.key: c.value for c in cookies.values()}
                self._tracker_sessions["rutracker"] = {
                    "cookies": cookie_dict,
                    "base_url": base_url,
                }

                async with session.get(search_url, cookies=cookies) as resp:
                    html_content = await resp.text()

                results = self._parse_rutracker_html(html_content, base_url)
        except Exception as e:
            logger.error(f"RuTracker search error: {e}")

        return results

    def _parse_rutracker_html(self, html_content: str, base_url: str) -> List[SearchResult]:
        import re
        import html

        results = []

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

        for thread in re_threads.findall(html_content):
            match = re_torrent_data.search(thread)
            if match:
                try:
                    d = match.groupdict()
                    title = html.unescape(d["title"])
                    topic_id = d["id"]
                    size_val = int(d.get("size", 0) or 0)
                    seeds = int(d.get("seeds", 0) or 0)
                    if seeds < 0:
                        seeds = 0
                    leechers = int(d.get("leech", 0) or 0)

                    results.append(
                        SearchResult(
                            name=title,
                            size=self._format_size(size_val) if size_val else "0 B",
                            seeds=seeds,
                            leechers=leechers,
                            link=f"{base_url}/forum/dl.php?t={topic_id}",
                            desc_link=f"{base_url}/forum/viewtopic.php?t={topic_id}",
                            tracker="rutracker",
                            engine_url=base_url,
                        )
                    )
                except Exception as e:
                    logger.debug(f"Skipping malformed RuTracker result: {e}")
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
        if bytes_size == 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} PB"

    async def _search_kinozal(self, query: str, category: str) -> List[SearchResult]:
        import gzip
        import os
        import logging
        import aiohttp
        from urllib.parse import urlencode

        logger = logging.getLogger(__name__)
        results = []
        username = os.getenv("KINOZAL_USERNAME")
        password = os.getenv("KINOZAL_PASSWORD")

        if not username or not password:
            logger.warning("Kinozal credentials not configured")
            return []

        try:
            base_url = os.getenv("KINOZAL_MIRRORS", "https://kinozal.tv").split(",")[0].strip()
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                login_data = urlencode({"username": username, "password": password}, encoding="cp1251")
                async with session.post(
                    f"{base_url}/takelogin.php",
                    data=login_data,
                    allow_redirects=False,
                ) as login_resp:
                    if login_resp.status not in (200, 301, 302):
                        logger.error(f"Kinozal login failed: HTTP {login_resp.status}")
                        return []
                    cookie_dict = {c.key: c.value for c in login_resp.cookies.values()}

                async with session.get(
                    f"{base_url}/browse.php",
                    params={"s": query},
                    cookies=cookie_dict,
                ) as resp:
                    raw = await resp.read()
                    if raw.startswith(b"\x1f\x8b\x08"):
                        raw = gzip.decompress(raw)
                    html = raw.decode("cp1251")
                    for c in resp.cookies.values():
                        cookie_dict[c.key] = c.value

                self._tracker_sessions["kinozal"] = {
                    "cookies": cookie_dict,
                    "base_url": base_url,
                }
            results = self._parse_kinozal_html(html, base_url)
            logger.info(f"Kinozal search '{query}': {len(results)} results")
        except Exception as e:
            logger.error(f"Kinozal search error: {e}")

        return results

    def _parse_kinozal_html(self, html_content: str, base_url: str) -> List[SearchResult]:
        import re
        from html import unescape

        results = []
        torrent_re = re.compile(
            r'nam"><a\s+?href="/(?P<desc_link>.+?)"\s+?class="r\d">(?P<name>.+?)'
            r"</a>.+?s\'>.+?s\'>(?P<size>.+?)<.+?sl_s\'>(?P<seeds>\d+?)<.+?sl_p\'"
            r">(?P<leech>\d+?)<.+?s\'>(?P<pub_date>.+?)</td>",
            re.S,
        )
        cyrillic_table = str.maketrans({"Т": "T", "Г": "G", "М": "M", "К": "K", "Б": "B"})
        url_dl = base_url.replace("//", "//dl.")

        for tor in torrent_re.finditer(html_content):
            try:
                topic_id = tor.group("desc_link").split("=")[-1]
                results.append(
                    SearchResult(
                        name=unescape(tor.group("name")),
                        size=tor.group("size").translate(cyrillic_table),
                        seeds=int(tor.group("seeds")),
                        leechers=int(tor.group("leech")),
                        link=f"{url_dl}download.php?id={topic_id}",
                        desc_link=f"{base_url}{tor.group('desc_link')}",
                        tracker="kinozal",
                        engine_url=base_url,
                    )
                )
            except Exception as e:
                logger.debug(f"Skipping malformed Kinozal result: {e}")
                continue

        return results

    async def _search_nnmclub(self, query: str, category: str) -> List[SearchResult]:
        import os
        import logging
        import aiohttp
        from urllib.parse import urlencode

        logger = logging.getLogger(__name__)
        results = []
        cookies_raw = os.getenv("NNMCLUB_COOKIES")

        if not cookies_raw:
            return []

        cookie_jar = {}
        for pair in cookies_raw.split(";"):
            pair = pair.strip()
            if "=" in pair:
                name, value = pair.split("=", 1)
                cookie_jar[name.strip()] = value.strip()

        if "phpbb2mysql_4_sid" not in cookie_jar:
            return []

        try:
            base_url = os.getenv("NNMCLUB_MIRRORS", "https://nnm-club.me").split(",")[0].strip()
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{base_url}/forum/tracker.php?{urlencode({'nm': query, 'f': '-1'})}",
                    cookies=cookie_jar,
                ) as resp:
                    raw_bytes = await resp.read()
                    html = raw_bytes.decode("cp1251", "ignore")
                self._tracker_sessions["nnmclub"] = {
                    "cookies": cookie_jar,
                    "base_url": base_url,
                }
            results = self._parse_nnmclub_html(html, base_url)
        except Exception as e:
            logger.error(f"NNMClub search error: {e}")

        return results

    def _parse_nnmclub_html(self, html_content: str, base_url: str) -> List[SearchResult]:
        import re
        from html import unescape

        results = []
        torrent_re = re.compile(
            r'topictitle"\shref="(?P<desc_link>.+?)"><b>(?P<name>.+?)</b>.+?'
            r'href="(?P<link>d.+?)".+?<u>(?P<size>\d+?)</u>.+?<b>(?P<seeds>\d+?)'
            r"</b>.+?<b>(?P<leech>\d+?)</b>.+?<u>(?P<pub_date>\d+?)</u>",
            re.S,
        )

        for match in torrent_re.finditer(html_content):
            try:
                results.append(
                    SearchResult(
                        name=unescape(match.group("name")),
                        size=match.group("size"),
                        seeds=int(match.group("seeds")),
                        leechers=int(match.group("leech")),
                        link=f"{base_url}/forum/{match.group('link')}",
                        desc_link=f"{base_url}/forum/{match.group('desc_link')}",
                        tracker="nnmclub",
                        engine_url=base_url,
                    )
                )
            except Exception as e:
                logger.debug(f"Skipping malformed NNMClub result: {e}")
                continue

        return results

    async def _search_iptorrents(self, query: str, category: str) -> List[SearchResult]:
        import os
        import logging
        import aiohttp
        import re
        import html
        from urllib.parse import urlencode

        logger = logging.getLogger(__name__)
        results = []
        username = os.getenv("IPTORRENTS_USERNAME")
        password = os.getenv("IPTORRENTS_PASSWORD")
        if not username or not password:
            return []

        base_url = "https://iptorrents.com"
        cat_map = {
            "movies": "72",
            "tv": "73",
            "music": "75",
            "games": "74",
            "anime": "60",
            "software": "1",
            "books": "35",
        }
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{base_url}/do-login.php",
                    data={"username": username, "password": password},
                    headers={"Referer": f"{base_url}/login.php"},
                    allow_redirects=False,
                ) as resp:
                    cookies = {c.key: c.value for c in resp.cookies.values()}
                    if not cookies:
                        logger.error(f"IPTorrents login failed: HTTP {resp.status}, no cookies returned")

                self._tracker_sessions["iptorrents"] = {
                    "cookies": cookies,
                    "base_url": base_url,
                }

                params = {"q": query, "o": "seeders"}
                if category != "all" and category in cat_map:
                    params[cat_map[category]] = ""

                search_url = f"{base_url}/t?{urlencode(params)}"
                async with session.get(
                    search_url,
                    cookies=cookies,
                    headers={"Referer": f"{base_url}/t"},
                ) as resp:
                    html_content = await resp.text()

                results = self._parse_iptorrents_html(html_content, base_url)
        except Exception as e:
            logger.error(f"IPTorrents search error: {e}")

        return results

    def _parse_iptorrents_html(self, html_content: str, base_url: str) -> List[SearchResult]:
        import re
        import html

        results = []
        table_match = re.search(r'<table[^>]*id="torrents"[^>]*>(.+?)</table>', html_content, re.S)
        if not table_match:
            return results
        table = table_match.group(1)

        for row in re.finditer(r"<tr>(.+?)</tr>", table, re.S):
            row_text = row.group(1)
            if "<th" in row_text:
                continue

            name_match = re.search(
                r'<a\s+class=" hv"\s+href="(?P<desc>/t/\d+)">(?P<name>.+?)</a>',
                row_text,
                re.S,
            )
            if not name_match:
                continue

            dl_match = re.search(r'href="(?P<link>/download\.php/\d+/[^"]+\.torrent[^"]*)"', row_text)
            if not dl_match:
                continue

            size_match = re.search(r">(?P<size>[\d.]+\s*(?:K|M|G|T)?B)<", row_text, re.I)

            td_values = re.findall(r"<td[^>]*>(?P<val>\d+)</td>", row_text)
            seeds = int(td_values[0]) if len(td_values) > 0 else 0
            leechers = int(td_values[1]) if len(td_values) > 1 else 0

            is_free = bool(re.search(r'class="free"', row_text, re.I))

            name_text = html.unescape(name_match.group("name"))
            if is_free and "[free]" not in name_text:
                name_text = name_text.rstrip() + " [free]"

            try:
                results.append(
                    SearchResult(
                        name=name_text,
                        size=size_match.group("size") if size_match else "0 B",
                        seeds=seeds,
                        leechers=leechers,
                        link=base_url + dl_match.group("link"),
                        desc_link=base_url + name_match.group("desc"),
                        tracker="iptorrents",
                        engine_url=base_url,
                        freeleech=is_free,
                    )
                )
            except Exception as e:
                logger.debug(f"Skipping malformed IPTorrents result: {e}")
                continue

        return results

    async def fetch_torrent(self, tracker: str, url: str) -> Optional[bytes]:
        import os
        import aiohttp
        import logging
        import re

        logger = logging.getLogger(__name__)
        session_data = self._tracker_sessions.get(tracker)
        if not session_data:
            self._load_env()
            try:
                if tracker == "rutracker":
                    await self._search_rutracker("__probe__", "all")
                elif tracker == "kinozal":
                    await self._search_kinozal("__probe__", "all")
                elif tracker == "nnmclub":
                    await self._search_nnmclub("__probe__", "all")
                elif tracker == "iptorrents":
                    await self._search_iptorrents("__probe__", "all")
            except Exception as e:
                logger.debug(f"Tracker probe failed for {tracker}: {e}")
            session_data = self._tracker_sessions.get(tracker)

        if not session_data:
            logger.error(f"No stored session for tracker: {tracker}")
            return None

        cookies = session_data["cookies"]
        base_url = session_data["base_url"]

        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Referer": base_url}
                async with session.get(url, cookies=cookies, headers=headers, allow_redirects=True) as resp:
                    if resp.status != 200:
                        logger.error(f"fetch_torrent {tracker}: HTTP {resp.status} for {url}")
                        return None
                    content_type = resp.headers.get("Content-Type", "")
                    data = await resp.read()
                    if (
                        "application/x-bittorrent" in content_type
                        or data[:11] == b"d8:announce"
                        or data[:14] == b"d10:created by"
                        or data[:7] == b"d8:files"
                    ):
                        return data
                    if tracker == "rutracker":
                        return await self._fetch_rutracker_redirect(session, url, cookies, base_url)
                    if tracker == "kinozal":
                        return await self._fetch_kinozal_torrent(session, url, cookies, base_url)
                    logger.error(f"fetch_torrent {tracker}: response not a torrent file ({content_type})")
                    return None
        except Exception as e:
            logger.error(f"fetch_torrent {tracker}: {e}")
            return None

    async def _fetch_rutracker_redirect(self, session, url: str, cookies: dict, base_url: str) -> Optional[bytes]:
        import re
        import logging

        logger = logging.getLogger(__name__)
        try:
            match = re.search(r"[?&]t=(\d+)", url)
            if not match:
                return None
            topic_id = match.group(1)
            dl_url = f"{base_url}/forum/dl.rss.php?{topic_id}"
            headers = {"Referer": f"{base_url}/forum/viewtopic.php?t={topic_id}"}
            async with session.get(dl_url, cookies=cookies, headers=headers) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
                if data[:11] == b"d8:announce" or data[:14] == b"d10:created by":
                    return data
        except Exception as e:
            logger.error(f"_fetch_rutracker_redirect: {e}")
        return None

    async def _fetch_kinozal_torrent(self, session, url: str, cookies: dict, base_url: str) -> Optional[bytes]:
        import logging

        logger = logging.getLogger(__name__)
        try:
            headers = {"Referer": base_url}
            async with session.get(url, cookies=cookies, headers=headers) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
                if data[:11] == b"d8:announce" or data[:14] == b"d10:created by":
                    return data
        except Exception as e:
            logger.error(f"_fetch_kinozal_torrent: {e}")
        return None

    def get_search_status(self, search_id: str) -> Optional[SearchMetadata]:
        return self._active_searches.get(search_id)

    def get_live_results(self, search_id: str) -> List[Any]:
        """Get all results found so far for a search, not yet merged.

        FIX: Also check _last_merged_results which IS populated incrementally
        as each tracker completes (inside asyncio.gather callback).
        """
        # First try _tracker_results
        if search_id in self._tracker_results:
            results = []
            for tracker_results in self._tracker_results[search_id].values():
                if tracker_results:
                    results.extend(tracker_results)
            if results:
                return results

        # Fallback: check _last_merged_results (populated INCREMENTALLY)
        if search_id in self._last_merged_results:
            merged, all_results = self._last_merged_results[search_id]
            if all_results:
                return all_results

        return []

    def get_all_tracker_results(self, search_id: str) -> List[Any]:
        """Get all results from _tracker_results."""
        if search_id not in self._tracker_results:
            return []
        results = []
        for tracker_results in self._tracker_results[search_id].values():
            if tracker_results:
                results.extend(tracker_results)
        return results

    def get_active_searches(self) -> List[SearchMetadata]:
        return list(self._active_searches.values())
