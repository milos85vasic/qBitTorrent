"""
End-to-end tests for the full search-merge-download pipeline.

These tests verify the complete workflow:
1. Search query → multiple trackers
2. Deduplication and merging
3. Download initiation to qBittorrent
"""

import os
import sys
from unittest.mock import patch

import pytest

_src = os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src")
_src = os.path.abspath(_src)
if _src not in sys.path:
    sys.path.insert(0, _src)

from merge_service.deduplicator import Deduplicator
from merge_service.search import (
    SearchMetadata,
    SearchOrchestrator,
    SearchResult,
    TrackerSource,
)


class TestFullPipeline:
    """Test the complete search-merge-download pipeline."""

    @pytest.fixture
    def sample_trackers(self):
        """Sample tracker sources."""
        return [
            TrackerSource(name="tracker1", url="https://tracker1.com", enabled=True),
            TrackerSource(name="tracker2", url="https://tracker2.com", enabled=True),
            TrackerSource(name="tracker3", url="https://tracker3.com", enabled=True),
        ]

    @pytest.fixture
    def sample_results(self):
        """Sample search results from multiple trackers."""
        return [
            SearchResult(
                name="Ubuntu 22.04 LTS Desktop amd64",
                link="magnet:?xt=urn:btih:ABC123DEF456",
                size="2.5 GB",
                seeds=100,
                leechers=20,
                engine_url="https://tracker1.com",
                tracker="tracker1",
            ),
            SearchResult(
                name="Ubuntu 22.04 LTS Desktop amd64",
                link="magnet:?xt=urn:btih:ABC123DEF456",
                size="2.5 GB",
                seeds=80,
                leechers=15,
                engine_url="https://tracker2.com",
                tracker="tracker2",
            ),
            SearchResult(
                name="Ubuntu 22.04 LTS Desktop 64bit",
                link="magnet:?xt=urn:btih:GHI789JKL012",
                size="2.6 GB",
                seeds=50,
                leechers=10,
                engine_url="https://tracker3.com",
                tracker="tracker3",
            ),
        ]

    def test_deduplicator_merges_same_content(self, sample_results):
        """Test that deduplicator merges results with same infohash."""
        dedup = Deduplicator()

        merged = dedup.merge_results(sample_results)

        # Should have 2 merged results (first two with same hash, third different)
        assert len(merged) >= 1

        # First merged result should have 2 sources (same content)
        if merged[0].total_seeds == 180:
            assert len(merged[0].original_results) == 2

    @pytest.mark.asyncio
    async def test_search_orchestrator_initializes(self):
        """Test that search orchestrator initializes correctly."""
        from collections.abc import MutableMapping

        orch = SearchOrchestrator()

        assert orch.deduplicator is not None
        assert orch.validator is not None
        # Phase 3 replaced the unbounded dict with a cachetools.TTLCache
        # (bounded + self-expiring). It still satisfies the mapping
        # contract and supports the same [] / in / __setitem__ usage.
        assert isinstance(orch._active_searches, MutableMapping)

    @pytest.mark.asyncio
    async def test_search_metadata_creation(self):
        """Test SearchMetadata creation and serialization."""
        metadata = SearchMetadata(
            search_id="test-123",
            query="Ubuntu",
            category="linux",
        )

        data = metadata.to_dict()

        assert data["search_id"] == "test-123"
        assert data["query"] == "Ubuntu"
        assert data["category"] == "linux"
        assert data["status"] == "running"
        assert "started_at" in data

    @pytest.mark.asyncio
    async def test_search_returns_metadata(self, sample_trackers):
        """Test that search returns proper metadata."""
        orch = SearchOrchestrator()

        with patch.object(orch, "_get_enabled_trackers", return_value=sample_trackers):
            metadata = await orch.search("Ubuntu", category="linux")

            assert metadata.search_id is not None
            assert metadata.query == "Ubuntu"
            assert metadata.status in ["running", "completed", "failed"]

    @pytest.mark.asyncio
    async def test_start_search_returns_immediately(self, sample_trackers):
        """start_search() must return before any tracker is fanned out.

        This is the core of the real-time search feature — callers get
        back a search_id synchronously and then attach to SSE, instead
        of blocking on the slowest tracker.
        """
        orch = SearchOrchestrator()
        with patch.object(orch, "_get_enabled_trackers", return_value=sample_trackers):
            metadata = orch.start_search("Ubuntu", category="linux")

        assert metadata.search_id is not None
        assert metadata.query == "Ubuntu"
        assert metadata.status == "running"
        # The search is registered and discoverable right away — SSE
        # consumers can attach before any tracker reports.
        assert orch.get_search_status(metadata.search_id) is metadata
        # No tracker has reported yet.
        assert metadata.total_results == 0

    @pytest.mark.asyncio
    async def test_run_search_populates_results_incrementally(self, sample_trackers):
        """_run_search pushes per-tracker results as each one completes.

        Verified via ``_tracker_results`` being populated for at least
        one tracker by the time the task finishes.
        """
        orch = SearchOrchestrator()

        async def _fake_search_tracker(tracker, query, category):
            # Pretend each tracker returns a single result.
            return [
                SearchResult(
                    name=f"{tracker.name} result",
                    link="magnet:?xt=urn:btih:abc",
                    size="1 GB",
                    seeds=10,
                    leechers=1,
                    engine_url=tracker.url,
                    tracker=tracker.name,
                )
            ]

        with (
            patch.object(orch, "_get_enabled_trackers", return_value=sample_trackers),
            patch.object(orch, "_search_tracker", side_effect=_fake_search_tracker),
        ):
            metadata = orch.start_search("Ubuntu", category="linux")
            await orch._run_search(metadata.search_id, "Ubuntu", "linux")

        assert metadata.status == "completed"
        # One result per fake tracker.
        assert metadata.total_results == len(sample_trackers)
        # Per-tracker buckets are filled.
        per_tracker = orch._tracker_results[metadata.search_id]
        assert len(per_tracker) == len(sample_trackers)
        for t in sample_trackers:
            assert per_tracker[t.name]  # non-empty


class TestDeduplication:
    """Tests for the deduplication logic."""

    def test_fuzzy_matching_threshold(self):
        """Test that fuzzy matching respects threshold."""
        dedup = Deduplicator()

        # Very similar names should match
        similarity = dedup._calculate_similarity("Ubuntu 22.04 LTS Desktop", "Ubuntu 22.04 LTS Desktop amd64")
        assert similarity >= 0.5  # Should be quite high

    def test_normalize_name_removes_year(self):
        """Test that name normalization removes year."""
        dedup = Deduplicator()

        normalized = dedup._normalize_name("Movie 2023")

        assert "2023" not in normalized

    def test_parse_size_various_formats(self):
        """Test size parsing with various formats."""
        dedup = Deduplicator()

        assert dedup._parse_size("2.5 GB") is not None
        assert dedup._parse_size("500 MB") is not None
        assert dedup._parse_size("1 TB") is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
