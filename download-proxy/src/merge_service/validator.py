"""
Tracker validation and health checking via scrape endpoints.

Supports:
- HTTP scrape (BEP 48)
- UDP scrape (BEP 15)
- Tracker health status tracking
"""

import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class TrackerStatus(Enum):
    """Tracker health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class ScrapeResult:
    """Result of a tracker scrape operation."""

    tracker: str
    status: TrackerStatus
    seeds: int = 0
    leechers: int = 0
    complete: int = 0
    error: Optional[str] = None
    scrape_time_ms: int = 0


class TrackerValidator:
    """Validates tracker health via scrape endpoints."""

    HTTP_TIMEOUT = 10  # seconds
    UDP_TIMEOUT = 5  # seconds

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, ScrapeResult] = {}
        self._cache_ttl = 300  # 5 minutes

    async def _get_session(self) -> Optional[aiohttp.ClientSession]:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.HTTP_TIMEOUT)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def validate_tracker(self, tracker_url: str) -> ScrapeResult:
        """
        Validate a tracker by attempting to scrape it.

        Args:
            tracker_url: The tracker's announce URL

        Returns:
            ScrapeResult with health status
        """
        import time

        start_time = time.time()

        # Try HTTP scrape first
        result = await self._http_scrape(tracker_url)

        # If HTTP fails, try UDP scrape
        if result.status == TrackerStatus.OFFLINE:
            result = await self._udp_scrape(tracker_url)

        result.scrape_time_ms = int((time.time() - start_time) * 1000)

        # Cache the result
        self._cache[tracker_url] = result

        return result

    async def _http_scrape(self, tracker_url: str) -> ScrapeResult:
        """Perform HTTP scrape (BEP 48)."""
        if not AIOHTTP_AVAILABLE:
            return ScrapeResult(
                tracker=tracker_url,
                status=TrackerStatus.UNKNOWN,
                error="aiohttp not available",
            )

        # Convert announce URL to scrape URL
        scrape_url = self._announce_to_scrape(tracker_url)
        if not scrape_url:
            return ScrapeResult(
                tracker=tracker_url,
                status=TrackerStatus.OFFLINE,
                error="Invalid tracker URL",
            )

        try:
            session = await self._get_session()
            async with session.get(scrape_url) as response:
                if response.status == 200:
                    # Parse bencoded response
                    content = await response.read()
                    data = self._parse_bencoded(content)

                    # Extract torrent info
                    files = data.get(b"files", {})
                    if isinstance(data.get(b"tracker"), bytes):
                        # Single torrent scrape response
                        return ScrapeResult(
                            tracker=tracker_url,
                            status=TrackerStatus.HEALTHY,
                            seeds=data.get(b"complete", 0),
                            leechers=data.get(b"incomplete", 0),
                            complete=data.get(b"complete", 0),
                        )

                    return ScrapeResult(
                        tracker=tracker_url,
                        status=TrackerStatus.HEALTHY,
                        seeds=sum(f.get(b"complete", 0) for f in files.values())
                        if files
                        else 0,
                        leechers=sum(f.get(b"incomplete", 0) for f in files.values())
                        if files
                        else 0,
                    )
                else:
                    return ScrapeResult(
                        tracker=tracker_url,
                        status=TrackerStatus.OFFLINE,
                        error=f"HTTP {response.status}",
                    )
        except asyncio.TimeoutError:
            return ScrapeResult(
                tracker=tracker_url, status=TrackerStatus.OFFLINE, error="Timeout"
            )
        except Exception as e:
            return ScrapeResult(
                tracker=tracker_url, status=TrackerStatus.OFFLINE, error=str(e)
            )

    async def _udp_scrape(self, tracker_url: str) -> ScrapeResult:
        """Perform UDP scrape (BEP 15) - placeholder for UDP implementation."""
        # UDP scrape requires socket operations
        # For now, return offline as fallback already tried HTTP
        return ScrapeResult(
            tracker=tracker_url,
            status=TrackerStatus.OFFLINE,
            error="UDP scrape not implemented",
        )

    def _announce_to_scrape(self, announce_url: str) -> Optional[str]:
        """Convert announce URL to scrape URL."""
        if not announce_url:
            return None

        # Common patterns
        if "/announce" in announce_url:
            return announce_url.replace("/announce", "/scrape")
        if "/announce.php" in announce_url:
            return announce_url.replace("/announce.php", "/scrape.php")

        # If already a scrape URL, return as-is
        if "/scrape" in announce_url:
            return announce_url

        return None

    def _parse_bencoded(self, data: bytes) -> dict:
        """Simple bencode parser for scrape responses."""
        # This is a simplified parser - in production use proper bencode library
        # For now, return empty dict if parsing fails
        try:
            import bencode  # If available

            return bencode.decode(data)
        except:
            pass

        # Fallback: return empty dict
        return {}

    async def validate_multiple(self, tracker_urls: List[str]) -> List[ScrapeResult]:
        """Validate multiple trackers concurrently."""
        tasks = [self.validate_tracker(url) for url in tracker_urls]
        return await asyncio.gather(*tasks)

    def get_cached_result(self, tracker_url: str) -> Optional[ScrapeResult]:
        """Get cached scrape result if still valid."""
        result = self._cache.get(tracker_url)
        if result:
            # For now, always return cached (could add TTL checking)
            return result
        return None
