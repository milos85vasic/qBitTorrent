"""
Unit tests for TrackerValidator with mocked HTTP/UDP.

Scenarios:
- HTTP scrape success
- UDP scrape success
- Invalid tracker URL handling
- Timeout handling
- Connection refused handling
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))

from merge_service.validator import ScrapeResult, TrackerStatus, TrackerValidator


def _make_mock_response(content=b"", status=200):
    """Create a mock aiohttp response."""
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.read = AsyncMock(return_value=content)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm


class TestTrackerValidator:
    """Test TrackerValidator with mocked network."""

    @pytest.fixture
    def validator(self):
        return TrackerValidator()

    @pytest.mark.asyncio
    async def test_validate_http_tracker_success(self, validator):
        """HTTP tracker validation with successful bencoded response."""
        # Valid bencoded scrape response with files dict (multi-torrent format)
        content = b"d5:filesd20:aaaaaaaaaaaaaaaaaaaad8:completei100e10:incompletei50eeee"
        mock_cm = _make_mock_response(content=content, status=200)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)
        mock_session.closed = False

        with patch.object(validator, "_get_session", AsyncMock(return_value=mock_session)):
            result = await validator._http_scrape("http://tracker.example.com:8080/announce")
            assert result.status == TrackerStatus.HEALTHY
            assert result.seeds == 100
            assert result.leechers == 50

    @pytest.mark.asyncio
    async def test_validate_http_tracker_failure(self, validator):
        """HTTP tracker validation with failure response."""
        mock_cm = _make_mock_response(status=404)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)
        mock_session.closed = False

        with patch.object(validator, "_get_session", AsyncMock(return_value=mock_session)):
            result = await validator._http_scrape("http://tracker.example.com:8080/announce")
            assert result.status == TrackerStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_validate_http_timeout(self, validator):
        """HTTP tracker timeout should return OFFLINE."""
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=TimeoutError())
        mock_session.closed = False

        with patch.object(validator, "_get_session", AsyncMock(return_value=mock_session)):
            result = await validator._http_scrape("http://tracker.example.com:8080/announce")
            assert result.status == TrackerStatus.OFFLINE
            assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_validate_tracker_invalid_url(self, validator):
        """Invalid URL should return OFFLINE."""
        result = await validator.validate_tracker("invalid_url")
        assert result.status == TrackerStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_validate_tracker_empty_url(self, validator):
        """Empty URL should return OFFLINE."""
        result = await validator.validate_tracker("")
        assert result.status == TrackerStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_validate_connection_refused(self, validator):
        """Connection refused should return OFFLINE."""
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=ConnectionRefusedError())
        mock_session.closed = False

        with patch.object(validator, "_get_session", AsyncMock(return_value=mock_session)):
            result = await validator._http_scrape("http://localhost:99999/announce")
            assert result.status == TrackerStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_validate_tracker_http_url(self, validator):
        """HTTP URL should use HTTP scrape and return result."""
        content = b"d8:completei100e10:incompletei50ee"
        mock_cm = _make_mock_response(content=content, status=200)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)
        mock_session.closed = False

        with patch.object(validator, "_get_session", AsyncMock(return_value=mock_session)):
            result = await validator.validate_tracker("http://tracker.example.com/announce")
            assert result is not None
            assert result.tracker == "http://tracker.example.com/announce"

    @pytest.mark.asyncio
    async def test_validate_tracker_udp_url(self, validator):
        """UDP URL should use UDP scrape."""
        mock_udp_result = ScrapeResult(
            tracker="udp://tracker.example.com:1337",
            status=TrackerStatus.HEALTHY,
            seeds=10,
            leechers=5,
        )

        with (
            patch.object(
                validator,
                "_http_scrape",
                AsyncMock(
                    return_value=ScrapeResult(
                        tracker="udp://tracker.example.com:1337",
                        status=TrackerStatus.OFFLINE,
                    )
                ),
            ),
            patch.object(validator, "_udp_scrape", AsyncMock(return_value=mock_udp_result)) as mock_udp,
        ):
            result = await validator.validate_tracker("udp://tracker.example.com:1337")
            mock_udp.assert_called_once()
            assert result.status == TrackerStatus.HEALTHY

    def test_announce_to_scrape(self, validator):
        """Announce URL should convert to scrape URL."""
        result = validator._announce_to_scrape("http://tracker.example.com:8080/announce")
        assert result is not None
        assert "scrape" in result

    def test_parse_bencoded_valid(self, validator):
        """Valid bencoded data should parse correctly."""
        data = b"d8:intervali1800e5:peerslee"
        result = validator._parse_bencoded(data)
        assert b"interval" in result
        assert result[b"interval"] == 1800

    def test_parse_bencoded_invalid(self, validator):
        """Invalid bencoded data should return empty dict."""
        result = validator._parse_bencoded(b"invalid")
        assert result == {}

    def test_get_cached_result_empty(self, validator):
        """Empty cache should return None."""
        result = validator.get_cached_result("http://tracker.example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_multiple(self, validator):
        """validate_multiple should validate multiple trackers."""
        content = b"d8:completei10e10:incompletei5ee"
        mock_cm = _make_mock_response(content=content, status=200)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)
        mock_session.closed = False

        with patch.object(validator, "_get_session", AsyncMock(return_value=mock_session)):
            results = await validator.validate_multiple(
                [
                    "http://tracker1.com/announce",
                    "http://tracker2.com/announce",
                ]
            )
            assert len(results) == 2
            for r in results:
                assert isinstance(r, ScrapeResult)

    @pytest.mark.asyncio
    async def test_validate_tracker_caches_result(self, validator):
        """validate_tracker should cache results."""
        content = b"d8:completei10e10:incompletei5ee"
        mock_cm = _make_mock_response(content=content, status=200)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)
        mock_session.closed = False

        with patch.object(validator, "_get_session", AsyncMock(return_value=mock_session)):
            result1 = await validator.validate_tracker("http://tracker.example.com/announce")
            cached = validator.get_cached_result("http://tracker.example.com/announce")
            assert cached is not None
            assert cached.status == result1.status
