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
        return requests.post(f"{self.base_url}/api/v1/search", json={"query": query, "limit": 5}, timeout=10).json()

    def test_dashboard_accessible(self):
        r = requests.get(f"{self.base_url}/", timeout=5)
        assert r.status_code == 200
        assert "results-table" in r.text
        print(f"✓ Dashboard loads")

    def test_searches_return_data(self):
        results_count = 0
        for q in SEARCH_QUERIES:
            data = self.search(q)
            results_count += data.get("total_results", 0)
        print(f"✓ {results_count} total results across {len(SEARCH_QUERIES)} queries")
        assert results_count > 0

    def test_required_fields_present(self):
        data = self.search("matrix")
        r = data["results"][0]
        for field in ["name", "size", "seeds", "leechers", "content_type", "quality", "sources"]:
            assert field in r
        print(f"✓ All required fields present")

    def test_ui_columns_sorted(self):
        r = requests.get(f"{self.base_url}/", timeout=5).text
        cols = ["name", "type", "size", "seeds", "leechers", "quality", "sources"]
        for c in cols:
            assert f'data-sort="{c}"' in r
        print(f"✓ All 7 sortable columns present")

    def test_buttons_present(self):
        r = requests.get(f"{self.base_url}/", timeout=5).text
        assert "btn-magnet" in r
        assert "btn-schedule" in r
        assert 'onclick="doMagnet(' in r
        print(f"✓ All 3 buttons present")

    def test_sorting_functions(self):
        r = requests.get(f"{self.base_url}/", timeout=5).text
        assert "function sortResults(" in r
        assert "function renderSortedResults(" in r
        print(f"✓ Sorting functions defined")

    def test_config_endpoint(self):
        data = requests.get(f"{self.base_url}/api/v1/config", timeout=5).json()
        assert data["qbittorrent_port"] == 7185
        print(f"✓ Config returns {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
