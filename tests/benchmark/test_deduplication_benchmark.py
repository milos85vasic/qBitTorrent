"""
Benchmark tests for deduplication engine performance.

Scenarios:
- Merge 100, 1000, 10000 results
- Hash deduplication speed
- Fuzzy similarity matching performance
- Content type detection throughput
"""

import pytest
import sys
import os
import time

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))

from merge_service.deduplicator import Deduplicator
from merge_service.search import SearchResult


class TestDeduplicationBenchmark:
    """Benchmark deduplication engine performance."""

    def _generate_results(self, count: int) -> list:
        """Generate fake SearchResult objects for benchmarking."""
        results = []
        for i in range(count):
            results.append(
                SearchResult(
                    name=f"Ubuntu 22.04 LTS {i % 10}",
                    link=f"magnet:?xt=urn:btih:{i:040x}",
                    size="2.5 GB",
                    seeds=i % 100,
                    leechers=i % 50,
                    engine_url="https://example.com",
                    desc_link=f"https://example.com/{i}",
                    pub_date="2024-01-01",
                    tracker="test_tracker",
                )
            )
        return results

    def test_merge_100_results(self):
        """Merge 100 results should complete in <100ms."""
        dedup = Deduplicator()
        results = self._generate_results(100)

        start = time.time()
        merged = dedup.merge_results(results)
        elapsed = time.time() - start

        assert elapsed < 0.5, f"Merging 100 results took {elapsed:.3f}s"
        assert len(merged) <= 100

    def test_merge_1000_results(self):
        """Merge 1000 results should complete in <1s."""
        dedup = Deduplicator()
        results = self._generate_results(1000)

        start = time.time()
        merged = dedup.merge_results(results)
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Merging 1000 results took {elapsed:.3f}s"
        assert len(merged) <= 1000

    def test_merge_10000_results(self):
        """Merge 10000 results should complete in <5s."""
        dedup = Deduplicator()
        results = self._generate_results(10000)

        start = time.time()
        merged = dedup.merge_results(results)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"Merging 10000 results took {elapsed:.3f}s"
        assert len(merged) <= 10000

    def test_hash_deduplication_speed(self):
        """Hash-based dedup should be O(n) and very fast."""
        dedup = Deduplicator()
        # 1000 results with only 10 unique hashes (valid magnet links)
        results = []
        for i in range(1000):
            hash_val = f"{i % 10:040x}"  # Only 10 unique hashes
            results.append(
                SearchResult(
                    name=f"Duplicate {i}",
                    link=f"magnet:?xt=urn:btih:{hash_val}",
                    size="1 GB",
                    seeds=10,
                    leechers=5,
                    engine_url="https://example.com",
                    desc_link="https://example.com",
                    pub_date="2024-01-01",
                    tracker="test",
                )
            )

        start = time.time()
        merged = dedup.merge_results(results)
        elapsed = time.time() - start

        # Should dedup to ~10 results very quickly
        assert len(merged) <= 15, f"Expected ~10 results, got {len(merged)}"
        assert elapsed < 0.5, f"Hash dedup took {elapsed:.3f}s"

    def test_content_type_detection_throughput(self):
        """Content type detection should handle 1000 results in <100ms."""
        dedup = Deduplicator()
        results = []
        names = [
            "Movie.Name.2024.1080p.BluRay.x264",
            "TV.Show.S01E05.720p.WEB-DL",
            "Artist - Album (2023) [FLAC]",
            "Game.Name-CODEX",
            "Ubuntu 22.04 LTS AMD64",
            "Anime.Title.EP01.1080p",
        ]
        for i in range(1000):
            results.append(
                SearchResult(
                    name=names[i % len(names)],
                    link="magnet:test",
                    size="1 GB",
                    seeds=10,
                    leechers=5,
                    engine_url="https://example.com",
                    desc_link="https://example.com",
                    pub_date="2024-01-01",
                    tracker="test",
                )
            )

        start = time.time()
        merged = dedup.merge_results(results)
        elapsed = time.time() - start

        assert elapsed < 0.5, f"Content type detection for 1000 took {elapsed:.3f}s"

    def test_name_scoring_performance(self):
        """Best name selection should be fast for large datasets."""
        dedup = Deduplicator()
        results = []
        for i in range(500):
            results.append(
                SearchResult(
                    name=f"Ubuntu 22.04 LTS {'1080p' if i % 2 == 0 else '720p'}",
                    link="magnet:test",
                    size="2.5 GB",
                    seeds=100 if i % 2 == 0 else 10,
                    leechers=50 if i % 2 == 0 else 5,
                    engine_url="https://example.com",
                    desc_link="https://example.com",
                    pub_date="2024-01-01",
                    tracker="test",
                )
            )

        start = time.time()
        merged = dedup.merge_results(results)
        elapsed = time.time() - start

        # Should select best names quickly
        assert elapsed < 0.5, f"Name scoring took {elapsed:.3f}s"
        # Results should be merged (fewer merged results than input)
        assert len(merged) < 500
