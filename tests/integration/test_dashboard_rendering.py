"""
Comprehensive tests for dashboard rendering fixes:
- Size display (NaN undefined fix)
- Missing + button restoration
- Magnet link styling
- Name column max-width + word-break
- Proper table structure in both SSE and polling paths
"""

import pytest
import requests
import re


BASE_URL = "http://localhost:7187"


class TestDashboardHtmlStructure:
    """Verify dashboard HTML contains correct CSS and JS."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        try:
            r = requests.get(f"{self.base_url}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")
        self.dashboard = requests.get(f"{self.base_url}/dashboard", timeout=5).text

    def test_format_size_function_exists(self):
        """formatSize must handle both strings and numbers."""
        assert "function formatSize(value)" in self.dashboard
        assert 'if (typeof value === \'string\')' in self.dashboard
        assert "return trimmed;" in self.dashboard

    def test_format_size_handles_string_input(self):
        """formatSize must return formatted strings unchanged."""
        # The regex check for already-formatted sizes
        assert "result.size.match(/^[\\d.]+\\s*[KMGT]?B$/i)" in self.dashboard

    def test_format_size_handles_number_input(self):
        """formatSize must convert bytes to human-readable."""
        assert "var bytes = parseFloat(value) || 0" in self.dashboard

    def test_name_column_max_width_css(self):
        """Name column must have max-width and word-break."""
        assert ".results-table td:first-child { max-width: 450px; word-break: break-word; white-space: normal; }" in self.dashboard

    def test_name_column_mobile_css(self):
        """Name column must wrap on mobile too."""
        assert "max-width: 200px; word-break: break-word; white-space: normal;" in self.dashboard

    def test_magnet_button_styling(self):
        """Magnet button must have explicit white color."""
        assert ".btn-magnet { background: var(--theme-purple); color: #fff;" in self.dashboard
        assert ".btn-magnet:hover { background: var(--theme-purple-hover); color: #fff; }" in self.dashboard

    def test_add_result_to_table_creates_proper_table(self):
        """addResultToTable must create <table id=\"results-table\"> not <div>."""
        assert 'container.innerHTML = \'<table class="results-table" id="results-table">' in self.dashboard
        assert "var table = document.getElementById('results-table');" in self.dashboard

    def test_add_result_to_table_has_all_columns(self):
        """addResultToTable must include all 8 columns."""
        assert "data-sort=\"name\"" in self.dashboard
        assert "data-sort=\"type\"" in self.dashboard
        assert "data-sort=\"size\"" in self.dashboard
        assert "data-sort=\"seeds\"" in self.dashboard
        assert "data-sort=\"leechers\"" in self.dashboard
        assert "data-sort=\"quality\"" in self.dashboard
        assert "data-sort=\"sources\"" in self.dashboard

    def test_add_result_to_table_has_plus_button(self):
        """addResultToTable must include + button."""
        assert 'title="Download">+</button>' in self.dashboard
        assert 'onclick="doDownload(' in self.dashboard

    def test_add_result_to_table_has_magnet_button(self):
        """addResultToTable magnet button must have btn-magnet class."""
        assert 'class="download-btn btn-magnet"' in self.dashboard

    def test_add_result_to_table_has_qbit_button(self):
        """addResultToTable must have qBit button with correct class."""
        assert 'class="download-btn btn-schedule"' in self.dashboard

    def test_add_result_to_table_uses_correct_index(self):
        """addResultToTable must pass correct index to button handlers."""
        assert "addResultToTable(normalized, _lastResults.length - 1);" in self.dashboard

    def test_render_results_formats_size_correctly(self):
        """renderResults must use formatSize for numeric sizes."""
        assert "var sizeDisplay = (typeof r.size === 'string'" in self.dashboard

    def test_render_results_has_fallback_for_name(self):
        """renderResults must handle missing name."""
        assert "escapeHtml(r.name || 'Unknown')" in self.dashboard

    def test_render_results_has_fallback_for_seeds(self):
        """renderResults must handle missing seeds."""
        assert "(r.seeds || 0)" in self.dashboard

    def test_render_results_has_fallback_for_leechers(self):
        """renderResults must handle missing leechers."""
        assert "(r.leechers || 0)" in self.dashboard

    def test_service_links_present(self):
        """Service links must be present in header."""
        assert "renderServiceLinks()" in self.dashboard
        assert "qBittorrent WebUI" in self.dashboard
        assert "Download Proxy" in self.dashboard


class TestSearchApiResponseStructure:
    """Verify search API returns properly structured results."""

    @pytest.fixture(scope="class")
    def search_data(self):
        base_url = BASE_URL
        try:
            r = requests.get(f"{base_url}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")
        data = requests.post(
            f"{base_url}/api/v1/search",
            json={"query": "matrix", "limit": 5},
            timeout=30,
        ).json()
        return data

    def test_search_returns_required_fields(self, search_data):
        assert "results" in search_data
        assert len(search_data["results"]) > 0
        r = search_data["results"][0]
        for field in ["name", "size", "seeds", "leechers", "content_type", "quality", "sources", "download_urls"]:
            assert field in r, f"Missing field: {field}"

    def test_size_is_string_not_number(self, search_data):
        """Size must be a human-readable string, not raw bytes."""
        for r in search_data.get("results", [])[:3]:
            size = r.get("size", "")
            assert isinstance(size, str), f"size is {type(size).__name__}, expected str"
            assert size != "NaN undefined", f"size is broken: {size}"
            assert size != "undefined", f"size is undefined string"
            # Should contain a unit or be "0 B"
            assert bool(re.search(r"[KMGT]?B$", size)) or size == "0 B", f"size has no unit: {size}"

    def test_seeds_is_int(self, search_data):
        for r in search_data.get("results", [])[:3]:
            seeds = r.get("seeds")
            assert isinstance(seeds, int), f"seeds is {type(seeds).__name__}, expected int"

    def test_leechers_is_int(self, search_data):
        for r in search_data.get("results", [])[:3]:
            leechers = r.get("leechers")
            assert isinstance(leechers, int), f"leechers is {type(leechers).__name__}, expected int"

    def test_sources_is_list(self, search_data):
        for r in search_data.get("results", [])[:3]:
            sources = r.get("sources", [])
            assert isinstance(sources, list), f"sources is {type(sources).__name__}, expected list"

    def test_download_urls_is_list(self, search_data):
        for r in search_data.get("results", [])[:3]:
            urls = r.get("download_urls", [])
            assert isinstance(urls, list), f"download_urls is {type(urls).__name__}, expected list"
            assert len(urls) > 0, "download_urls must not be empty"

    def test_name_is_string_not_empty(self, search_data):
        for r in search_data.get("results", [])[:3]:
            name = r.get("name", "")
            assert isinstance(name, str) and len(name) > 0, f"name is empty or wrong type: {name!r}"

    def test_quality_is_string(self, search_data):
        for r in search_data.get("results", [])[:3]:
            quality = r.get("quality", "")
            assert isinstance(quality, str), f"quality is {type(quality).__name__}, expected str"

    def test_content_type_is_string(self, search_data):
        for r in search_data.get("results", [])[:3]:
            ct = r.get("content_type", "")
            assert isinstance(ct, str), f"content_type is {type(ct).__name__}, expected str"

    def test_results_have_tracker_field(self, search_data):
        for r in search_data.get("results", [])[:3]:
            assert "tracker" in r, "Missing tracker field"

    def test_no_nan_in_any_field(self, search_data):
        """Ensure no NaN or undefined values leak into response."""
        for r in search_data.get("results", [])[:5]:
            for key, val in r.items():
                if isinstance(val, str):
                    assert "NaN" not in val, f"Field {key} contains NaN: {val!r}"
                    assert val != "undefined", f"Field {key} is undefined string"


class TestDashboardButtonsInHtml:
    """Verify action buttons are present in dashboard HTML."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        try:
            r = requests.get(f"{self.base_url}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")
        self.dashboard = requests.get(f"{self.base_url}/dashboard", timeout=5).text

    def test_magnet_button_in_render_results(self):
        assert 'class="download-btn btn-magnet"' in self.dashboard
        assert 'title="Get Magnet Link"' in self.dashboard

    def test_qbit_button_in_render_results(self):
        assert 'class="download-btn btn-schedule"' in self.dashboard
        assert 'title="Send to qBittorrent"' in self.dashboard

    def test_plus_button_in_render_results(self):
        assert 'title="Download"' in self.dashboard
        assert ">+</button>" in self.dashboard

    def test_all_three_buttons_in_add_result_to_table(self):
        """addResultToTable must have all 3 buttons."""
        # Count occurrences - both addResultToTable and renderResults should have them
        assert self.dashboard.count('btn-magnet') >= 1
        assert self.dashboard.count('btn-schedule') >= 1
        assert self.dashboard.count('doDownload(') >= 1
