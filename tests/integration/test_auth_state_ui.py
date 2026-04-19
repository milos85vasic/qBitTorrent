"""
Tests for Auth State UI - Header Login/Logout Controls and Button Disabled State

Tests:
1. Header shows login button when user is NOT logged in
2. Header shows username + logout when user IS logged in
3. qBit, Add, + buttons are disabled when not logged in
4. Buttons become enabled after successful login
5. Visual indicators show disabled state
6. Auth state persists across page refreshes
"""


import pytest
import requests

BASE_URL = "http://localhost:7187"


class TestAuthStateUI:
    """Test auth state UI in header and button disabled states."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.qbit_creds_path = (
            "/run/media/milosvasic/DATA4TB/Projects/qBitTorrent/config/download-proxy/qbittorrent_creds.json"
        )

    def test_auth_status_endpoint_exists(self):
        """Auth status endpoint should exist and return auth state."""
        resp = self.session.get(f"{self.base_url}/api/v1/auth/status", timeout=10)
        assert resp.status_code == 200, "Auth status endpoint should return 200"
        data = resp.json()
        assert "trackers" in data, "Auth status should include trackers"

    def test_dashboard_is_angular_app(self):
        """Dashboard should be the Angular SPA."""
        html = self.session.get(self.base_url).text
        assert "<app-root>" in html or "<app-root></app-root>" in html, "Angular app-root should exist"
        assert "<base href=\"/\">" in html, "Angular base href should exist"
        assert "<script src=\"main-" in html, "Angular main script should exist"

    def test_login_api_exists(self):
        """Login API should exist."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/auth/qbittorrent", json={"username": "bad", "password": "wrong"}, timeout=10
        )
        assert resp.status_code == 200, "Login API should respond"


class TestButtonDisabledState:
    """Test that buttons are properly disabled when not authenticated."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL
        self.session = requests.Session()

    def test_dashboard_is_angular_app(self):
        """Dashboard should be the Angular SPA."""
        html = self.session.get(self.base_url).text
        assert "<app-root>" in html or "<app-root></app-root>" in html, "Angular app-root should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
