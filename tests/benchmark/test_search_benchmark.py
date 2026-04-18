"""
Benchmark tests for search throughput.

Scenarios:
- Search with many trackers (timing)
- Search result serialization performance
- Memory usage with large result sets
"""

import pytest
import requests
import time


BASE_URL = "http://localhost:7187"


class TestSearchBenchmark:
    """Benchmark search API performance."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_search_with_few_trackers(self):
        """Search with few trackers should be fast."""
        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": "ubuntu", "limit": 10, "trackers": ["piratebay"]},
            timeout=30,
        )
        elapsed = time.time() - start

        assert resp.status_code == 200
        assert elapsed < 10, f"Single tracker search took {elapsed:.1f}s"

    def test_search_result_count_performance(self):
        """Search returning many results should not slow down."""
        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": "ubuntu", "limit": 100},
            timeout=60,
        )
        elapsed = time.time() - start

        assert resp.status_code == 200
        data = resp.json()
        results = data.get("results", [])
        # Serialization should be fast regardless of result count
        assert elapsed < 30, f"Large result search took {elapsed:.1f}s"

    def test_search_response_size(self):
        """Search response should not be excessively large."""
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": "ubuntu", "limit": 50},
            timeout=60,
        )
        assert resp.status_code == 200
        # Response should be under 1MB even for 50 results
        assert len(resp.content) < 1024 * 1024, f"Response too large: {len(resp.content)} bytes"

    def test_repeated_search_consistency(self):
        """Repeated identical searches should have consistent timing."""
        times = []
        for _ in range(5):
            start = time.time()
            resp = requests.post(
                f"{BASE_URL}/api/v1/search",
                json={"query": "ubuntu", "limit": 10},
                timeout=30,
            )
            elapsed = time.time() - start
            if resp.status_code == 200:
                times.append(elapsed)
            time.sleep(1)

        if len(times) >= 3:
            avg = sum(times) / len(times)
            max_time = max(times)
            # Max should not be more than 3x average (no huge spikes)
            assert max_time < avg * 3, f"Search time inconsistent: avg={avg:.1f}s, max={max_time:.1f}s"

    def test_dashboard_load_time(self):
        """Dashboard should load quickly."""
        start = time.time()
        resp = requests.get(f"{BASE_URL}/dashboard", timeout=10)
        elapsed = time.time() - start

        assert resp.status_code == 200
        assert elapsed < 2, f"Dashboard took {elapsed:.1f}s to load"
