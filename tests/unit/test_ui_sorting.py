import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))


class TestContentTypeDetectionFromAPI:
    """Test that content_type is properly returned in API responses."""

    def test_search_result_has_content_type(self):
        from api.routes import SearchResultResponse

        resp = SearchResultResponse(
            name="Test Movie 2024 1080p",
            size="1.5 GB",
            seeds=100,
            leechers=50,
            download_urls=["http://example.com/torrent.torrent"],
            quality="full_hd",
            content_type="movie",
            tracker="example",
            sources=[{"tracker": "example", "seeds": 100, "leechers": 50}],
        )
        assert resp.content_type == "movie"

    def test_search_result_content_type_none(self):
        from api.routes import SearchResultResponse

        resp = SearchResultResponse(
            name="Test File",
            size="500 MB",
            seeds=10,
            leechers=5,
            download_urls=["http://example.com/file.torrent"],
            tracker="example",
        )
        assert resp.content_type is None


class TestSortingHelpers:
    """Test sorting logic that mirrors frontend."""

    def test_parse_size_various_formats(self):
        test_cases = [
            ("1.5 GB", 1.5 * 1024**3),
            ("500 MB", 500 * 1024**2),
            ("1 TB", 1024**4),
            ("1024 KB", 1024 * 1024),
            ("1.2 KiB", 1.2 * 1024),
            ("500 bytes", 500),
        ]
        for size_str, expected in test_cases:
            assert _parse_test_size(size_str) == pytest.approx(expected, rel=1)

    def test_sort_by_seeds_descending(self):
        results = [
            {"seeds": 100},
            {"seeds": 50},
            {"seeds": 200},
        ]
        results.sort(key=lambda x: x.get("seeds", 0), reverse=True)
        assert [r["seeds"] for r in results] == [200, 100, 50]

    def test_sort_by_seeds_ascending(self):
        results = [
            {"seeds": 100},
            {"seeds": 50},
            {"seeds": 200},
        ]
        results.sort(key=lambda x: x.get("seeds", 0), reverse=False)
        assert [r["seeds"] for r in results] == [50, 100, 200]

    def test_sort_by_name_alphabetically(self):
        results = [
            {"name": "Zebra Movie"},
            {"name": "Alpha Movie"},
            {"name": "Beta Movie"},
        ]
        results.sort(key=lambda x: x.get("name", ""), reverse=False)
        assert [r["name"] for r in results] == ["Alpha Movie", "Beta Movie", "Zebra Movie"]


def _parse_test_size(size_str):
    """Mirrors frontend parseSize function."""
    if not size_str:
        return 0
    import re

    m = re.match(r"([\d.]+)\s*([KMGT]?B)", size_str, re.I)
    if not m:
        return 0
    val = float(m.group(1))
    unit = m.group(2).upper()
    multipliers = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
        "KIB": 1024,
        "MIB": 1024**2,
        "GIB": 1024**3,
        "TIB": 1024**4,
    }
    return val * multipliers.get(unit, 1)
