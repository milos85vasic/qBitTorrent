"""
Unit tests for quality detection.

Issue 3: Quality column shows Unknown for most results.
"""

import sys
import os

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from api.routes import _detect_quality


class TestQualityDetection:
    """Quality detection must recognize resolution and source markers."""

    def test_4k_detection(self):
        for name in [
            "Movie 2024 4K HDR",
            "Movie 2024 2160p BluRay",
        ]:
            assert _detect_quality(name, "10 GB") == "uhd_4k", f"Failed for {name}"

    def test_1080p_detection(self):
        for name in [
            "Movie 2024 1080p BluRay",
            "Movie 2024 BluRay 1080p",
            "Movie 2024 BDRip",
        ]:
            assert _detect_quality(name, "5 GB") == "full_hd", f"Failed for {name}"

    def test_720p_detection(self):
        for name in [
            "Movie 2024 720p WEB-DL",
            "Movie 2024 WEBRip 720p",
            "Movie 2024 HDTV",
        ]:
            assert _detect_quality(name, "2 GB") == "hd", f"Failed for {name}"

    def test_sd_detection(self):
        for name in [
            "Movie 2024 DVDRip",
            "Movie 2024 SD TV",
        ]:
            assert _detect_quality(name, "700 MB") == "sd", f"Failed for {name}"

    def test_size_fallback(self):
        """When name has no quality markers, size should be used."""
        assert _detect_quality("Some Movie", "50 GB") == "uhd_4k"
        assert _detect_quality("Some Movie", "10 GB") == "full_hd"
        assert _detect_quality("Some Movie", "3 GB") == "hd"
        assert _detect_quality("Some Movie", "500 MB") == "sd"

    def test_unknown_for_small_size(self):
        """Very small files should be unknown."""
        assert _detect_quality("Some File", "100 MB") == "unknown"
        assert _detect_quality("Some File", "0 B") == "unknown"

    def test_quality_case_insensitive(self):
        """Quality markers should be detected regardless of case."""
        assert _detect_quality("Movie 1080P BLURAY", "5 GB") == "full_hd"
        assert _detect_quality("Movie 4k HDR", "10 GB") == "uhd_4k"
        assert _detect_quality("Movie WEB-DL", "2 GB") == "hd"

    def test_merged_result_best_quality_set(self):
        """MergedResult.best_quality should be populated after deduplication."""
        from merge_service.search import SearchResult, MergedResult, CanonicalIdentity, QualityTier
        from merge_service.deduplicator import Deduplicator

        results = [
            SearchResult(name="Movie 2024 1080p", link="magnet:x", size="5 GB", seeds=100, leechers=20, engine_url="http://a", tracker="a"),
            SearchResult(name="Movie 2024 720p", link="magnet:y", size="5 GB", seeds=50, leechers=10, engine_url="http://b", tracker="b"),
        ]
        dedup = Deduplicator()
        merged = dedup.merge_results(results)
        assert len(merged) == 1, f"Expected 1 merged result, got {len(merged)}"
        m = merged[0]
        # After fix, best_quality should be set to the best among sources
        assert m.best_quality is not None, "best_quality must be set after merge"
        assert m.best_quality.value == "full_hd", \
            f"Expected full_hd, got {m.best_quality}"

    def test_api_response_quality_is_string(self):
        """API response quality must be a string."""
        from api.routes import _to_response
        from merge_service.search import SearchResult
        r = SearchResult(
            name="Movie 2024 1080p",
            link="magnet:x",
            size="5 GB",
            seeds=100,
            leechers=20,
            engine_url="http://test",
            tracker="test",
        )
        resp = _to_response(r)
        assert isinstance(resp.quality, str)
        assert resp.quality in ("uhd_4k", "full_hd", "hd", "sd", "unknown")
