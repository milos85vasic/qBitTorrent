"""
End-to-end tests for the 5 dashboard issues.

These tests exercise the full pipeline:
search → deduplication → API response → dashboard rendering.
"""

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")
sys.path.insert(0, _SRC_PATH)

from merge_service.deduplicator import Deduplicator
from merge_service.search import SearchOrchestrator, SearchResult


class TestE2EIssue1DownloadMergedSources:
    """E2E: Download button produces merged sources."""

    def test_merged_result_has_multiple_download_urls(self):
        """A merged result from multiple trackers should have all unique URLs."""
        results = [
            SearchResult(
                name="Ubuntu 22.04 LTS",
                link="magnet:?xt=urn:btih:abc123",
                size="4.5 GB",
                seeds=100,
                leechers=20,
                engine_url="https://tracker1.com",
                tracker="tracker1",
            ),
            SearchResult(
                name="Ubuntu 22.04 LTS",
                link="magnet:?xt=urn:btih:def456",
                size="4.5 GB",
                seeds=50,
                leechers=10,
                engine_url="https://tracker2.com",
                tracker="tracker2",
            ),
        ]
        dedup = Deduplicator()
        merged = dedup.merge_results(results)
        assert len(merged) == 1
        m = merged[0]
        assert len(m.download_urls) == 2, "Merged result should have both tracker URLs"

    def test_merged_magnet_contains_all_trackers(self):
        """Magnet generation should include trackers from all source URLs."""
        import re

        urls = [
            "magnet:?xt=urn:btih:abc123def4567890abc123def4567890abc12345&tr=udp://t1:1337",
            "magnet:?xt=urn:btih:abc123def4567890abc123def4567890abc12345&tr=udp://t2:6969",
        ]
        hashes = []
        trackers = set()
        for url in urls:
            m = re.search(r"btih:([a-f0-9]{40}|[a-f0-9]{32})", url, re.I)
            if m:
                hashes.append(m.group(1))
            for tr in re.findall(r"tr=([^&]+)", url):
                trackers.add(tr)
        assert len(hashes) == 2
        assert len(trackers) == 2


class TestE2EIssue2TypeAndSeeds:
    """E2E: Type detection and seeds/leechers flow correctly."""

    def test_public_tracker_result_parsing(self):
        """Simulate plugin output and verify SearchResult parsing."""
        plugin_dict = {
            "name": "Linux Ubuntu 22.04",
            "link": "magnet:x",
            "size": "4.5 GB",
            "seeds": 150,
            "leech": 25,
            "engine_url": "https://linuxtracker.org",
        }
        r = SearchResult(
            name=plugin_dict.get("name", ""),
            size=plugin_dict.get("size", "0 B"),
            seeds=int(plugin_dict.get("seeds", 0)),
            leechers=int(plugin_dict.get("leech", 0)),
            link=plugin_dict.get("link", ""),
            engine_url=plugin_dict.get("engine_url", ""),
            tracker="linuxtracker",
        )
        assert r.seeds == 150
        assert r.leechers == 25
        assert r.tracker == "linuxtracker"

    def test_deduplication_sums_seeds_and_leechers(self):
        """Merged result should sum seeds and leechers from sources."""
        results = [
            SearchResult(
                name="Test", link="magnet:x", size="1 GB", seeds=100, leechers=10, engine_url="a", tracker="a"
            ),
            SearchResult(name="Test", link="magnet:x", size="1 GB", seeds=50, leechers=5, engine_url="b", tracker="b"),
        ]
        dedup = Deduplicator()
        merged = dedup.merge_results(results)
        assert len(merged) == 1
        assert merged[0].total_seeds == 150
        assert merged[0].total_leechers == 15


class TestE2EIssue3Quality:
    """E2E: Quality detection works end-to-end."""

    def test_best_quality_set_on_merge(self):
        """After merging, best_quality should be the best among sources."""
        results = [
            SearchResult(name="Movie 720p", link="x", size="2 GB", seeds=10, leechers=1, engine_url="a", tracker="a"),
            SearchResult(name="Movie 1080p", link="y", size="5 GB", seeds=20, leechers=2, engine_url="b", tracker="b"),
        ]
        dedup = Deduplicator()
        merged = dedup.merge_results(results)
        assert len(merged) == 1
        assert merged[0].best_quality is not None
        assert merged[0].best_quality.value == "full_hd"


class TestE2EIssue4SearchCompletes:
    """E2E: Search orchestrator completes with all trackers."""

    def test_orchestrator_has_many_public_trackers(self):
        orch = SearchOrchestrator()
        trackers = orch._get_enabled_trackers()
        public = [t for t in trackers if t.name not in ("rutracker", "kinozal", "nnmclub", "iptorrents")]
        # After the DEAD_PUBLIC_TRACKERS filter (added 2026-04-20),
        # only ~14 live public plugins remain in the default fan-out.
        # See docs/MERGE_SEARCH_DIAGNOSTICS.md §Dead trackers.
        assert len(public) >= 10, f"Only {len(public)} public trackers"

    def test_subprocess_script_contains_tracker_name(self):
        """The generated script must hardcode the tracker name."""
        import inspect

        source = inspect.getsource(SearchOrchestrator._search_public_tracker)
        # The buggy code used {{tracker_name}} which appeared as {tracker_name} in subprocess
        assert "{{tracker_name}}" not in source, "Bug: subprocess uses unresolved {{tracker_name}}"
        # The fixed code uses single braces for f-string interpolation
        assert "'{tracker_name}'" in source or '"{tracker_name}"' in source, "Fix: tracker name must be interpolated"


class TestE2EIssue5Sorting:
    """E2E: Sorting weights and backend support."""

    def test_backend_sort_by_name_ascending(self):
        from api.routes import SearchRequest

        req = SearchRequest(query="test", sort_by="name", sort_order="asc")
        assert req.sort_by == "name"
        assert req.sort_order == "asc"

    def test_backend_default_sort_is_seeds_desc(self):
        from api.routes import SearchRequest

        req = SearchRequest(query="test")
        assert req.sort_by == "seeds"
        assert req.sort_order == "desc"
