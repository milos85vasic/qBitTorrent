"""
Benchmark tests for search throughput.

Scenarios:
- Search with many trackers (timing)
- Search result serialization performance
- Memory usage with large result sets
"""

import time

import pytest
import requests


class TestSearchBenchmark:
    """Benchmark search API performance."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    @pytest.mark.timeout(120)
    def test_search_with_few_trackers(self):
        """Search with few trackers should be fast."""
        start = time.time()
        resp = requests.post(
            f"{self.base_url}/api/v1/search",
            json={"query": "ubuntu", "limit": 10, "trackers": ["piratebay"]},
            timeout=60,
        )
        elapsed = time.time() - start

        assert resp.status_code == 200
        # 60s CI-friendly ceiling. Single-tracker p50 is ~5-10s locally
        # but CI runners + network-bound trackers can hit ~30-40s.
        assert elapsed < 60, f"Single tracker search took {elapsed:.1f}s"

    @pytest.mark.timeout(180)
    def test_search_result_count_performance(self):
        """Search returning many results should not slow down."""
        start = time.time()
        resp = requests.post(
            f"{self.base_url}/api/v1/search",
            json={"query": "ubuntu", "limit": 100},
            timeout=120,
        )
        elapsed = time.time() - start

        assert resp.status_code == 200
        # Full multi-tracker fan-out; 90s ceiling is realistic against
        # the live stack. Serialization overhead alone is tiny.
        assert elapsed < 90, f"Large result search took {elapsed:.1f}s"

    @pytest.mark.timeout(180)
    def test_search_response_size(self):
        """Search response should not be excessively large."""
        resp = requests.post(
            f"{self.base_url}/api/v1/search",
            json={"query": "ubuntu", "limit": 50},
            timeout=120,
        )
        assert resp.status_code == 200
        # Response should be under 1MB even for 50 results
        assert len(resp.content) < 1024 * 1024, f"Response too large: {len(resp.content)} bytes"

    @pytest.mark.timeout(300)
    def test_repeated_search_consistency(self):
        """Repeated identical searches should have consistent timing."""
        times = []
        for _ in range(3):  # Reduced from 5 so the test fits comfortably in a CI budget.
            start = time.time()
            resp = requests.post(
                f"{self.base_url}/api/v1/search",
                json={"query": "ubuntu", "limit": 10},
                timeout=60,
            )
            elapsed = time.time() - start
            if resp.status_code == 200:
                times.append(elapsed)
            time.sleep(1)

        assert len(times) >= 2, f"too few successful searches: {len(times)}"
        avg = sum(times) / len(times)
        max_time = max(times)
        # Max should not be more than 4x average (allow CI noise).
        assert max_time < avg * 4, f"Search time inconsistent: avg={avg:.1f}s, max={max_time:.1f}s"

    def test_dashboard_load_time(self):
        """Dashboard should load quickly."""
        start = time.time()
        # The Angular SPA is served at '/', not '/dashboard'.
        resp = requests.get(f"{self.base_url}/", timeout=10)
        elapsed = time.time() - start

        assert resp.status_code == 200
        # Static SPA shell → sub-2s easily.
        assert elapsed < 2, f"Dashboard took {elapsed:.1f}s to load"
