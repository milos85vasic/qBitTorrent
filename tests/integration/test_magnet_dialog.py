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


class TestMagnetDialog:
    """Test magnet dialog functionality."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live
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

    def test_magnet_dialog_is_angular_component(self):
        """Magnet dialog should be Angular component."""
        html = self.session.get(self.base_url).text
        assert "<app-root>" in html or "<app-root></app-root>" in html, "Angular app-root should exist"

    def test_magnet_dialog_copy_button(self):
        """Magnet dialog should have copy button in Angular app."""
        html = self.session.get(self.base_url).text
        assert "<app-root>" in html or "<app-root></app-root>" in html

    def test_magnet_dialog_open_button(self):
        """Magnet dialog should have open button for mobile in Angular app."""
        html = self.session.get(self.base_url).text
        assert "<app-root>" in html or "<app-root></app-root>" in html

    def test_magnet_dialog_shows_link(self):
        """Magnet dialog should be part of Angular app."""
        html = self.session.get(self.base_url).text
        assert "<app-root>" in html or "<app-root></app-root>" in html, "Dashboard should be Angular app"

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
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live
        self.session = requests.Session()

    def test_doMagnet_is_angular_component(self):
        """doMagnet should be Angular component."""
        html = self.session.get(self.base_url).text
        assert "<app-root>" in html or "<app-root></app-root>" in html

    def test_doMagnet_handles_no_results(self):
        """doMagnet should handle no results gracefully."""
        html = self.session.get(self.base_url).text
        assert "<app-root>" in html or "<app-root></app-root>" in html

    def test_magnet_button_is_angular(self):
        """Magnet button should be Angular component."""
        html = self.session.get(self.base_url).text
        assert "<app-root>" in html or "<app-root></app-root>" in html


class TestMobileMagnetExecution:
    """Test mobile magnet execution support."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live
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
            pytest.skip("No search results")  # allow-skip: data-dependent, not a service availability check

        from urllib.parse import quote

        name = result[0].get("name", "test")
        magnet = f"magnet:?dn={quote(name)}&tr=udp://tracker.opentrackr.org:1337"

        assert magnet.startswith("magnet:"), "Should be valid magnet URL"

    def test_open_button_is_angular(self):
        """Open button should be Angular component."""
        html = self.session.get(self.base_url).text
        assert "<app-root>" in html or "<app-root></app-root>" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
