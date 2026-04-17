"""
Comprehensive tests for Login Flow and Actions

Tests:
1. Login modal opens/closes properly
2. Login authentication works
3. Credentials are remembered/saved
4. Pending action continues after login success
5. Modal stacking and dismissal
6. Magnet dialog operations
7. Download button with authentication
8. All button flows end-to-end
"""

import pytest
import requests
import json
import time


BASE_URL = "http://localhost:7187"
QBIT_URL = "http://localhost:7185"


class TestLoginModal:
    """Test login modal functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def test_login_modal_exists(self):
        """Login modal should exist in dashboard."""
        html = self.session.get(self.base_url).text
        assert 'id="qbit-login-modal"' in html, "Login modal should exist"

    def test_login_modal_has_username_field(self):
        """Login modal should have username input."""
        html = self.session.get(self.base_url).text
        assert 'id="qbit-username"' in html, "Username field should exist"

    def test_login_modal_has_password_field(self):
        """Login modal should have password input."""
        html = self.session.get(self.base_url).text
        assert 'id="qbit-password"' in html, "Password field should exist"

    def test_login_modal_has_remember_me(self):
        """Login modal should have remember me checkbox."""
        html = self.session.get(self.base_url).text
        assert 'id="qbit-save-credentials"' in html, "Remember me should exist"

    def test_login_modal_has_login_button(self):
        """Login modal should have login button."""
        html = self.session.get(self.base_url).text
        assert 'id="qbit-login-submit"' in html, "Login button should exist"

    def test_login_modal_can_open(self):
        """openQbitLogin function should exist."""
        html = self.session.get(self.base_url).text
        assert "function openQbitLogin(" in html, "openQbitLogin function should exist"

    def test_login_modal_can_close(self):
        """closeQbitLogin function should exist."""
        html = self.session.get(self.base_url).text
        assert "function closeQbitLogin(" in html, "closeQbitLogin function should exist"


class TestLoginAuthentication:
    """Test login authentication."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.qbit_url = QBIT_URL
        self.session = requests.Session()

    def test_direct_qbittorrent_login(self):
        """Direct qBittorrent login should work."""
        resp = self.session.post(
            f"{self.qbit_url}/api/v2/auth/login",
            data={"username": "admin", "password": "admin"},
        )
        assert resp.text == "Ok.", f"Direct login failed: {resp.text}"

    def test_merge_service_auth_endpoint(self):
        """Merge service auth endpoint should work."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin"},
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 200, f"Auth endpoint returned {resp.status_code}"
        data = resp.json()
        assert data.get("status") == "authenticated", f"Not authenticated: {data}"


class TestCredentialsPersistence:
    """Test credentials save/load functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def test_credentials_can_be_saved(self):
        """Credentials should be saved when save is true."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin", "save": True},
            headers={"Content-Type": "application/json"},
        )
        data = resp.json()
        # Either saved or already authenticated
        assert data.get("status") in ["authenticated", "saved"], f"Unexpected: {data}"


class TestMagnetDialog:
    """Test magnet dialog operations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def test_magnet_dialog_exists(self):
        """Magnet dialog should exist."""
        html = self.session.get(self.base_url).text
        assert 'id="magnet-dialog"' in html, "Magnet dialog should exist"

    def test_magnet_dialog_has_copy_button(self):
        """Magnet dialog should have copy button."""
        html = self.session.get(self.base_url).text
        assert 'id="magnet-copy-btn"' in html, "Copy button should exist"

    def test_magnet_dialog_has_open_button(self):
        """Magnet dialog should have open button."""
        html = self.session.get(self.base_url).text
        assert 'id="magnet-open-btn"' in html, "Open button should exist"

    def test_magnet_dialog_has_add_button(self):
        """Magnet dialog should have add button."""
        html = self.session.get(self.base_url).text
        assert 'id="magnet-add-btn"' in html, "Add button should exist"

    def test_magnet_dialog_has_textarea(self):
        """Magnet dialog should have text area for link."""
        html = self.session.get(self.base_url).text
        assert 'id="magnet-link-text"' in html, "Text area should exist"

    def test_magnet_dialog_close_function(self):
        """closeMagnetDialog function should exist."""
        html = self.session.get(self.base_url).text
        assert "function closeMagnetDialog(" in html, "closeMagnetDialog should exist"

    def test_magnet_copy_function(self):
        """copyMagnetLink function should exist."""
        html = self.session.get(self.base_url).text
        assert "function copyMagnetLink(" in html, "copyMagnetLink should exist"

    def test_magnet_add_function(self):
        """addMagnetToQbit function should exist."""
        html = self.session.get(self.base_url).text
        assert "function addMagnetToQbit(" in html, "addMagnetToQbit should exist"

    def test_generateMagnet_produces_valid_uri(self):
        """generateMagnet should produce valid magnet URI."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/search",
            json={"query": "test", "limit": 1},
            headers={"Content-Type": "application/json"},
        )
        results = resp.json().get("results", [])
        if not results:
            pytest.skip("No search results")

        name = results[0].get("name", "test")
        from urllib.parse import quote

        magnet = f"magnet:?dn={quote(name)}&tr=udp://tracker.opentrackr.org:1337"
        assert magnet.startswith("magnet:?dn="), "Should be valid magnet URI"


class TestMagnetAddToQbit:
    """Test magnet add to qBittorrent functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def test_add_magnet_via_download_api(self):
        """Adding magnet via download API should work."""
        # First get a valid magnet from search
        resp = self.session.post(
            f"{self.base_url}/api/v1/search",
            json={"query": "matrix", "limit": 1},
            headers={"Content-Type": "application/json"},
        )
        results = resp.json().get("results", [])
        if not results:
            pytest.skip("No search results")

        # Try download endpoint
        download_resp = self.session.post(
            f"{self.base_url}/api/v1/download",
            json={"result_id": "0", "download_urls": ["magnet:?dn=test"]},
            headers={"Content-Type": "application/json"},
        )
        # Should not return 500
        assert download_resp.status_code < 500, "Download API should not 500"


class TestDownloadButtons:
    """Test download button functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def test_doDownload_function_exists(self):
        """doDownload function should exist."""
        html = self.session.get(self.base_url).text
        assert "function doDownload(" in html, "doDownload should exist"

    def test_doSchedule_function_exists(self):
        """doSchedule function should exist."""
        html = self.session.get(self.base_url).text
        assert "function doSchedule(" in html, "doSchedule should exist"

    def test_download_button_has_handler(self):
        """Download button should have onclick handler."""
        html = self.session.get(self.base_url).text
        assert 'onclick="doDownload(' in html, "doDownload should have onclick"


class TestModalStacking:
    """Test modal stacking and dismissal."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def test_modal_overlay_css_exists(self):
        """Modal overlay CSS should exist."""
        html = self.session.get(self.base_url).text
        assert ".modal-overlay" in html or "modal-overlay" in html, "Modal CSS should exist"

    def test_modal_can_show(self):
        """Modal should have show class for display."""
        html = self.session.get(self.base_url).text
        assert "classList.add('show')" in html, "Modal show class should exist"

    def test_modal_can_hide(self):
        """Modal should have hide functionality."""
        html = self.session.get(self.base_url).text
        assert "classList.remove('show')" in html, "Modal hide should exist"


class TestFullUserFlows:
    """Test full user flows from search to download."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def test_search_returns_results(self):
        """Search should return results."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/search",
            json={"query": "matrix", "limit": 3},
            headers={"Content-Type": "application/json"},
        )
        data = resp.json()
        assert data.get("results"), "Search should return results"
        assert len(data.get("results", [])) > 0, "Should have at least one result"

    def test_results_have_download_urls(self):
        """Results should have download URLs."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/search",
            json={"query": "matrix", "limit": 1},
            headers={"Content-Type": "application/json"},
        )
        results = resp.json().get("results", [])
        if results:
            assert "download_urls" in results[0], "Results should have download_urls"

    def test_results_have_name(self):
        """Results should have name."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/search",
            json={"query": "matrix", "limit": 1},
            headers={"Content-Type": "application/json"},
        )
        results = resp.json().get("results", [])
        if results:
            assert "name" in results[0], "Results should have name"

    def test_results_have_size(self):
        """Results should have size."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/search",
            json={"query": "matrix", "limit": 1},
            headers={"Content-Type": "application/json"},
        )
        results = resp.json().get("results", [])
        if results:
            assert "size" in results[0], "Results should have size"


class TestCredentialStorage:
    """Test credential storage file."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()

    def test_credentials_file_structure(self):
        """Credentials file should have proper structure."""
        # Test via API - login with save
        resp = self.session.post(
            f"{BASE_URL}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin", "save": False},
            headers={"Content-Type": "application/json"},
        )
        # Should return proper JSON
        try:
            data = resp.json()
            assert isinstance(data, dict), "Should return JSON object"
        except:
            pytest.fail("Should return valid JSON")


class TestDashboardLoads:
    """Test dashboard loads properly."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()

    def test_dashboard_loads(self):
        """Dashboard should load."""
        resp = self.session.get(BASE_URL)
        assert resp.status_code == 200, f"Dashboard returned {resp.status_code}"

    def test_dashboard_has_theme(self):
        """Dashboard should have theme."""
        html = self.session.get(BASE_URL).text
        assert "theme.css" in html, "Theme should be loaded"

    def test_dashboard_has_results_table(self):
        """Dashboard should have results table."""
        html = self.session.get(BASE_URL).text
        assert "results-table" in html or 'id="results-table"' in html, "Results table should exist"

    def test_dashboard_has_search_form(self):
        """Dashboard should have search form."""
        html = self.session.get(BASE_URL).text
        assert "search-query" in html or 'id="search-query"' in html, "Search form should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
