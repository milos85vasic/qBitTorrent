"""
Tracker validation and health checking via scrape endpoints.

Supports:
- HTTP scrape (BEP 48)
- UDP scrape (BEP 15)
- Tracker health status tracking
"""

from __future__ import annotations

import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None  # type: ignore
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
        self._cache: Dict[str, tuple] = {}
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

        self._cache[tracker_url] = (time.time(), result)

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
        """Perform UDP scrape (BEP 15)."""
        import struct
        import random
        from urllib.parse import urlparse

        try:
            parsed = urlparse(tracker_url)
            host = parsed.hostname
            port = parsed.port or 80

            if not host:
                return ScrapeResult(
                    tracker=tracker_url,
                    status=TrackerStatus.OFFLINE,
                    error="Invalid tracker URL",
                )

            loop = asyncio.get_event_loop()

            class UDPProtocol(asyncio.DatagramProtocol):
                def __init__(self):
                    self.response_future = loop.create_future()
                    self.transport = None

                def connection_made(self, transport):
                    self.transport = transport

                def datagram_received(self, data, addr):
                    if not self.response_future.done():
                        self.response_future.set_result(data)

                def error_received(self, exc):
                    if not self.response_future.done():
                        self.response_future.set_exception(exc)

                def connection_lost(self, exc):
                    if not self.response_future.done():
                        self.response_future.set_exception(
                            exc or asyncio.TimeoutError()
                        )

            transport, protocol = await asyncio.wait_for(
                loop.create_datagram_endpoint(UDPProtocol, remote_addr=(host, port)),
                timeout=self.UDP_TIMEOUT,
            )

            try:
                connect_id = 0x41727101980
                action = 0
                transaction_id = random.randint(0, 0x7FFFFFFF)

                connect_req = struct.pack("!qii", connect_id, action, transaction_id)
                transport.sendto(connect_req)

                connect_resp = await asyncio.wait_for(
                    protocol.response_future, timeout=self.UDP_TIMEOUT
                )

                if len(connect_resp) < 16:
                    return ScrapeResult(
                        tracker=tracker_url,
                        status=TrackerStatus.OFFLINE,
                        error="UDP connect response too short",
                    )

                resp_action, resp_tid, conn_id = struct.unpack(
                    "!iiq", connect_resp[:16]
                )

                if resp_action != 0 or resp_tid != transaction_id:
                    return ScrapeResult(
                        tracker=tracker_url,
                        status=TrackerStatus.OFFLINE,
                        error="UDP connect handshake failed",
                    )

                info_hash = parsed.query
                if not info_hash:
                    return ScrapeResult(
                        tracker=tracker_url,
                        status=TrackerStatus.HEALTHY,
                        seeds=0,
                        leechers=0,
                    )

                scrape_action = 2
                scrape_tid = random.randint(0, 0x7FFFFFFF)

                try:
                    ih_bytes = bytes.fromhex(info_hash[:40])
                except ValueError:
                    ih_bytes = info_hash.encode()[:20]

                scrape_req = struct.pack("!qii", conn_id, scrape_action, scrape_tid)
                scrape_req += ih_bytes

                protocol.response_future = loop.create_future()
                transport.sendto(scrape_req)

                scrape_resp = await asyncio.wait_for(
                    protocol.response_future, timeout=self.UDP_TIMEOUT
                )

                if len(scrape_resp) < 20:
                    return ScrapeResult(
                        tracker=tracker_url,
                        status=TrackerStatus.OFFLINE,
                        error="UDP scrape response too short",
                    )

                s_action, s_tid = struct.unpack("!ii", scrape_resp[:8])
                if s_action == 3:
                    return ScrapeResult(
                        tracker=tracker_url,
                        status=TrackerStatus.OFFLINE,
                        error="UDP scrape error from tracker",
                    )

                seeders, completed, leechers = struct.unpack("!iii", scrape_resp[8:20])

                return ScrapeResult(
                    tracker=tracker_url,
                    status=TrackerStatus.HEALTHY,
                    seeds=seeders,
                    leechers=leechers,
                    complete=completed,
                )

            finally:
                transport.close()

        except asyncio.TimeoutError:
            return ScrapeResult(
                tracker=tracker_url, status=TrackerStatus.OFFLINE, error="UDP timeout"
            )
        except Exception as e:
            return ScrapeResult(
                tracker=tracker_url, status=TrackerStatus.OFFLINE, error=str(e)
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
        """Parse bencoded data (BEP 03) for scrape responses."""
        try:
            result, _ = self._decode_benc(data, 0)
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    def _decode_benc(self, data: bytes, pos: int):
        """Recursively decode bencoded bytes starting at pos."""
        if pos >= len(data):
            raise ValueError("Unexpected end of data")
        ch = data[pos : pos + 1]
        if ch == b"d":
            return self._decode_dict(data, pos)
        elif ch == b"l":
            return self._decode_list(data, pos)
        elif ch == b"i":
            return self._decode_int(data, pos)
        elif ch.isdigit():
            return self._decode_string(data, pos)
        raise ValueError(f"Invalid bencode char at {pos}: {ch}")

    def _decode_dict(self, data: bytes, pos: int):
        pos += 1
        result = {}
        while data[pos : pos + 1] != b"e":
            key, pos = self._decode_string(data, pos)
            val, pos = self._decode_benc(data, pos)
            result[key] = val
        return result, pos + 1

    def _decode_list(self, data: bytes, pos: int):
        pos += 1
        result = []
        while data[pos : pos + 1] != b"e":
            val, pos = self._decode_benc(data, pos)
            result.append(val)
        return result, pos + 1

    def _decode_int(self, data: bytes, pos: int):
        pos += 1
        end = data.index(b"e", pos)
        return int(data[pos:end]), end + 1

    def _decode_string(self, data: bytes, pos: int):
        colon = data.index(b":", pos)
        length = int(data[pos:colon])
        start = colon + 1
        return data[start : start + length], start + length

    async def validate_multiple(self, tracker_urls: List[str]) -> List[ScrapeResult]:
        """Validate multiple trackers concurrently."""
        tasks = [self.validate_tracker(url) for url in tracker_urls]
        return await asyncio.gather(*tasks)

    def get_cached_result(self, tracker_url: str) -> Optional[ScrapeResult]:
        """Get cached scrape result if still within TTL."""
        import time

        entry = self._cache.get(tracker_url)
        if entry:
            cached_time, result = entry
            if time.time() - cached_time < self._cache_ttl:
                return result
            del self._cache[tracker_url]
        return None
