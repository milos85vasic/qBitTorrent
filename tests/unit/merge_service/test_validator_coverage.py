"""
Additional coverage for merge_service/validator.py — bencode parsing,
HTTP/UDP scrape, caching, validate_multiple.
"""

import importlib.util
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")
_MS_PATH = os.path.join(_SRC_PATH, "merge_service")

sys.modules.setdefault("merge_service", type(sys)("merge_service"))
sys.modules["merge_service"].__path__ = [_MS_PATH]

_validator_spec = importlib.util.spec_from_file_location(
    "merge_service.validator", os.path.join(_MS_PATH, "validator.py")
)
_validator_mod = importlib.util.module_from_spec(_validator_spec)
sys.modules["merge_service.validator"] = _validator_mod
_validator_spec.loader.exec_module(_validator_mod)

TrackerValidator = _validator_mod.TrackerValidator
ScrapeResult = _validator_mod.ScrapeResult
TrackerStatus = _validator_mod.TrackerStatus


class TestBencodeParsing:
    def test_empty_dict(self):
        v = TrackerValidator()
        result = v._parse_bencoded(b"de")
        assert result == {}

    def test_simple_dict(self):
        v = TrackerValidator()
        data = b"d4:name5:alice3:agei25ee"
        result = v._parse_bencoded(data)
        assert result[b"name"] == b"alice"
        assert result[b"age"] == 25

    def test_nested_dict(self):
        v = TrackerValidator()
        data = b"d4:infod6:lengthi1024eee"
        result = v._parse_bencoded(data)
        assert result[b"info"][b"length"] == 1024

    def test_list(self):
        v = TrackerValidator()
        data = b"l5:hello5:worlde"
        result, pos = v._decode_benc(data, 0)
        assert result == [b"hello", b"world"]

    def test_integer(self):
        v = TrackerValidator()
        data = b"i42e"
        result, pos = v._decode_benc(data, 0)
        assert result == 42

    def test_string(self):
        v = TrackerValidator()
        data = b"5:hello"
        result, pos = v._decode_benc(data, 0)
        assert result == b"hello"

    def test_empty_list(self):
        v = TrackerValidator()
        data = b"le"
        result, pos = v._decode_benc(data, 0)
        assert result == []

    def test_invalid_bencode(self):
        v = TrackerValidator()
        result = v._parse_bencoded(b"xyz")
        assert result == {}

    def test_unexpected_end(self):
        v = TrackerValidator()
        with pytest.raises(ValueError, match="Unexpected end"):
            v._decode_benc(b"", 0)

    def test_invalid_char(self):
        v = TrackerValidator()
        with pytest.raises(ValueError, match="Invalid bencode"):
            v._decode_benc(b"x", 0)

    def test_dict_with_list_value(self):
        v = TrackerValidator()
        data = b"d4:listli1ei2eee"
        result = v._parse_bencoded(data)
        assert result[b"list"] == [1, 2]


class TestHttpScrape:
    @pytest.mark.asyncio
    async def test_invalid_scrape_url(self):
        v = TrackerValidator()
        result = await v._http_scrape("not-a-valid-url")
        assert result.status == TrackerStatus.OFFLINE
        assert "Invalid" in result.error

    @pytest.mark.asyncio
    async def test_successful_scrape(self):
        v = TrackerValidator()
        bencoded_response = b"d5:filesdee"

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=bencoded_response)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch.object(v, "_get_session", return_value=mock_session):
            result = await v._http_scrape("https://tracker.com/announce")
            assert result.status == TrackerStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_http_error_status(self):
        v = TrackerValidator()
        mock_resp = AsyncMock()
        mock_resp.status = 500
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch.object(v, "_get_session", return_value=mock_session):
            result = await v._http_scrape("https://tracker.com/announce")
            assert result.status == TrackerStatus.OFFLINE
            assert "500" in result.error

    @pytest.mark.asyncio
    async def test_timeout(self):
        v = TrackerValidator()
        with patch.object(v, "_get_session", side_effect=TimeoutError()):
            result = await v._http_scrape("https://tracker.com/announce")
            assert result.status == TrackerStatus.OFFLINE
            assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_connection_error(self):
        v = TrackerValidator()
        with patch.object(v, "_get_session", side_effect=Exception("conn refused")):
            result = await v._http_scrape("https://tracker.com/announce")
            assert result.status == TrackerStatus.OFFLINE
            assert "conn refused" in result.error


class TestValidateTracker:
    @pytest.mark.asyncio
    async def test_caches_result(self):
        v = TrackerValidator()
        mock_result = ScrapeResult(tracker="http://t", status=TrackerStatus.HEALTHY)

        with patch.object(v, "_http_scrape", return_value=mock_result):
            r1 = await v.validate_tracker("https://tracker.com/announce")
            assert r1.status == TrackerStatus.HEALTHY
            assert "https://tracker.com/announce" in v._cache


class TestGetCachedResult:
    def test_no_cache(self):
        v = TrackerValidator()
        assert v.get_cached_result("http://unknown") is None

    def test_expired_cache(self):
        import time

        v = TrackerValidator()
        mock_result = ScrapeResult(tracker="http://t", status=TrackerStatus.HEALTHY)
        v._cache["http://t"] = (time.time() - 600, mock_result)
        assert v.get_cached_result("http://t") is None

    def test_valid_cache(self):
        import time

        v = TrackerValidator()
        mock_result = ScrapeResult(tracker="http://t", status=TrackerStatus.HEALTHY)
        v._cache["http://t"] = (time.time(), mock_result)
        assert v.get_cached_result("http://t") is mock_result


class TestValidateMultiple:
    @pytest.mark.asyncio
    async def test_multiple_trackers(self):
        v = TrackerValidator()
        urls = ["https://a.com/announce", "https://b.com/announce"]
        mock_result = ScrapeResult(tracker="http://t", status=TrackerStatus.HEALTHY)

        with patch.object(v, "validate_tracker", return_value=mock_result):
            results = await v.validate_multiple(urls)
            assert len(results) == 2


class TestUdpScrape:
    @pytest.mark.asyncio
    async def test_invalid_url(self):
        v = TrackerValidator()
        result = await v._udp_scrape("not-valid")
        assert result.status == TrackerStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        v = TrackerValidator()
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.side_effect = Exception("no loop")
            result = await v._udp_scrape("udp://tracker.com:80/announce")
            assert result.status == TrackerStatus.OFFLINE


class TestCloseSession:
    @pytest.mark.asyncio
    async def test_close_with_open_session(self):
        v = TrackerValidator()
        mock_session = AsyncMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        v._session = mock_session
        await v.close()
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_with_none_session(self):
        v = TrackerValidator()
        v._session = None
        await v.close()
