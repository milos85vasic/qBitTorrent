"""
Metadata enrichment for better matching across trackers.

Provides integration with:
- OMDb API (movies)
- TMDB API (movies, TV)
- TVMaze API (TV shows)
- AniList API (anime)
- MusicBrainz API (music)
- OpenLibrary API (books)
"""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MetadataResult:
    """Result from metadata API lookup."""

    source: str  # OMDb, TMDB, etc.
    title: str
    year: Optional[int] = None
    content_type: Optional[str] = None  # movie, tv, music, book
    imdb_id: Optional[str] = None
    tmdb_id: Optional[str] = None
    anilist_id: Optional[str] = None
    musicbrainz_id: Optional[str] = None
    openlibrary_id: Optional[str] = None
    poster_url: Optional[str] = None
    overview: Optional[str] = None
    genres: List[str] = None

    def __post_init__(self):
        if self.genres is None:
            self.genres = []


class MetadataEnricher:
    """Enriches search results with metadata from external APIs."""

    def __init__(self):
        self._omdb_key = os.environ.get("OMDB_API_KEY")
        self._tmdb_key = os.environ.get("TMDB_API_KEY")
        self._anilist_id = os.environ.get("ANILIST_CLIENT_ID")
        self._cache: Dict[str, MetadataResult] = {}

    async def resolve(self, query: str) -> Optional[MetadataResult]:
        """
        Resolve a query to metadata using multiple APIs.

        Tries APIs in order of reliability:
        1. TMDB (movies, TV)
        2. OMDb (movies)
        3. TVMaze (TV)
        4. AniList (anime)
        5. OpenLibrary (books)
        6. MusicBrainz (music)
        """
        cache_key = query.lower().strip()

        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try TMDB first
        result = await self._lookup_tmdb(query)
        if result:
            self._cache[cache_key] = result
            return result

        # Try OMDb
        result = await self._lookup_omdb(query)
        if result:
            self._cache[cache_key] = result
            return result

        # Try TVMaze
        result = await self._lookup_tvmaze(query)
        if result:
            self._cache[cache_key] = result
            return result

        # Try AniList
        result = await self._lookup_anilist(query)
        if result:
            self._cache[cache_key] = result
            return result

        # Try OpenLibrary
        result = await self._lookup_openlibrary(query)
        if result:
            self._cache[cache_key] = result
            return result

        # Try MusicBrainz
        result = await self._lookup_musicbrainz(query)
        if result:
            self._cache[cache_key] = result
            return result

        return None

    async def _lookup_omdb(self, query: str) -> Optional[MetadataResult]:
        """Look up using OMDb API."""
        if not self._omdb_key:
            return None

        try:
            import aiohttp

            url = f"http://www.omdbapi.com/?apikey={self._omdb_key}&t={query}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("Response") == "True":
                            return MetadataResult(
                                source="OMDb",
                                title=data.get("Title", ""),
                                year=int(data.get("Year", "0").split("-")[0])
                                if data.get("Year")
                                else None,
                                content_type="movie"
                                if data.get("Type") == "movie"
                                else "tv",
                                imdb_id=data.get("imdbID"),
                                poster_url=data.get("Poster"),
                                overview=data.get("Plot"),
                                genres=data.get("Genre", "").split(", ")
                                if data.get("Genre")
                                else [],
                            )
        except Exception as e:
            logger.debug(f"OMDb lookup failed: {e}")

        return None

    async def _lookup_tmdb(self, query: str) -> Optional[MetadataResult]:
        """Look up using TMDB API."""
        if not self._tmdb_key:
            return None

        try:
            import aiohttp

            # Search
            search_url = f"https://api.themoviedb.org/3/search/multi?api_key={self._tmdb_key}&query={query}"

            async with aiohttp.ClientSession() as session:
                async with session.get(search_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])
                        if results:
                            result = results[0]
                            media_type = result.get("media_type")

                            return MetadataResult(
                                source="TMDB",
                                title=result.get("title") or result.get("name", ""),
                                year=int(result.get("release_date", "").split("-")[0])
                                if result.get("release_date")
                                else None,
                                content_type=media_type,
                                tmdb_id=str(result.get("id")),
                                poster_url=f"https://image.tmdb.org/t/p/w500{result.get('poster_path')}"
                                if result.get("poster_path")
                                else None,
                                overview=result.get("overview"),
                            )
        except Exception as e:
            logger.debug(f"TMDB lookup failed: {e}")

        return None

    async def _lookup_tvmaze(self, query: str) -> Optional[MetadataResult]:
        """Look up using TVMaze API."""
        try:
            import aiohttp

            url = f"https://api.tvmaze.com/search/shows?q={query}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            result = data[0].get("show", {})
                            return MetadataResult(
                                source="TVMaze",
                                title=result.get("name", ""),
                                year=int(result.get("premiered", "").split("-")[0])
                                if result.get("premiered")
                                else None,
                                content_type="tv",
                                poster_url=result.get("image", {}).get("medium")
                                if result.get("image")
                                else None,
                                overview=result.get("summary", "").strip("<p></p>"),
                            )
        except Exception as e:
            logger.debug(f"TVMaze lookup failed: {e}")

        return None

    async def _lookup_anilist(self, query: str) -> Optional[MetadataResult]:
        """Look up using AniList API (GraphQL)."""
        if not self._anilist_id:
            return None

        try:
            import aiohttp

            query_str = """
            query ($search: String) {
              Media(search: $search, type: ANIME) {
                id
                title { english romaji }
                startDate { year }
                coverImage { large }
                description
              }
            }
            """
            variables = {"search": query}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://graphql.anilist.co",
                    json={"query": query_str, "variables": variables},
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        media = data.get("data", {}).get("Media")
                        if media:
                            return MetadataResult(
                                source="AniList",
                                title=media.get("title", {}).get("english")
                                or media.get("title", {}).get("romaji", ""),
                                year=media.get("startDate", {}).get("year"),
                                content_type="anime",
                                anilist_id=str(media.get("id")),
                                poster_url=media.get("coverImage", {}).get("large"),
                                overview=media.get("description"),
                            )
        except Exception as e:
            logger.debug(f"AniList lookup failed: {e}")

        return None

    async def _lookup_musicbrainz(self, query: str) -> Optional[MetadataResult]:
        """Look up using MusicBrainz API."""
        try:
            import aiohttp

            url = f"https://musicbrainz.org/ws/2/release-group/?query={query}&fmt=json&limit=1"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        release_groups = data.get("release-groups", [])
                        if release_groups:
                            rg = release_groups[0]
                            return MetadataResult(
                                source="MusicBrainz",
                                title=rg.get("title", ""),
                                year=int(
                                    rg.get("first-release-date", "0").split("-")[0]
                                )
                                if rg.get("first-release-date")
                                else None,
                                content_type="music",
                                musicbrainz_id=rg.get("id"),
                            )
        except Exception as e:
            logger.debug(f"MusicBrainz lookup failed: {e}")

        return None

    async def _lookup_openlibrary(self, query: str) -> Optional[MetadataResult]:
        """Look up using OpenLibrary API."""
        try:
            import aiohttp

            url = f"https://openlibrary.org/search.json?q={query}&limit=1"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        docs = data.get("docs", [])
                        if docs:
                            doc = docs[0]
                            return MetadataResult(
                                source="OpenLibrary",
                                title=doc.get("title", ""),
                                year=doc.get("first_publish_year"),
                                content_type="book",
                                openlibrary_id=doc.get("key", "").replace(
                                    "/works/", ""
                                ),
                            )
        except Exception as e:
            logger.debug(f"OpenLibrary lookup failed: {e}")

        return None

    def clear_cache(self):
        """Clear the metadata cache."""
        self._cache.clear()

    def detect_quality(self, name: str) -> Optional[str]:
        """
        Detect quality tier from torrent name.

        Parses common quality indicators:
        - Resolution: 720p, 1080p, 2160p, 4K, 8K
        - Source: BluRay, WEB-DL, HDTV, DVD
        - Codec: x264, x265, HEVC
        """
        import re

        name_lower = name.lower()

        # Resolution detection
        if "2160p" in name_lower or "4k" in name_lower:
            return "4K"
        if "1080p" in name_lower:
            return "1080p"
        if "720p" in name_lower:
            return "720p"
        if "480p" in name_lower or "sd" in name_lower:
            return "SD"

        # Source-based detection
        if "bluray" in name_lower or "blu-ray" in name_lower:
            return "BluRay"
        if "web-dl" in name_lower or "webrip" in name_lower:
            return "WEB-DL"
        if "hdtv" in name_lower:
            return "HDTV"
        if "dvd" in name_lower:
            return "DVD"

        return None
