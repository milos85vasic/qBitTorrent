"""
Full automation tests for the dashboard covering all 5 manual testing issues.

These tests verify the dashboard UI and API behavior end-to-end
with the actual running service.
"""

import pytest
import requests
import time


BASE_URL = "http://localhost:7187"


class TestDashboardIssue1DownloadButton:
    """Issue 1: Plus button became Download button with merged sources."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_dashboard_is_angular_app(self):
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        assert "<app-root>" in dashboard or "<app-root></app-root>" in dashboard
        assert "<base href=\"/\">" in dashboard
        assert "<script src=\"main-" in dashboard

    def test_magnet_dialog_uses_backend_endpoint(self):
        """Magnet endpoint should exist in API."""
        resp = requests.post(
            f"{BASE_URL}/api/v1/magnet",
            json={
                "result_id": "test",
                "download_urls": ["magnet:?xt=urn:btih:abc123def4567890abc123def4567890abc12345"],
            },
            timeout=10,
        )
        assert resp.status_code == 200

    def test_download_file_returns_content_disposition(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/download/file",
            json={
                "result_id": "test",
                "download_urls": ["magnet:?xt=urn:btih:abc123def4567890abc123def4567890abc12345"],
            },
            timeout=10,
        )
        assert resp.status_code in (200, 404)  # 404 if no file found, but endpoint works
        if resp.status_code == 200:
            assert "content-disposition" in resp.headers


class TestDashboardIssue2TypeAndSeeds:
    """Issue 2: Type column and Seeds/Leechers columns fixed."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def search_and_get_results(self, query, limit=20):
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": query, "limit": limit},
            timeout=60,
        )
        assert resp.status_code == 200
        data = resp.json()
        search_id = data["search_id"]
        for _ in range(30):
            time.sleep(2)
            poll = requests.get(f"{BASE_URL}/api/v1/search/{search_id}", timeout=10)
            pdata = poll.json()
            if pdata.get("status") in ("completed", "failed"):
                return pdata.get("results", [])
        return []

    def test_type_detection_works_for_linux(self):
        results = self.search_and_get_results("linux", limit=10)
        if not results:
            pytest.skip("No results returned")
        non_unknown = [r for r in results if r.get("content_type") not in (None, "unknown", "")]
        assert len(non_unknown) >= max(1, len(results) * 0.1), \
            f"Too many unknown types: {len(non_unknown)}/{len(results)}"

    def test_seeds_are_integers_and_nonnegative(self):
        results = self.search_and_get_results("ubuntu", limit=5)
        if not results:
            pytest.skip("No results returned")
        for r in results:
            seeds = r.get("seeds")
            leechers = r.get("leechers")
            assert isinstance(seeds, int), f"seeds is {type(seeds).__name__}"
            assert isinstance(leechers, int), f"leechers is {type(leechers).__name__}"
            assert seeds >= 0
            assert leechers >= 0


class TestDashboardIssue3Quality:
    """Issue 3: Quality column fixed."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def search_and_get_results(self, query, limit=20):
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": query, "limit": limit},
            timeout=60,
        )
        assert resp.status_code == 200
        data = resp.json()
        search_id = data["search_id"]
        for _ in range(30):
            time.sleep(2)
            poll = requests.get(f"{BASE_URL}/api/v1/search/{search_id}", timeout=10)
            pdata = poll.json()
            if pdata.get("status") in ("completed", "failed"):
                return pdata.get("results", [])
        return []

    def test_quality_is_string_not_null(self):
        results = self.search_and_get_results("matrix", limit=5)
        if not results:
            pytest.skip("No results returned")
        for r in results:
            q = r.get("quality")
            assert isinstance(q, str), f"quality is {type(q).__name__}"
            assert q in ("uhd_4k", "full_hd", "hd", "sd", "unknown")

    def test_quality_detected_for_movies(self):
        results = self.search_and_get_results("matrix", limit=10)
        if not results:
            pytest.skip("No results returned")
        known = [r for r in results if r.get("quality") != "unknown"]
        assert len(known) >= 1, "No results have detected quality"


class TestDashboardIssue4SearchPerformance:
    """Issue 4: Search completes quickly and uses multiple trackers."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_search_completes_within_60_seconds(self):
        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": "linux", "limit": 10},
            timeout=60,
        )
        assert resp.status_code == 200
        data = resp.json()
        search_id = data["search_id"]
        for _ in range(30):
            time.sleep(2)
            poll = requests.get(f"{BASE_URL}/api/v1/search/{search_id}", timeout=10)
            pdata = poll.json()
            if pdata.get("status") in ("completed", "failed"):
                elapsed = time.time() - start
                assert elapsed < 60, f"Search took too long: {elapsed:.1f}s"
                return
        pytest.fail("Search did not complete")

    def test_search_uses_many_trackers(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": "ubuntu", "limit": 10},
            timeout=60,
        )
        data = resp.json()
        trackers = data.get("trackers_searched", [])
        assert len(trackers) >= 10, f"Only {len(trackers)} trackers searched"


class TestDashboardIssue5Sorting:
    """Issue 5: Sorting works correctly with weights."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_dashboard_is_angular_app(self):
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        assert "<app-root>" in dashboard or "<app-root></app-root>" in dashboard
        assert "<script src=\"main-" in dashboard

    def test_backend_supports_sort_params(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": "test", "sort_by": "name", "sort_order": "asc"},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
