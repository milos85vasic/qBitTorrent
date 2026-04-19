"""
Unit tests for the tracker validator module.
"""

import importlib.util
import os
import sys

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


class TestTrackerValidator:
    """Tests for TrackerValidator class."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return TrackerValidator()

    def test_init(self, validator):
        """Test validator initialization."""
        assert validator._session is None
        assert validator._cache == {}
        assert validator.HTTP_TIMEOUT == 10
        assert validator.UDP_TIMEOUT == 5

    def test_announce_to_scrape_standard(self, validator):
        """Test scrape URL conversion for standard announce."""
        scrape = validator._announce_to_scrape("https://tracker.com/announce")
        assert scrape == "https://tracker.com/scrape"

    def test_announce_to_scrape_php(self, validator):
        """Test scrape URL conversion for PHP announce."""
        scrape = validator._announce_to_scrape("https://tracker.com/announce.php")
        assert scrape == "https://tracker.com/scrape.php"

    def test_announce_to_scrape_already_scrape(self, validator):
        """Test that scrape URLs are returned as-is."""
        scrape = validator._announce_to_scrape("https://tracker.com/scrape")
        assert scrape == "https://tracker.com/scrape"

    def test_announce_to_scrape_invalid(self, validator):
        """Test with invalid URL."""
        scrape = validator._announce_to_scrape("")
        assert scrape is None

    def test_close_session(self, validator):
        """Test session cleanup."""
        import asyncio

        asyncio.run(validator.close())
        assert True


class TestScrapeResult:
    """Tests for ScrapeResult dataclass."""

    def test_creation(self):
        """Test ScrapeResult creation."""
        result = ScrapeResult(
            tracker="https://tracker.com",
            status=TrackerStatus.HEALTHY,
            seeds=100,
            leechers=20,
            complete=80,
        )

        assert result.tracker == "https://tracker.com"
        assert result.status == TrackerStatus.HEALTHY
        assert result.seeds == 100
        assert result.leechers == 20
        assert result.complete == 80

    def test_with_error(self):
        """Test ScrapeResult with error."""
        result = ScrapeResult(
            tracker="https://tracker.com",
            status=TrackerStatus.OFFLINE,
            error="Connection timeout",
        )

        assert result.status == TrackerStatus.OFFLINE
        assert result.error == "Connection timeout"


class TestTrackerStatus:
    """Tests for TrackerStatus enum."""

    def test_values(self):
        """Test all tracker status values."""
        assert TrackerStatus.HEALTHY.value == "healthy"
        assert TrackerStatus.DEGRADED.value == "degraded"
        assert TrackerStatus.OFFLINE.value == "offline"
        assert TrackerStatus.UNKNOWN.value == "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
