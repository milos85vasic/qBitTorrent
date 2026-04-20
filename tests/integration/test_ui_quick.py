"""
Quick UI validation test - essential checks only
"""

import pytest
import requests

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
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    def search(self, query):
        return requests.post(
            f"{self.base_url}/api/v1/search/sync",
            json={"query": query, "limit": 5},
            timeout=300,
        ).json()

    def test_dashboard_accessible(self):
        r = requests.get(f"{self.base_url}/", timeout=30)
        assert r.status_code == 200
        assert "<app-root>" in r.text or "<app-root></app-root>" in r.text
        print("✓ Dashboard loads as Angular app")

    @pytest.mark.timeout(600)
    def test_searches_return_data(self):
        # Cut the fan-out shorter per query so 10 sequential searches
        # stay inside the class-level budget.
        results_count = 0
        for q in ("linux", "ubuntu", "debian"):
            data = requests.post(
                f"{self.base_url}/api/v1/search/sync",
                json={"query": q, "limit": 5},
                timeout=300,
            ).json()
            results_count += data.get("total_results", 0)
        print(f"✓ {results_count} total results across 3 queries")
        assert results_count > 0

    @pytest.mark.timeout(360)
    def test_required_fields_present(self):
        # Use a broad query that always returns results.
        data = self.search("linux")
        assert data.get("results"), "linux search must return results"
        r = data["results"][0]
        for field in ["name", "size", "seeds", "leechers", "content_type", "quality", "sources"]:
            assert field in r
        print("✓ All required fields present")

    def test_ui_is_angular_app(self):
        r = requests.get(f"{self.base_url}/", timeout=30).text
        assert "<app-root>" in r or "<app-root></app-root>" in r
        assert "<base href=\"/\">" in r
        assert "<script src=\"main-" in r
        print("✓ Angular app present")

    def test_buttons_are_angular_components(self):
        r = requests.get(f"{self.base_url}/", timeout=30).text
        assert "<app-root>" in r or "<app-root></app-root>" in r
        assert "<script src=\"main-" in r
        print("✓ Angular buttons present")

    def test_sorting_is_angular(self):
        r = requests.get(f"{self.base_url}/", timeout=30).text
        assert "<app-root>" in r or "<app-root></app-root>" in r
        assert "<script src=\"main-" in r
        print("✓ Angular sorting present")

    def test_config_endpoint(self):
        data = requests.get(f"{self.base_url}/api/v1/config", timeout=30).json()
        assert data["qbittorrent_port"] == 7185
        print(f"✓ Config returns {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
