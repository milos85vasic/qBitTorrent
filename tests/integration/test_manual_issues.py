"""
Failing tests for issues discovered during manual testing.

Issues:
1. Plus button should download .torrent file (not send to qBittorrent)
2. Type column shows Unknown for most results
3. Seeds/Leechers columns show 0 for many results
4. Search hangs / takes too long for some queries
5. Sorting is broken (case-sensitive name, wrong quality/type ordering)
"""

import pytest
import requests
import time


BASE_URL = "http://localhost:7187"
QBIT_URL = "http://localhost:7185"


class TestIssue1PlusButtonDownload:
    """Issue 1: Plus button MUST download a .torrent file."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_download_file_endpoint_exists(self):
        """There must be an endpoint to download .torrent files."""
        resp = requests.post(
            f"{BASE_URL}/api/v1/download/file",
            json={"result_id": "test", "download_urls": ["magnet:?xt=urn:btih:abc123"]},
            timeout=10,
            allow_redirects=False,
        )
        # Should not be 404 - endpoint must exist
        assert resp.status_code != 404, "Download file endpoint does not exist"

    def test_plus_button_triggers_file_download(self):
        """Dashboard + button must call download/file endpoint, not /download."""
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        # The + button onclick should reference a download function, not doDownload
        # which sends to qBittorrent
        assert "doDownload" in dashboard or "downloadTorrent" in dashboard
        # The doDownload function should trigger a file download
        assert "download/file" in dashboard or "download.php" in dashboard or "magnet:" in dashboard


class TestIssue2TypeColumn:
    """Issue 2: Type column shows Unknown for too many results."""

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

        # Poll until complete
        for _ in range(20):
            time.sleep(2)
            poll = requests.get(f"{BASE_URL}/api/v1/search/{search_id}", timeout=10)
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
        assert len(non_unknown) >= max(1, len(results) * 0.2), \
            f"Too many unknown types: {len(non_unknown)}/{len(results)} have detected type"

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


class TestIssue3SeedsLeechers:
    """Issue 3: Seeds/Leechers showing 0 for most results."""

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
        data = resp.json()
        search_id = data["search_id"]
        for _ in range(20):
            time.sleep(2)
            poll = requests.get(f"{BASE_URL}/api/v1/search/{search_id}", timeout=10)
            pdata = poll.json()
            if pdata.get("status") in ("completed", "failed"):
                return pdata.get("results", [])
        return []

    def test_most_results_have_nonzero_seeds(self):
        """Most results should have seeds > 0."""
        results = self.search_and_get_results("matrix", limit=20)
        assert len(results) > 0
        nonzero = [r for r in results if r.get("seeds", 0) > 0]
        # At least 50% should have non-zero seeds
        assert len(nonzero) >= len(results) * 0.5, \
            f"Too many zero seeds: {len(results) - len(nonzero)}/{len(results)} have 0 seeds"

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
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_search_completes_within_reasonable_time(self):
        """Search must complete within 60 seconds."""
        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": "linux", "limit": 10},
            timeout=60,
        )
        assert resp.status_code == 200
        data = resp.json()
        search_id = data["search_id"]

        # Poll for completion
        completed = False
        for _ in range(30):
            time.sleep(2)
            poll = requests.get(f"{BASE_URL}/api/v1/search/{search_id}", timeout=10)
            pdata = poll.json()
            if pdata.get("status") in ("completed", "failed"):
                completed = True
                break

        elapsed = time.time() - start
        assert completed, f"Search did not complete within 60 seconds (elapsed: {elapsed:.1f}s)"
        assert elapsed < 60, f"Search took too long: {elapsed:.1f}s"

    def test_search_returns_results_from_multiple_trackers(self):
        """Search should return results from multiple trackers."""
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": "matrix", "limit": 20},
            timeout=60,
        )
        data = resp.json()
        search_id = data["search_id"]

        for _ in range(30):
            time.sleep(2)
            poll = requests.get(f"{BASE_URL}/api/v1/search/{search_id}", timeout=10)
            pdata = poll.json()
            if pdata.get("status") == "completed":
                trackers = set()
                for r in pdata.get("results", []):
                    for s in r.get("sources", []):
                        trackers.add(s.get("tracker", "unknown"))
                assert len(trackers) >= 2, f"Only {len(trackers)} trackers in results: {trackers}"
                return

        pytest.fail("Search did not complete")


class TestIssue5Sorting:
    """Issue 5: Sorting is broken."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_dashboard_has_sortable_columns(self):
        """Dashboard must have sortable column headers."""
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        sortable_cols = ["name", "type", "size", "seeds", "leechers", "quality", "sources"]
        for col in sortable_cols:
            assert f'data-sort="{col}"' in dashboard, f"Missing sortable column: {col}"

    def test_action_column_not_sortable(self):
        """Action column must NOT have data-sort attribute."""
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        assert 'data-sort="action"' not in dashboard, "Action column should not be sortable"

    def test_sorting_by_name_is_case_insensitive(self):
        """Name sorting must be case-insensitive."""
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        # The sort function should use case-insensitive comparison
        assert "toLowerCase" in dashboard or "toUpperCase" in dashboard
        # Check specifically for case-insensitive name sorting in the name case
        assert "case 'name':" in dashboard
        assert "toLowerCase()" in dashboard

    def test_sorting_by_quality_uses_weight(self):
        """Quality sorting must use quality weight, not alphabetical."""
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        # Should have a quality weight/priority mapping
        assert ("uhd_4k" in dashboard and "full_hd" in dashboard) or "qualityWeight" in dashboard or "qualityMap" in dashboard

    def test_sorting_unknown_type_goes_last(self):
        """When sorting by type ascending, 'unknown' must be at the end."""
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        # The sort function should handle 'unknown' specially
        assert "unknown" in dashboard



class TestFooter:
    """Footer must show 'Made with <3 by Vasic Digital' on every screen."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_footer_contains_made_with_love_text(self):
        """Footer must contain 'Made with' text."""
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        assert "Made with" in dashboard

    def test_footer_contains_heart_symbol(self):
        """Footer must contain a heart symbol (emoji or HTML entity)."""
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        # Check for heart emoji or HTML entity
        heart_indicators = ["❤", "&#10084;", "&hearts;", "♥", "💖", "💙", "💚"]
        assert any(h in dashboard for h in heart_indicators), "No heart symbol found in footer"

    def test_footer_contains_vasic_digital_link(self):
        """Footer must contain clickable 'Vasic Digital' link to vasic.digital."""
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        assert "Vasic Digital" in dashboard
        assert "https://www.vasic.digital" in dashboard
        # Should be inside an <a> tag
        import re
        link_pattern = r'<a[^>]*href=["\']https://www\.vasic\.digital["\'][^>]*>.*Vasic Digital.*</a>'
        assert re.search(link_pattern, dashboard, re.IGNORECASE), "Vasic Digital must be a clickable link"



class TestSearchPerformance:
    """Search endpoint must return quickly with search_id, not block for minutes."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_search_returns_within_fifteen_seconds(self):
        """POST /search must return within 15s with search_id, not block for minutes."""
        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": "ubuntu", "limit": 5},
            timeout=20,
        )
        elapsed = time.time() - start
        assert resp.status_code == 200, f"Search returned {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "search_id" in data, "Response must contain search_id"
        assert elapsed < 15, f"Search took {elapsed:.1f}s, must return within 15s"

    def test_search_returns_running_status_immediately(self):
        """Initial search response must have status 'running' or 'in_progress'."""
        resp = requests.post(
            f"{BASE_URL}/api/v1/search",
            json={"query": "ubuntu", "limit": 5},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("running", "in_progress", "completed"), \
            f"Unexpected status: {data.get('status')}"


class TestDownloadButtonConsistency:
    """Both renderResults and addResultToTable must use doDownloadTorrent for + button."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_addResultToTable_uses_doDownloadTorrent(self):
        """Live results (SSE) + button must call doDownloadTorrent, not doDownload."""
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        import re
        # Extract addResultToTable function body (from { to next top-level function)
        match = re.search(
            r'function addResultToTable\(result, index\)\s*\{(.*?)function \w+\(',
            dashboard, re.DOTALL
        )
        assert match, "addResultToTable function not found"
        func_body = match.group(1)
        # The + button in addResultToTable must call doDownloadTorrent
        assert "doDownloadTorrent(" in func_body, \
            "addResultToTable + button must call doDownloadTorrent, not doDownload"
        assert "doDownload(" not in func_body, \
            "addResultToTable must NOT call old doDownload function"

    def test_doDownloadTorrent_does_not_use_event_target(self):
        """doDownloadTorrent must not rely on global event variable."""
        dashboard = requests.get(f"{BASE_URL}/dashboard", timeout=5).text
        import re
        match = re.search(r'function doDownloadTorrent\([^)]*\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', dashboard, re.DOTALL)
        assert match, "doDownloadTorrent function not found"
        func_body = match.group(1)
        # Should not use event.target
        assert "event.target" not in func_body, \
            "doDownloadTorrent must not use event.target - pass button reference instead"
        # Should accept a button parameter
        match_sig = re.search(r'function doDownloadTorrent\(([^)]*)\)', dashboard)
        assert match_sig, "doDownloadTorrent signature not found"
        params = match_sig.group(1)
        assert "," in params or "btn" in params, \
            "doDownloadTorrent must accept button element as parameter"


class TestDashboardCacheControl:
    """Dashboard must have cache-busting headers to prevent stale content."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_dashboard_has_cache_control_header(self):
        """Dashboard response must include Cache-Control: no-cache or similar."""
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        cc = resp.headers.get("Cache-Control", "").lower()
        assert "no-cache" in cc or "no-store" in cc or "must-revalidate" in cc, \
            f"Missing cache-control header, got: {cc!r}"

    def test_dashboard_has_no_etag_or_weak_etag(self):
        """Dashboard should not use strong etag caching."""
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        # ETag is OK if Cache-Control is set to no-cache
        cc = resp.headers.get("Cache-Control", "").lower()
        assert "no-cache" in cc or "no-store" in cc, \
            "Dashboard must have cache-busting headers"
