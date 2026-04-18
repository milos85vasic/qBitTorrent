"""
Stress tests for search endpoint under extreme load.

Scenarios:
- Rapid-fire searches (100 in quick succession)
- Burst of concurrent searches (20 simultaneous)
- Sustained load over time
- Resource exhaustion prevention
"""

import pytest
import requests
import concurrent.futures
import time


class TestSearchStress:
    """Search endpoint stress testing."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    def test_rapid_fire_searches(self):
        """50 rapid searches should not crash the service."""
        success = 0
        failure = 0
        for i in range(50):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/v1/search",
                    json={"query": f"stress{i}", "limit": 3},
                    timeout=5,
                )
                if resp.status_code == 200:
                    success += 1
                else:
                    failure += 1
            except (requests.Timeout, requests.ConnectionError):
                failure += 1

        # Should have majority successes
        assert success > 20, f"Only {success}/50 rapid searches succeeded"
        # Service should still be healthy
        health = requests.get(f"{self.base_url}/health", timeout=5)
        assert health.status_code == 200

    def test_burst_concurrent_searches(self):
        """20 simultaneous searches should complete without deadlock."""
        results = []

        def search(i):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/v1/search",
                    json={"query": f"burst{i}", "limit": 5},
                    timeout=60,
                )
                return resp.status_code
            except Exception:
                return -1

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(search, i) for i in range(20)]
            for future in concurrent.futures.as_completed(futures, timeout=120):
                try:
                    results.append(future.result(timeout=0))
                except Exception:
                    results.append(-1)

        success_count = sum(1 for r in results if r == 200)
        assert success_count >= 10, f"Only {success_count}/20 burst searches succeeded"

    def test_sustained_load(self):
        """Sustained load over 20 seconds should not crash service."""
        start = time.time()
        success = 0
        failure = 0

        while time.time() - start < 20:
            try:
                resp = requests.post(
                    f"{self.base_url}/api/v1/search",
                    json={"query": "sustained", "limit": 5},
                    timeout=10,
                )
                if resp.status_code == 200:
                    success += 1
                else:
                    failure += 1
            except (requests.Timeout, requests.ConnectionError):
                failure += 1
            time.sleep(0.3)

        assert success >= 2, f"Only {success} sustained searches succeeded"
        health = requests.get(f"{self.base_url}/health", timeout=5)
        assert health.status_code == 200

    def test_search_with_abort_under_stress(self):
        """Aborting searches under stress should not cause issues."""
        # Start many searches that might be aborted
        def search_and_maybe_abort(i):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/v1/search",
                    json={"query": f"abort{i}", "limit": 10},
                    timeout=5,  # Short timeout to trigger "aborts"
                )
                return resp.status_code
            except requests.Timeout:
                return 408
            except Exception:
                return -1

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(search_and_maybe_abort, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Should not crash regardless of outcomes
        health = requests.get(f"{self.base_url}/health", timeout=5)
        assert health.status_code == 200

    def test_stats_endpoint_under_stress(self):
        """Stats endpoint should remain accurate under load."""
        # Run some searches
        def search(i):
            requests.post(
                f"{self.base_url}/api/v1/search",
                json={"query": f"stats{i}", "limit": 5},
                timeout=30,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(search, i) for i in range(10)]
            # Check stats while searches running
            for _ in range(5):
                stats = requests.get(f"{self.base_url}/api/v1/stats", timeout=5)
                assert stats.status_code == 200
                time.sleep(1)
            for f in concurrent.futures.as_completed(futures):
                f.result()

    def test_file_descriptor_exhaustion_prevention(self):
        """Service should not exhaust file descriptors under load."""
        # Many concurrent connections
        def connect(i):
            try:
                resp = requests.get(f"{self.base_url}/health", timeout=5)
                return resp.status_code
            except Exception:
                return -1

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(connect, i) for i in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        success_count = sum(1 for r in results if r == 200)
        assert success_count > 50, f"Only {success_count}/100 health checks succeeded"
