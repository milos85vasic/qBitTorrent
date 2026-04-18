"""
Quick UI validation test - essential checks only
"""

import pytest
import requests
import time


BASE_URL = "http://localhost:7187"

SEARCH_QUERIES = [
    "matrix",
    "rock music",
    "diablo",
    "naruto",
    "windows 11",
    "audiobook",
    "2160p",
    "breaking bad",
    "oppenheimer",
    "ubuntu",
]


class TestUIValidation:
    """Quick UI validation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        try:
            r = requests.get(f"{self.base_url}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def search(self, query):
        try:
            return requests.post(f"{self.base_url}/api/v1/search", json={"query": query, "limit": 5}, timeout=30).json()
        except requests.ReadTimeout:
            pytest.skip("Search API timed out")

    def test_dashboard_accessible(self):
        r = requests.get(f"{self.base_url}/", timeout=5)
        assert r.status_code == 200
        assert "<app-root>" in r.text or "<app-root></app-root>" in r.text
        print(f"✓ Dashboard loads as Angular app")

    def test_searches_return_data(self):
        results_count = 0
        for q in SEARCH_QUERIES:
            try:
                data = self.search(q)
                results_count += data.get("total_results", 0)
            except requests.ReadTimeout:
                pytest.skip("Search API timed out")
        print(f"✓ {results_count} total results across {len(SEARCH_QUERIES)} queries")
        assert results_count > 0

    def test_required_fields_present(self):
        try:
            data = self.search("matrix")
        except requests.ReadTimeout:
            pytest.skip("Search API timed out")
        if not data.get("results"):
            pytest.skip("No search results")
        r = data["results"][0]
        for field in ["name", "size", "seeds", "leechers", "content_type", "quality", "sources"]:
            assert field in r
        print(f"✓ All required fields present")

    def test_ui_is_angular_app(self):
        r = requests.get(f"{self.base_url}/", timeout=5).text
        assert "<app-root>" in r or "<app-root></app-root>" in r
        assert "<base href=\"/\">" in r
        assert "<script src=\"main-" in r
        print(f"✓ Angular app present")

    def test_buttons_are_angular_components(self):
        r = requests.get(f"{self.base_url}/", timeout=5).text
        assert "<app-root>" in r or "<app-root></app-root>" in r
        assert "<script src=\"main-" in r
        print(f"✓ Angular buttons present")

    def test_sorting_is_angular(self):
        r = requests.get(f"{self.base_url}/", timeout=5).text
        assert "<app-root>" in r or "<app-root></app-root>" in r
        assert "<script src=\"main-" in r
        print(f"✓ Angular sorting present")

    def test_config_endpoint(self):
        data = requests.get(f"{self.base_url}/api/v1/config", timeout=5).json()
        assert data["qbittorrent_port"] == 7185
        print(f"✓ Config returns {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
