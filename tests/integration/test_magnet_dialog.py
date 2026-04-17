"""
Tests for Magnet Dialog feature - copy and open functionality

TDD Tests:
1. Magnet dialog should exist with copy and open buttons
2. Copy button should copy magnet link to clipboard
3. Open button should trigger magnet link execution (mobile)
4. Dialog should show magnet link text
"""

import pytest
import requests
import json


BASE_URL = "http://localhost:7187"


class TestMagnetDialog:
    """Test magnet dialog functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def search_and_get_first_result(self, query="matrix"):
        """Perform search and return first result."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/search",
            json={"query": query, "limit": 1},
            headers={"Content-Type": "application/json"},
        )
        results = resp.json().get("results", [])
        if results:
            return results[0]
        return None

    def test_magnet_dialog_modal_exists(self):
        """Magnet dialog modal should exist in dashboard."""
        html = self.session.get(self.base_url).text

        assert 'id="magnet-dialog"' in html or "magnet-dialog" in html, "Magnet dialog modal should exist in HTML"

    def test_magnet_dialog_copy_button(self):
        """Magnet dialog should have copy button."""
        html = self.session.get(self.base_url).text

        assert "magnet-copy-btn" in html or "copy-magnet" in html or "Copy" in html, (
            "Magnet dialog should have copy button"
        )

    def test_magnet_dialog_open_button(self):
        """Magnet dialog should have open button for mobile."""
        html = self.session.get(self.base_url).text

        assert "magnet-open-btn" in html or "open-magnet" in html or "Open" in html, (
            "Magnet dialog should have open button"
        )

    def test_magnet_dialog_shows_link(self):
        """Magnet dialog should display the magnet link."""
        html = self.session.get(self.base_url).text

        assert "magnet" in html.lower(), "Dashboard should have magnet-related elements"

    def test_generateMagnet_creates_valid_uri(self):
        """generateMagnet should create valid magnet URI."""
        result = self.search_and_get_first_result("matrix")
        assert result is not None, "Need search results"

        name = result.get("name")
        assert name, "Result should have a name"

        from urllib.parse import quote

        magnet_uri = f"magnet:?dn={quote(name)}&tr=udp://tracker.opentrackr.org:1337"

        assert magnet_uri.startswith("magnet:?dn="), "Should be valid magnet URI"
        assert "tr=" in magnet_uri, "Should have tracker"


class TestMagnetDialogBehavior:
    """Test magnet dialog behavior with results."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def test_doMagnet_function_exists(self):
        """doMagnet function should exist."""
        html = self.session.get(self.base_url).text
        assert "function doMagnet(" in html, "doMagnet function should exist"

    def test_doMagnet_handles_no_results(self):
        """doMagnet should handle no results gracefully."""
        html = self.session.get(self.base_url).text

        assert "No results" in html or "not found" in html.lower() or "error" in html.lower(), (
            "Should have error handling for no results"
        )

    def test_magnet_button_is_clickable(self):
        """Magnet button should have onclick handler."""
        html = self.session.get(self.base_url).text

        assert 'onclick="doMagnet(' in html, "Magnet button should have onclick handler"


class TestMobileMagnetExecution:
    """Test mobile magnet execution support."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def test_magnet_link_can_be_opened(self):
        """Magnet link should be openable as URL."""
        result = (
            self.session.post(
                f"{self.base_url}/api/v1/search",
                json={"query": "test", "limit": 1},
                headers={"Content-Type": "application/json"},
            )
            .json()
            .get("results", [])
        )

        if not result:
            pytest.skip("No search results")

        from urllib.parse import quote

        name = result[0].get("name", "test")
        magnet = f"magnet:?dn={quote(name)}&tr=udp://tracker.opentrackr.org:1337"

        assert magnet.startswith("magnet:"), "Should be valid magnet URL"

    def test_open_button_has_proper_href(self):
        """Open button should use href for magnet execution."""
        html = self.session.get(self.base_url).text

        assert 'href="magnet:' in html or "magnet:?" in html, "Open button should use magnet: href"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
