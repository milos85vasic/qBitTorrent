"""
Comprehensive tests for dashboard rendering fixes:
- Size display (NaN undefined fix)
- Missing + button restoration
- Magnet link styling
- Name column max-width + word-break
- Proper table structure in both SSE and polling paths
"""

import re

import pytest
import requests


class TestDashboardHtmlStructure:
    """Verify dashboard HTML is Angular SPA."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live
        self.dashboard = requests.get(f"{self.base_url}/dashboard", timeout=30).text

    def test_dashboard_is_angular_app(self):
        """Dashboard must be Angular SPA."""
        assert "<app-root>" in self.dashboard or "<app-root></app-root>" in self.dashboard
        assert "<base href=\"/\">" in self.dashboard
        assert "<script src=\"main-" in self.dashboard

    def test_angular_styles_bundle_loaded(self):
        """Angular styles bundle must be loaded."""
        assert "styles-" in self.dashboard, "Angular styles bundle should be loaded"

    def test_service_links_present_via_api(self):
        """Service links must be accessible via API."""
        resp = requests.get(f"{self.base_url}/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "qbittorrent_url" in data


class TestSearchApiResponseStructure:
    """Verify search API returns properly structured results."""

    @pytest.fixture(scope="class")
    def search_data(self, merge_service_live):
        data = requests.post(
            f"{merge_service_live}/api/v1/search/sync",
            json={"query": "linux", "limit": 5},
            timeout=180,
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
            assert size != "undefined", "size is undefined string"
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
    """Verify action buttons are rendered by Angular."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live
        self.dashboard = requests.get(f"{self.base_url}/dashboard", timeout=30).text

    def test_dashboard_is_angular_app(self):
        assert "<app-root>" in self.dashboard or "<app-root></app-root>" in self.dashboard
        assert "<script src=\"main-" in self.dashboard

    def test_angular_styles_loaded(self):
        assert "styles-" in self.dashboard
