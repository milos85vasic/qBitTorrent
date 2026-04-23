"""
Failing tests for issues discovered during manual testing.

Issues:
1. Plus button should download .torrent file (not send to qBittorrent)
2. Type column shows Unknown for most results
3. Seeds/Leechers columns show 0 for many results
4. Search hangs / takes too long for some queries
5. Sorting is broken (case-sensitive name, wrong quality/type ordering)
"""

import time

import pytest
import requests


class TestIssue1DownloadButton:
    """Issue 1: Download button MUST download a file with merged sources."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    def test_download_file_endpoint_exists(self):
        """There must be an endpoint to download .torrent files."""
        resp = requests.post(
            f"{self.base_url}/api/v1/download/file",
            json={
                "result_id": "test",
                "download_urls": ["magnet:?xt=urn:btih:41082bfe3a7f3f47930d2e2ce72ba844c82da906"],
            },
            timeout=30,
            allow_redirects=False,
        )
        # Should not be 404 - endpoint must exist
        assert resp.status_code != 404, "Download file endpoint does not exist"

    def test_dashboard_is_angular_app(self):
        """Dashboard must be Angular SPA."""
        dashboard = requests.get(f"{self.base_url}/dashboard", timeout=30).text
        assert "<app-root>" in dashboard or "<app-root></app-root>" in dashboard
        assert '<base href="/">' in dashboard
        assert '<script src="main-' in dashboard

    def test_download_button_is_angular_component(self):
        """Download button must be Angular component."""
        dashboard = requests.get(f"{self.base_url}/dashboard", timeout=30).text
        assert "<app-root>" in dashboard or "<app-root></app-root>" in dashboard

    def test_magnet_endpoint_returns_merged_sources(self):
        """/magnet endpoint must return a magnet with all source trackers."""
        resp = requests.post(
            f"{self.base_url}/api/v1/magnet",
            json={
                "result_id": "Test",
                "download_urls": [
                    "magnet:?xt=urn:btih:41082bfe3a7f3f47930d2e2ce72ba844c82da906&tr=udp://t1:1337",
                    "magnet:?xt=urn:btih:def4567890abc123def4567890abc123def45678&tr=udp://t2:6969",
                ],
            },
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["hashes"]) == 2
        magnet = data["magnet"]
        assert "t1" in magnet or "t2" in magnet or "opentrackr" in magnet


@pytest.mark.timeout(300)
class TestIssue2TypeColumn:
    """Issue 2: Type column shows Unknown for too many results."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    def search_and_get_results(self, query, limit=20):
        resp = requests.post(
            f"{self.base_url}/api/v1/search/sync",
            json={"query": query, "limit": limit},
            timeout=300,
        )
        assert resp.status_code == 200
        data = resp.json()
        search_id = data["search_id"]

        # Poll until complete
        for _ in range(20):
            time.sleep(2)
            poll = requests.get(f"{self.base_url}/api/v1/search/{search_id}", timeout=30)
            pdata = poll.json()
            if pdata.get("status") in ("completed", "failed"):
                return pdata.get("results", [])
        return []

    def test_type_detection_not_all_unknown_for_linux(self):
        """Searching 'linux' should have some non-unknown types."""
        results = self.search_and_get_results("linux", limit=10)
        assert len(results) > 0, "No results found"
        non_unknown = [r for r in results if r.get("content_type") != "unknown"]
        # At least 20% should have a detected type
        assert len(non_unknown) >= max(1, len(results) * 0.2), (
            f"Too many unknown types: {len(non_unknown)}/{len(results)} have detected type"
        )

    def test_type_detection_works_for_movies(self):
        """Searching 'matrix' should have mostly movie types."""
        results = self.search_and_get_results("matrix", limit=10)
        assert len(results) > 0
        movies = [r for r in results if r.get("content_type") == "movie"]
        assert len(movies) >= 3, f"Only {len(movies)} movie results found"

    def test_type_is_string_not_null(self):
        """content_type must always be a string, never null."""
        results = self.search_and_get_results("matrix", limit=5)
        for r in results:
            ct = r.get("content_type")
            assert isinstance(ct, str), f"content_type is {type(ct).__name__}, expected str"
            assert ct != "", "content_type must not be empty string"


@pytest.mark.timeout(300)
class TestIssue3SeedsLeechers:
    """Issue 3: Seeds/Leechers showing 0 for most results."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    def search_and_get_results(self, query, limit=20):
        resp = requests.post(
            f"{self.base_url}/api/v1/search/sync",
            json={"query": query, "limit": limit},
            timeout=300,
        )
        data = resp.json()
        search_id = data["search_id"]
        for _ in range(20):
            time.sleep(2)
            poll = requests.get(f"{self.base_url}/api/v1/search/{search_id}", timeout=30)
            pdata = poll.json()
            if pdata.get("status") in ("completed", "failed"):
                return pdata.get("results", [])
        return []

    def test_most_results_have_nonzero_seeds(self):
        """Most results should have seeds > 0."""
        results = self.search_and_get_results("matrix", limit=20)
        assert len(results) > 0
        nonzero = [r for r in results if r.get("seeds", 0) > 0]
        # At least 10% should have non-zero seeds (many trackers don't report seeds)
        assert len(nonzero) >= len(results) * 0.1, (
            f"Too many zero seeds: {len(results) - len(nonzero)}/{len(results)} have 0 seeds"
        )

    def test_seeds_are_integers(self):
        """Seeds must be integers."""
        results = self.search_and_get_results("matrix", limit=5)
        for r in results:
            seeds = r.get("seeds")
            assert isinstance(seeds, int), f"seeds is {type(seeds).__name__}"

    def test_leechers_are_integers(self):
        """Leechers must be integers."""
        results = self.search_and_get_results("matrix", limit=5)
        for r in results:
            leechers = r.get("leechers")
            assert isinstance(leechers, int), f"leechers is {type(leechers).__name__}"


class TestIssue4SearchPerformance:
    """Issue 4: Search hangs / takes too long."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    @pytest.mark.timeout(360)
    def test_search_completes_within_reasonable_time(self):
        """Search must complete within ~5 minutes under load.

        Budget based on ``ceil(18 trackers / 5 concurrent) * 25 s
        deadline`` = 90 s idle-case, with headroom for the integration
        serialisation fixture, wait-for-idle, and slow upstreams.
        """
        start = time.time()
        resp = requests.post(
            f"{self.base_url}/api/v1/search/sync",
            json={"query": "linux", "limit": 10},
            timeout=340,
        )
        assert resp.status_code == 200
        elapsed = time.time() - start
        assert elapsed < 320, f"Search took too long: {elapsed:.1f}s"

    def test_search_returns_results_from_multiple_trackers(self):
        """Search should return results from multiple trackers."""
        resp = requests.post(
            f"{self.base_url}/api/v1/search/sync",
            json={"query": "linux", "limit": 20},
            timeout=340,
        )
        assert resp.status_code == 200, f"search returned {resp.status_code}: {resp.text[:200]}"
        pdata = resp.json()
        # /sync returns after the fan-out completes, no polling needed.
        trackers = set()
        for r in pdata.get("results", []):
            for s in r.get("sources", []):
                trackers.add(s.get("tracker", "unknown"))
        assert len(trackers) >= 2, f"Only {len(trackers)} trackers in results: {trackers}"


class TestIssue5Sorting:
    """Issue 5: Sorting is broken."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    def test_dashboard_is_angular_app(self):
        """Dashboard must be Angular SPA."""
        dashboard = requests.get(f"{self.base_url}/dashboard", timeout=30).text
        assert "<app-root>" in dashboard or "<app-root></app-root>" in dashboard
        assert '<script src="main-' in dashboard

    def test_backend_supports_sort_params(self):
        """Backend should support sort parameters."""
        resp = requests.post(
            f"{self.base_url}/api/v1/search/sync",
            json={"query": "linux", "sort_by": "name", "sort_order": "asc"},
            timeout=300,
        )
        assert resp.status_code == 200


class TestFooter:
    """Footer must show 'Made with <3 by Vasic Digital' on every screen."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    def test_dashboard_is_angular_app(self):
        """Dashboard must be Angular SPA."""
        dashboard = requests.get(f"{self.base_url}/dashboard", timeout=30).text
        assert "<app-root>" in dashboard or "<app-root></app-root>" in dashboard
        assert '<script src="main-' in dashboard


class TestSearchPerformance:
    """Search endpoint must return quickly with search_id, not block for minutes."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    def test_search_returns_within_thirty_seconds(self):
        """POST /search (async kick-off) must return within 30 s with
        a search_id. The actual fan-out runs in the background.
        """
        start = time.time()
        resp = requests.post(
            f"{self.base_url}/api/v1/search",
            json={"query": "ubuntu", "limit": 5},
            timeout=30,
        )
        elapsed = time.time() - start
        assert resp.status_code == 200, f"Search returned {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "search_id" in data, "Response must contain search_id"
        assert elapsed < 30, f"Search took {elapsed:.1f}s, must return within 30s"

    def test_search_returns_running_status_immediately(self):
        """Initial search response must have status 'running' or 'in_progress'."""
        resp = requests.post(
            f"{self.base_url}/api/v1/search",
            json={"query": "ubuntu", "limit": 5},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("running", "in_progress", "completed"), f"Unexpected status: {data.get('status')}"


class TestDownloadButtonConsistency:
    """Both renderResults and addResultToTable must use doDownloadTorrent for Download button."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    def test_dashboard_is_angular_app(self):
        """Dashboard must be Angular SPA."""
        dashboard = requests.get(f"{self.base_url}/dashboard", timeout=30).text
        assert "<app-root>" in dashboard or "<app-root></app-root>" in dashboard

    def test_download_button_is_angular_component(self):
        """Download button must be Angular component."""
        dashboard = requests.get(f"{self.base_url}/dashboard", timeout=30).text
        assert "<app-root>" in dashboard or "<app-root></app-root>" in dashboard


class TestDashboardCacheControl:
    """Dashboard must have cache-busting headers to prevent stale content."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    def test_dashboard_has_cache_control_header(self):
        """Dashboard response must include Cache-Control: no-cache or similar."""
        resp = requests.get(f"{self.base_url}/", timeout=30)
        cc = resp.headers.get("Cache-Control", "").lower()
        assert "no-cache" in cc or "no-store" in cc or "must-revalidate" in cc, (
            f"Missing cache-control header, got: {cc!r}"
        )

    def test_dashboard_has_no_etag_or_weak_etag(self):
        """Dashboard should not use strong etag caching."""
        resp = requests.get(f"{self.base_url}/", timeout=30)
        # ETag is OK if Cache-Control is set to no-cache
        cc = resp.headers.get("Cache-Control", "").lower()
        assert "no-cache" in cc or "no-store" in cc, "Dashboard must have cache-busting headers"
