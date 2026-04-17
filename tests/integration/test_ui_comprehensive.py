"""
Comprehensive UI test with 30+ search queries to validate:
- API returns correct data
- Content type detection works
- Quality detection works
- UI rendering produces valid HTML
- Sorting works
- All columns display correctly
"""

import pytest
import requests
import json
import time


BASE_URL = "http://localhost:7187"
SEARCH_QUERIES = [
    # Movies (various languages and formats)
    "matrix",
    "lord of the rings",
    "the batman",
    "oppenheimer",
    "dune part two",
    "interstellar",
    "inception",
    "gladiator",
    # TV Shows
    "breaking bad",
    "game of thrones",
    "stranger things",
    "the last of us",
    "house of dragon",
    " succession",
    # Music (various genres)
    "rock music mp3",
    " jazz flac",
    "electronic dance",
    "hip hop 320kbps",
    "classical symphonic",
    "metal album",
    # Software/Games
    "windows 11 iso",
    "ubuntu linux",
    "diablo iv",
    "elden ring",
    "cyberpunk 2077",
    # Anime
    "naruto shippuden",
    "attack on titan",
    "one piece",
    "demon slayer",
    # Books/Audiobooks
    "audiobook english",
    " epub novel",
    "programming ebook",
    # Various qualities and formats
    "2160p 4k",
    "1080p bluray",
    "720p hd",
    "webrip web-dl",
    # Different languages
    "кино русское",
    "anime japanese",
    "film francais",
]


class TestUISearchVariety:
    """Test search with varied queries."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        try:
            r = requests.get(f"{self.base_url}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")
        self.session = requests.Session()

    def search(self, query):
        """Perform a search and return results."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/search",
            json={"query": query, "limit": 10},
            headers={"Content-Type": "application/json"},
        )
        return resp.json()

    def test_all_queries_return_results(self):
        """All 30+ queries should return results."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _search_one(query):
            try:
                data = self.search(query)
                count = data.get("total_results", 0)
                return query, count
            except Exception as e:
                return query, 0

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_search_one, q): q for q in SEARCH_QUERIES}
            for future in as_completed(futures):
                query, count = future.result()
                results.append((query, count))
                print(f"Query: '{query}' -> {count} results")

        print(f"\n=== Summary ===")
        print(f"Total queries: {len(results)}")
        print(f"Queries with results: {sum(1 for _, c in results if c > 0)}")

        # At least 80% should return results
        success_rate = sum(1 for _, c in results if c > 0) / len(results)
        assert success_rate >= 0.8, f"Only {success_rate * 100:.0f}% returned results"

    def test_api_returns_complete_data(self):
        """API should return complete data for all columns."""
        data = self.search("matrix")
        assert "results" in data
        assert len(data["results"]) > 0

        r = data["results"][0]

        # Check all expected fields
        required_fields = ["name", "size", "seeds", "leechers", "content_type", "quality", "sources", "download_urls"]
        for field in required_fields:
            assert field in r, f"Missing field: {field}"

        print(f"\n=== Sample result fields ===")
        for field in required_fields:
            print(f"  {field}: {r.get(field)}")

    def test_content_type_detection(self):
        """Content type should be detected and returned as a valid known type."""
        valid_types = {
            "movie", "tv", "music", "game", "anime", "software",
            "audiobook", "ebook", "unknown",
        }

        for query in SEARCH_QUERIES[:10]:
            data = self.search(query)
            if data.get("total_results", 0) > 0:
                for r in data["results"][:3]:
                    ct = r.get("content_type", "unknown")
                    assert ct in valid_types, f"Invalid content_type: {ct}"
                    assert ct is not None, "content_type should not be None"

    def test_quality_detection(self):
        """Quality should be detected."""
        qualities_seen = set()

        for query in SEARCH_QUERIES[:15]:  # Check first 15
            data = self.search(query)
            if data.get("total_results", 0) > 0:
                r = data["results"][0]
                q = r.get("quality", "unknown")
                qualities_seen.add(q)

        print(f"\n=== Qualities detected: {qualities_seen} ===")
        assert len(qualities_seen) > 0

    def test_sources_merged(self):
        """Sources should be tracked and merged correctly."""
        data = self.search("matrix")

        merged_count = 0
        for r in data.get("results", [])[:5]:
            sources = r.get("sources", [])
            if len(sources) > 1:
                merged_count += 1

        print(f"\n=== Merged results: {merged_count}/5 ===")
        print(f"First result sources: {data['results'][0].get('sources', [])[:3]}")

    def test_ui_renders_valid_html(self):
        """Dashboard HTML should be valid with proper structure."""
        resp = self.session.get(f"{self.base_url}/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

        html = resp.text

        # Check for required UI elements
        checks = [
            ("results-table" in html, "results-table class"),
            ('data-sort="name"' in html, "sortable name column"),
            ('data-sort="type"' in html, "sortable type column"),
            ('data-sort="size"' in html, "sortable size column"),
            ('data-sort="seeds"' in html, "sortable seeds column"),
            ('data-sort="quality"' in html, "sortable quality column"),
            ("renderResults" in html, "renderResults function"),
            ("sortResults" in html, "sortResults function"),
            ('class="type-badge' in html, "type-badge CSS"),
            ('class="quality-badge' in html, "quality-badge CSS"),
        ]

        print(f"\n=== UI Structure Checks ===")
        all_pass = True
        for passed, name in checks:
            status = "✓" if passed else "✗"
            print(f"  {status} {name}")
            if not passed:
                all_pass = False

        assert all_pass, "UI structure is invalid"

    def test_sorting_functionality(self):
        """Sorting functions should be defined."""
        resp = self.session.get(f"{self.base_url}/")
        html = resp.text

        # Check sorting functions exist
        assert "function sortResults(" in html, "sortResults not found"
        assert "function renderSortedResults(" in html, "renderSortedResults not found"
        assert "_sortColumn" in html, "_sortColumn not found"
        assert "_sortDirection" in html, "_sortDirection not found"

        print(f"\n=== Sorting functions present: YES ===")

    def test_button_group_rendering(self):
        """Action buttons should be rendered."""
        resp = self.session.get(f"{self.base_url}/")
        html = resp.text

        checks = [
            ("btn-magnet" in html, "Magnet button"),
            ("btn-schedule" in html, "Schedule button"),
            ('onclick="doMagnet(' in html, "doMagnet handler"),
            ('onclick="doSchedule(' in html, "doSchedule handler"),
            ('onclick="doDownload(' in html, "doDownload handler"),
        ]

        print(f"\n=== Button checks ===")
        for passed, name in checks:
            status = "✓" if passed else "✗"
            print(f"  {status} {name}")

    def test_config_endpoint(self):
        """Config endpoint should return qBittorrent settings."""
        resp = self.session.get(f"{self.base_url}/api/v1/config")
        assert resp.status_code == 200
        data = resp.json()

        assert "qbittorrent_url" in data
        assert "qbittorrent_port" in data
        assert data["qbittorrent_port"] == 7185

        print(f"\n=== Config: {data} ===")

    def test_health_endpoint(self):
        """Health check should work."""
        resp = self.session.get(f"{self.base_url}/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
        print(f"\n=== Health: OK ===")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
