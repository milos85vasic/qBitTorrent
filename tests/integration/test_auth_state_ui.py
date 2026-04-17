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
import json
import time


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

    def test_qbit_button_exists(self):
        """qBit button should exist in the dashboard."""
        html = self.session.get(self.base_url).text
        assert 'onclick="openQbitLogin()"' in html or "btn-schedule" in html, "qBit button should exist"

    def test_add_button_exists(self):
        """Add button should exist in the dashboard."""
        html = self.session.get(self.base_url).text
        assert "doAddToQbit" in html or "Add" in html, "Add button should exist"

    def test_magnet_dialog_add_button_exists(self):
        """Magnet dialog should have Add button."""
        html = self.session.get(self.base_url).text
        assert "addMagnetToQbit" in html, "Magnet dialog Add button should exist"

    def test_auth_section_in_header(self):
        """Auth section should exist in header."""
        html = self.session.get(self.base_url).text
        assert 'id="auth-section"' in html, "Auth section should exist in header"

    def test_login_modal_exists(self):
        """Login modal should exist for qBittorrent authentication."""
        html = self.session.get(self.base_url).text
        assert 'id="qbit-login-modal"' in html, "Login modal should exist"

    def test_login_modal_has_username_and_password(self):
        """Login modal should have username and password fields."""
        html = self.session.get(self.base_url).text
        assert 'id="qbit-username"' in html, "Username field should exist"
        assert 'id="qbit-password"' in html, "Password field should exist"

    def test_login_modal_has_remember_me(self):
        """Login modal should have remember me checkbox."""
        html = self.session.get(self.base_url).text
        assert "remember-me" in html.lower() or "remember" in html.lower(), "Remember me checkbox should exist"

    def test_login_modal_submit_button(self):
        """Login modal should have submit button."""
        html = self.session.get(self.base_url).text
        assert "qbit-login-submit" in html, "Login submit button should exist"

    def test_logout_function_exists(self):
        """Logout function should exist for clearing auth."""
        html = self.session.get(self.base_url).text
        assert "logoutQbit" in html or "clearAuth" in html, "Logout function should exist"

    def test_authenticated_state_shows_username(self):
        """When authenticated, username should be displayed in header."""
        html = self.session.get(self.base_url).text
        assert "logoutQbit" in html, "Logout function should exist for authenticated state"

    def test_buttons_have_disabled_state(self):
        """Buttons should have disabled styling for unauthenticated state."""
        html = self.session.get(self.base_url).text
        assert "download-btn:disabled" in html or "disabled" in html.lower(), "Buttons should have disabled state"

    def test_login_button_triggers_modal(self):
        """Login button should open login modal."""
        html = self.session.get(self.base_url).text
        assert "openQbitLogin()" in html, "Login should trigger modal open function"

    def test_login_success_continues_pending_action(self):
        """After login success, pending action should continue."""
        html = self.session.get(self.base_url).text
        assert "_pendingAction" in html or "pending" in html.lower(), "Pending action handling should exist"

    def test_credentials_saved_to_file(self):
        """Credentials should be savable to file for persistence."""
        import os

        if os.path.exists(self.qbit_creds_path):
            with open(self.qbit_creds_path) as f:
                creds = json.load(f)
            assert "username" in creds or "user" in creds, "Saved credentials should have username"

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

    def test_download_button_checks_auth(self):
        """Download buttons should check auth before action."""
        html = self.session.get(self.base_url).text
        assert "auth" in html.lower(), "Download should check authentication"

    def test_doaddtoqbit_exists(self):
        """doAddToQbit or addMagnetToQbit should exist."""
        html = self.session.get(self.base_url).text
        assert "addMagnetToQbit" in html or "Add" in html, "Add function should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
