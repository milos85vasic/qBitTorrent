"""
Unit tests for the metadata enricher module.
"""

import pytest
from unittest.mock import patch, AsyncMock
from download_proxy.src.merge_service.enricher import MetadataEnricher, MetadataResult


class TestMetadataEnricher:
    """Tests for MetadataEnricher class."""

    @pytest.fixture
    def enricher(self):
        """Create enricher instance."""
        return MetadataEnricher()

    def test_init(self, enricher):
        """Test enricher initialization."""
        assert enricher._omdb_key is None
        assert enricher._tmdb_key is None
        assert enricher._cache == {}

    def test_detect_quality_4k(self, enricher):
        """Test quality detection for 4K."""
        assert enricher.detect_quality("Movie 2023 2160p BluRay") == "4K"
        assert enricher.detect_quality("Movie 2023 4K WEB-DL") == "4K"

    def test_detect_quality_1080p(self, enricher):
        """Test quality detection for 1080p."""
        assert enricher.detect_quality("Movie 2023 1080p BluRay") == "1080p"
        assert enricher.detect_quality("Movie 2023 1080p WEB-DL") == "1080p"

    def test_detect_quality_720p(self, enricher):
        """Test quality detection for 720p."""
        assert enricher.detect_quality("Movie 720p HDTV") == "720p"

    def test_detect_quality_sd(self, enricher):
        """Test quality detection for SD."""
        assert enricher.detect_quality("Movie DVD") == "DVD"
        assert enricher.detect_quality("Movie 480p") == "SD"

    def test_detect_quality_source_based(self, enricher):
        """Test quality detection from source."""
        assert enricher.detect_quality("Movie BluRay") == "BluRay"
        assert enricher.detect_quality("Movie WEB-DL") == "WEB-DL"
        assert enricher.detect_quality("Movie HDTV") == "HDTV"

    def test_detect_quality_unknown(self, enricher):
        """Test quality detection with no clear indicator."""
        assert enricher.detect_quality("Movie 2023") is None

    def test_clear_cache(self, enricher):
        """Test cache clearing."""
        enricher._cache["test"] = MetadataResult(source="test", title="test")

        enricher.clear_cache()

        assert enricher._cache == {}

    @pytest.mark.asyncio
    async def test_resolve_no_apis(self, enricher):
        """Test resolve with no API keys configured."""
        result = await enricher.resolve("Test Movie")

        # Should return None since no APIs are configured
        assert result is None


class TestMetadataResult:
    """Tests for MetadataResult dataclass."""

    def test_creation(self):
        """Test MetadataResult creation."""
        result = MetadataResult(
            source="TMDB",
            title="Test Movie",
            year=2023,
            content_type="movie",
            tmdb_id="12345",
        )

        assert result.source == "TMDB"
        assert result.title == "Test Movie"
        assert result.year == 2023
        assert result.content_type == "movie"
        assert result.tmdb_id == "12345"

    def test_default_genres(self):
        """Test that genres defaults to empty list."""
        result = MetadataResult(source="test", title="test")

        assert result.genres == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
