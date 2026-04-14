"""
Unit tests for the deduplicator module.
"""

import sys
import os
import pytest
import importlib.util

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")
_MS_PATH = os.path.join(_SRC_PATH, "merge_service")

sys.modules.setdefault("merge_service", type(sys)("merge_service"))
sys.modules["merge_service"].__path__ = [_MS_PATH]

_dedup_spec = importlib.util.spec_from_file_location(
    "merge_service.deduplicator", os.path.join(_MS_PATH, "deduplicator.py")
)
_dedup_mod = importlib.util.module_from_spec(_dedup_spec)
sys.modules["merge_service.deduplicator"] = _dedup_mod
_dedup_spec.loader.exec_module(_dedup_mod)

_search_spec = importlib.util.spec_from_file_location(
    "merge_service.search", os.path.join(_MS_PATH, "search.py")
)
_search_mod = importlib.util.module_from_spec(_search_spec)
sys.modules["merge_service.search"] = _search_mod
_search_spec.loader.exec_module(_search_mod)

Deduplicator = _dedup_mod.Deduplicator
MatchResult = _dedup_mod.MatchResult
SearchResult = _search_mod.SearchResult


class TestDeduplicator:
    """Tests for Deduplicator class."""

    @pytest.fixture
    def dedup(self):
        """Create a deduplicator instance."""
        return Deduplicator()

    @pytest.fixture
    def sample_result(self):
        """Create a sample search result."""
        return SearchResult(
            name="Test Movie 2023 1080p BluRay",
            link="magnet:?xt=urn:btih:ABCDEF123456",
            size="2.0 GB",
            seeds=100,
            leechers=20,
            engine_url="https://tracker1.com",
            tracker="tracker1",
        )

    def test_init(self, dedup):
        """Test deduplicator initialization."""
        assert dedup._merged_groups == []

    def test_extract_identity_from_result(self, dedup, sample_result):
        """Test identity extraction from result."""
        identity = dedup._extract_identity_from_result(sample_result)

        assert identity.title == "Test Movie 2023 1080p BluRay"
        assert identity.year == 2023
        assert identity.resolution == "1080p"

    def test_extract_infohash_from_magnet(self, dedup):
        """Test infohash extraction from magnet link."""
        hash1 = dedup._extract_infohash(
            "magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12"
        )
        assert hash1 == "ABCDEF1234567890ABCDEF1234567890ABCDEF12"

        hash2 = dedup._extract_infohash("https://tracker.com/file.torrent")
        assert hash2 is None

        hash3 = dedup._extract_infohash("magnet:?xt=urn:btih:short")
        assert hash3 is None

    def test_compare_name_and_size_same(self, dedup, sample_result):
        """Test name+size comparison with identical results."""
        result2 = SearchResult(
            name="Test Movie 2023 1080p BluRay",
            link="magnet:?xt=urn:btih:DIFFERENTHASH",
            size="2.0 GB",
            seeds=50,
            leechers=10,
            engine_url="https://tracker2.com",
            tracker="tracker2",
        )

        assert dedup._compare_name_and_size(sample_result, result2) == True

    def test_compare_name_and_size_different(self, dedup, sample_result):
        """Test name+size comparison with different results."""
        result2 = SearchResult(
            name="Different Movie 2023",
            link="magnet:?xt=urn:btih:DIFFERENTHASH",
            size="2.0 GB",
            seeds=50,
            leechers=10,
            engine_url="https://tracker2.com",
            tracker="tracker2",
        )

        assert dedup._compare_name_and_size(sample_result, result2) == False

    def test_normalize_name(self, dedup):
        """Test name normalization."""
        normalized = dedup._normalize_name("Movie 2023 1080p BluRay x264 [Group]")

        assert "2023" not in normalized
        assert "1080p" not in normalized
        assert "x264" not in normalized
        assert "Group" not in normalized

    def test_parse_size(self, dedup):
        """Test size string parsing."""
        assert dedup._parse_size("2.5 GB") == 2.5 * 1024**3
        assert dedup._parse_size("500 MB") == 500 * 1024**2
        assert dedup._parse_size("1 TB") == 1024**4
        assert dedup._parse_size("invalid") is None

    def test_calculate_similarity(self, dedup):
        """Test similarity calculation."""
        sim = dedup._calculate_similarity("Ubuntu 22.04", "Ubuntu 22.04 LTS")
        assert sim > 0.5

        sim_diff = dedup._calculate_similarity("Ubuntu", "Windows")
        assert sim_diff < 0.5

    def test_merge_results_empty(self, dedup):
        """Test merging empty results."""
        merged = dedup.merge_results([])
        assert merged == []

    def test_merge_results_single(self, dedup, sample_result):
        """Test merging single result."""
        merged = dedup.merge_results([sample_result])

        assert len(merged) == 1
        assert merged[0].total_seeds == sample_result.seeds
        assert len(merged[0].download_urls) == 1


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_match_result_creation(self):
        """Test MatchResult creation."""
        result = MatchResult(
            is_match=True, confidence=0.95, tier=3, reason="name+size match"
        )

        assert result.is_match == True
        assert result.confidence == 0.95
        assert result.tier == 3
        assert result.reason == "name+size match"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
