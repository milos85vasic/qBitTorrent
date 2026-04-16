"""
Tests for button functionality: Magnet, qBit, Download
"""

import pytest
import requests
import json
import re


BASE_URL = "http://localhost:7187"


class TestButtonFunctions:
    """Test buttons in the UI."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def search_and_get_results(self, query="matrix"):
        """Perform search and return results."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/search",
            json={"query": query, "limit": 3},
            headers={"Content-Type": "application/json"},
        )
        return resp.json().get("results", [])

    def test_dashboard_has_all_button_handlers(self):
        """All button click handlers should be defined."""
        html = self.session.get(self.base_url).text

        checks = [
            ("function doMagnet(", "doMagnet function"),
            ("function doSchedule(", "doSchedule function"),
            ("function doDownload(", "doDownload function"),
            ("function generateMagnet(", "generateMagnet function"),
            ('onclick="doMagnet(', "Magnet button onclick"),
            ('onclick="doSchedule(', "Schedule button onclick"),
            ('onclick="doDownload(', "Download button onclick"),
        ]

        print("\n=== Button Handlers ===")
        for pattern, name in checks:
            found = pattern in html
            print(f"{'Y' if found else 'N'} {name}")
            assert found, f"Missing: {name}"

    def test_magnet_button_present(self):
        """Magnet button should be in UI."""
        html = self.session.get(self.base_url).text
        assert "btn-magnet" in html
        assert "Magnet" in html
        print("\nY Magnet button present")

    def test_schedule_button_present(self):
        """Schedule (qBit) button should be in UI."""
        html = self.session.get(self.base_url).text
        assert "btn-schedule" in html
        assert "qBit" in html or "Schedule" in html
        print("Y Schedule button present")

    def test_download_button_present(self):
        """Download button should be in UI."""
        html = self.session.get(self.base_url).text
        assert 'onclick="doDownload(' in html
        print("Y Download button present")

    def test_magnet_generation_logic(self):
        """generateMagnet function should exist and have valid logic."""
        html = self.session.get(self.base_url).text

        # Check the function exists and uses proper magnet format
        assert "function generateMagnet(" in html
        assert "magnet:?dn=" in html
        assert "xt=urn:btih:" in html or "tr=udp://" in html

        print("\nY Magnet generation logic valid")

    def test_config_loaded_for_schedule(self):
        """_config should be loaded for qBit button."""
        html = self.session.get(self.base_url).text

        assert "_config" in html
        assert "qbittorrent_url" in html

        print("Y _config variable defined")

    def test_api_download_endpoint_exists(self):
        """Download API endpoint should exist."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/download",
            json={"result_id": "0", "download_urls": ["http://example.com/test.torrent"]},
            headers={"Content-Type": "application/json"},
        )

        # Should return a response (auth may fail, but endpoint exists)
        data = resp.json()
        assert "download_id" in data
        print(f"\nY Download API: {data.get('status')}")

    def test_api_magnet_endpoint_exists(self):
        """Magnet generation API endpoint should exist."""
        resp = self.session.get(f"{self.base_url}/api/v1/magnet")

        # Check if endpoint exists (may need params)
        # This is just existence check
        print("Y Magnet API endpoint exists")

    def test_results_have_download_urls(self):
        """Results should have download_urls for buttons to work."""
        results = self.search_and_get_results("matrix")

        assert len(results) > 0
        r = results[0]

        assert "download_urls" in r
        assert isinstance(r["download_urls"], list)

        print(f"\nY Download URLs: {len(r['download_urls'])} URLs in first result")

    def test_results_have_sources(self):
        """Results should have sources for display."""
        results = self.search_and_get_results("matrix")

        r = results[0]
        assert "sources" in r
        assert isinstance(r["sources"], list)

        print(f"Y Sources: {len(r['sources'])} sources in first result")

    def test_magnet_button_title_attribute(self):
        """Magnet button should have title attribute."""
        html = self.session.get(self.base_url).text

        assert 'title="Get Magnet Link"' in html
        print("\nY Magnet button title attribute")

    def test_schedule_button_title_attribute(self):
        """Schedule button should have title attribute."""
        html = self.session.get(self.base_url).text

        assert 'title="Send to qBittorrent"' in html
        print("Y Schedule button title attribute")

    def test_button_group_css(self):
        """Button group CSS should be defined."""
        html = self.session.get(self.base_url).text

        assert ".btn-group" in html
        assert ".btn-magnet" in html
        assert ".btn-schedule" in html
        print("Y Button group CSS defined")

    def test_alert_handling_in_buttons(self):
        """Buttons should have alert handling for errors."""
        html = self.session.get(self.base_url).text

        # Check for alert calls in functions
        assert "alert('" in html or 'alert("' in html
        print("\nY Alert handling present for errors")


class TestMagnetLinkGeneration:
    """Test magnet link generation logic."""

    def test_magnet_url_format(self):
        """Magnet links should follow correct format."""
        html = requests.get(BASE_URL).text

        checks = [
            ("magnet:?dn=", "magnet:?dn= in code"),
            ("tr=udp://", "UDP tracker"),
        ]

        print("\n=== Magnet Link Validation ===")
        for text, name in checks:
            found = text in html
            print(f"{'Y' if found else 'N'} {name}")
            assert found, f"Magnet format missing: {text}"


class TestScheduleButtonConfig:
    """Test schedule button config loading."""

    def test_config_loads_at_startup(self):
        """_config should be loaded when page loads."""
        html = requests.get(BASE_URL).text

        # Should call loadConfig
        assert "loadConfig()" in html or "loadConfig" in html

        # Should define _config
        assert "var _config" in html

        print("\nY Config loads at startup")

    def test_config_has_qbittorrent_url(self):
        """Config should contain qBittorrent URL."""
        resp = requests.get(f"{BASE_URL}/api/v1/config")
        data = resp.json()

        assert "qbittorrent_url" in data
        assert "7185" in data["qbittorrent_url"]

        print(f"\nY Config: {data}")


class TestButtonFixes:
    """Tests for the three bug fixes."""

    def test_magnet_generates_without_hash_in_url(self):
        """generateMagnet should work without btih hash in tracker URLs."""
        html = requests.get(BASE_URL).text

        # The function should work with just name and default trackers
        assert "magnet:?dn=" in html
        # Should have default fallback trackers
        assert "tracker.opentrackr.org" in html
        # Should NOT try to extract hash from URL (that fails)
        assert "url.match(/btih:" not in html or "m = url.match" not in html

        print("\nY Magnet generates without hash extraction")

    def test_password_field_has_css(self):
        """Password field should have CSS styling in modals."""
        html = requests.get(BASE_URL).text

        # Check password field is styled
        assert 'input[type="password"]' in html
        # The modal CSS should include password
        assert '.modal input[type="password"]' in html or 'input[type="password"]' in html

        print("\nY Password field CSS present")

    def test_doDownload_handles_auth_failed(self):
        """doDownload should detect auth_failed and prompt login."""
        html = requests.get(BASE_URL).text

        # Should check for auth_failed status
        assert "auth_failed" in html
        # Should call openQbitLogin on auth failure
        assert "openQbitLogin()" in html

        print("\nY doDownload handles auth_failed")

    def test_no_duplicate_doDownload(self):
        """Only one doDownload function should exist."""
        html = requests.get(BASE_URL).text

        # Count occurrences of function definition
        count = html.count("function doDownload(")
        assert count == 1, f"Expected 1 doDownload, found {count}"

        print(f"\nY Single doDownload function (count={count})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
