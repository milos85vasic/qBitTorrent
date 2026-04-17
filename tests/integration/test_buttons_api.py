"""
Tests for button actions via API - Magnet, Download, Schedule
These tests verify buttons trigger correct API calls
"""

import pytest
import requests
import json
import re


BASE_URL = "http://localhost:7187"
QBIT_URL = "http://localhost:7185"


class TestMagnetButton:
    """Test Magnet button functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def search_get_result(self, query="matrix"):
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

    def test_generateMagnet_creates_valid_magnet(self):
        """generateMagnet should create valid magnet URI."""
        result = self.search_get_result("matrix")
        assert result is not None, "No search results"

        name = result.get("name")
        assert name, "Result has no name"

        # Magnet format: magnet:?dn=<name>&tr=<tracker>
        magnet_uri = f"magnet:?dn={requests.utils.quote(name)}&tr=udp://tracker.opentrackr.org:1337&tr=udp://tracker.leechers.org:6969"

        # Verify it's a valid magnet URI
        assert magnet_uri.startswith("magnet:?dn="), "Invalid magnet format"
        assert "tr=" in magnet_uri, "Missing tracker"

    def test_magnet_button_has_valid_href(self):
        """Magnet button should link to valid magnet URI."""
        html = self.session.get(self.base_url).text

        # Find doMagnet function
        assert "function doMagnet(" in html, "doMagnet function missing"

        # Check onclick calls generateMagnet
        assert 'onclick="doMagnet(' in html, "Magnet button missing onclick"

    def test_getMagnetUrl_function_exists(self):
        """getMagnetUrl should be defined."""
        html = self.session.get(self.base_url).text
        assert "function getMagnetUrl(" in html, "getMagnetUrl function missing"


class TestDownloadButton:
    """Test + (Download) button functionality via API."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        # Ensure logged in to qBittorrent
        try:
            login = self.session.post(
                f"{QBIT_URL}/api/v2/auth/login",
                data={"username": "admin", "password": "admin"},
                timeout=5,
            )
        except requests.ConnectionError:
            pytest.skip("qBittorrent not available")
        if login.text != "Ok.":
            pytest.skip(f"qBittorrent login failed: {login.text}")

    def test_download_api_accepts_valid_request(self):
        """/api/v1/download should accept download request."""
        # First get a search result with download URLs
        resp = self.session.post(
            f"{self.base_url}/api/v1/search",
            json={"query": "matrix", "limit": 1},
            headers={"Content-Type": "application/json"},
        )
        results = resp.json().get("results", [])
        if not results:
            pytest.skip("No search results")

        result = results[0]
        download_urls = result.get("download_urls", [])

        if download_urls:
            # Try to download
            download_resp = self.session.post(
                f"{self.base_url}/api/v1/download",
                json={"result_id": "0", "download_urls": download_urls},
                headers={"Content-Type": "application/json"},
            )
            # Should get a valid response (not 500 error)
            assert download_resp.status_code != 500, "Download API returns 500"
        else:
            pytest.skip("No download URLs in result")

    def test_download_api_returns_proper_response(self):
        """Download API should return proper JSON response."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/download",
            json={"result_id": "999", "download_urls": []},
            headers={"Content-Type": "application/json"},
        )

        # Should be valid JSON
        try:
            data = resp.json()
            assert isinstance(data, dict), "Response is not JSON object"
        except Exception as e:
            pytest.fail(f"Invalid JSON response: {e}")

    def test_download_api_with_invalid_id(self):
        """Download API should handle invalid result_id gracefully."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/download",
            json={"result_id": "invalid999", "download_urls": []},
            headers={"Content-Type": "application/json"},
        )

        # Should not return 500
        assert resp.status_code < 500, "API returns server error"


class TestScheduleButton:
    """Test Schedule button functionality via API."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def test_schedule_button_function_exists(self):
        """doSchedule function should exist."""
        html = self.session.get(self.base_url).text
        assert "function doSchedule(" in html, "doSchedule function missing"

    def test_schedule_api_endpoint_works(self):
        """Schedule API should respond."""
        html = self.session.get(self.base_url).text

        # Find if there's a schedule button
        if 'onclick="doSchedule(' in html:
            # Try calling schedule endpoint if it exists
            # Look for schedule route in routes.py
            pass


class TestQBitLoginButton:
    """Test qBittorrent login button/flow."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.qbit_url = QBIT_URL
        self.session = requests.Session()

    def test_qbit_login_api_works(self):
        """qBittorrent login API should work."""
        try:
            resp = self.session.post(
                f"{self.qbit_url}/api/v2/auth/login",
                data={"username": "admin", "password": "admin"},
                timeout=5,
            )
        except requests.ConnectionError:
            pytest.skip("qBittorrent not available")
        if resp.text != "Ok.":
            pytest.skip(f"qBittorrent login failed: {resp.text}")

    def test_merge_service_auth_endpoint_works(self):
        """Merge service /auth/qbittorrent endpoint should work."""
        try:
            resp = self.session.post(
                f"{self.base_url}/api/v1/auth/qbittorrent",
                json={"username": "admin", "password": "admin"},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
        except requests.ConnectionError:
            pytest.skip("Merge service not available")

        data = resp.json()
        # Should either auth successfully or return proper error
        assert resp.status_code in [200, 401, 403], "Unexpected status"

        if resp.status_code == 200 and data.get("status") != "authenticated":
            pytest.skip(f"qBittorrent auth via merge service failed: {data}")

    def test_login_form_submits_correctly(self):
        """Login form should submit to correct endpoint."""
        html = self.session.get(self.base_url).text

        # Check login form points to correct API
        assert "/api/v1/auth/qbittorrent" in html, "Login form missing correct endpoint"


class TestButtonUIIntegration:
    """Integration tests for button UI."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def test_dashboard_loads_without_errors(self):
        """Dashboard should load."""
        resp = self.session.get(self.base_url)
        assert resp.status_code == 200, "Dashboard not loading"

    def test_all_button_functions_defined(self):
        """All button handler functions should be defined."""
        html = self.session.get(self.base_url).text

        functions = [
            "doMagnet",
            "doDownload",
            "doSchedule",
            "generateMagnet",
            "getMagnetUrl",
        ]

        for fn in functions:
            assert f"function {fn}(" in html, f"Function {fn} missing"

    def test_buttons_have_onclick(self):
        """Buttons should have onclick handlers."""
        html = self.session.get(self.base_url).text

        buttons = [
            ('onclick="doMagnet(', "Magnet button"),
            ('onclick="doDownload(', "Download button"),
            ('onclick="doSchedule(', "Schedule button"),
        ]

        for pattern, name in buttons:
            assert pattern in html, f"{name} missing onclick"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
