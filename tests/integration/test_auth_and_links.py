"""
Comprehensive tests for qBittorrent auth states and service links.

Covers:
- admin/admin default password setup
- Temp password state detection
- Auth status endpoint accuracy
- Service link accessibility
- Dashboard auth handling
"""

import pytest
import requests


class TestQbitDefaultPassword:
    """Verify admin/admin is the default qBittorrent password."""

    @pytest.fixture(autouse=True)
    def _services_up(self, all_services_live):
        self.base_url = all_services_live["merge_service"]
        self.qbit_url = all_services_live["qbittorrent"]

    def test_admin_admin_login_succeeds(self):
        """qBittorrent must accept admin/admin credentials."""
        resp = requests.post(
            f"{self.qbit_url}/api/v2/auth/login",
            data={"username": "admin", "password": "admin"},
            timeout=30,
        )
        assert resp.status_code == 200
        assert resp.text.strip() == "Ok.", f"Unexpected response: {resp.text!r}"

    def test_wrong_password_rejected(self):
        """Wrong password must be rejected."""
        resp = requests.post(
            f"{self.qbit_url}/api/v2/auth/login",
            data={"username": "admin", "password": "wrong"},
            timeout=30,
        )
        assert resp.status_code == 200
        assert resp.text.strip() == "Fails."

    def test_auth_grants_api_access(self):
        """Successful login must grant access to protected API."""
        session = requests.Session()
        login = session.post(
            f"{self.qbit_url}/api/v2/auth/login",
            data={"username": "admin", "password": "admin"},
            timeout=30,
        )
        assert login.text.strip() == "Ok."

        version = session.get(f"{self.qbit_url}/api/v2/app/version", timeout=30)
        assert version.status_code == 200
        assert version.text.startswith("v")

    def test_auth_status_reflects_session(self):
        """Merge service auth status must reflect live qBittorrent session."""
        # First ensure we have valid saved credentials
        requests.post(
            f"{self.base_url}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin", "save": True},
            timeout=30,
        )

        status = requests.get(f"{self.base_url}/api/v1/auth/status", timeout=30).json()
        qbit = status["trackers"]["qbittorrent"]
        assert qbit["has_session"] is True, "Expected qBittorrent session to be active"
        assert qbit["username"] == "admin"

    def test_auth_status_fails_with_bad_saved_creds(self):
        """Auth status must show false when saved credentials file has wrong password."""
        import os
        import tempfile

        # Write bad credentials to a temp file and copy into the proxy container
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"username":"admin","password":"wrongwrong"}')
            tmp_path = f.name

        os.system(f"podman cp {tmp_path} qbittorrent-proxy:/config/download-proxy/qbittorrent_creds.json")
        os.unlink(tmp_path)

        status = requests.get(f"{self.base_url}/api/v1/auth/status", timeout=30).json()
        qbit = status["trackers"]["qbittorrent"]

        # Restore correct credentials
        requests.post(
            f"{self.base_url}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin", "save": True},
            timeout=30,
        )

        assert qbit["has_session"] is False, "Expected qBittorrent session to be inactive with wrong creds"


class TestServiceLinksAccessibility:
    """Verify service links are accessible."""

    @pytest.fixture(autouse=True)
    def _services_up(self, all_services_live):
        self.base_url = all_services_live["merge_service"]
        self.qbit_url = all_services_live["qbittorrent"]

    def test_merge_search_dashboard_accessible(self):
        """Боба Dashboard (port 7187) must be accessible."""
        r = requests.get(f"{self.base_url}/dashboard", timeout=30)
        assert r.status_code == 200
        assert "Боба Dashboard" in r.text

    def test_qbittorrent_webui_accessible(self):
        """qBittorrent WebUI (port 7185) must respond."""
        r = requests.get(self.qbit_url, timeout=30)
        # qBittorrent returns 200 for the login page or 403 if already authenticated
        assert r.status_code in (200, 403)

    def test_download_proxy_accessible(self):
        """Download proxy (port 7186) must respond (same URL as qbittorrent_live)."""
        r = requests.get(self.qbit_url, timeout=30)
        # Proxy might return various status codes
        assert r.status_code < 500

    def test_dashboard_is_angular_app(self):
        """Dashboard must be the Angular SPA."""
        r = requests.get(f"{self.base_url}/dashboard", timeout=30)
        assert r.status_code == 200
        assert "<app-root>" in r.text or "<app-root></app-root>" in r.text
        assert "<base href=\"/\">" in r.text
        assert "<script src=\"main-" in r.text


class TestAuthEndpointBehavior:
    """Test auth endpoint behavior with different qBittorrent states."""

    @pytest.fixture(autouse=True)
    def _service_up(self, merge_service_live):
        self.base_url = merge_service_live

    def test_qbittorrent_login_endpoint_accepts_valid(self):
        """POST /auth/qbittorrent must return authenticated for valid creds."""
        resp = requests.post(
            f"{self.base_url}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin", "save": False},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "authenticated"
        assert data["version"].startswith("v")

    def test_qbittorrent_login_endpoint_rejects_invalid(self):
        """POST /auth/qbittorrent must return failed for invalid creds."""
        resp = requests.post(
            f"{self.base_url}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "wrong", "save": False},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"

    def test_download_endpoint_auth_failed_with_bad_saved_creds(self):
        """POST /download must return auth_failed when qBittorrent rejects login."""
        import os
        import tempfile

        # Write bad credentials to a temp file and copy into the proxy container
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"username":"admin","password":"wrong"}')
            tmp_path = f.name

        os.system(f"podman cp {tmp_path} qbittorrent-proxy:/config/download-proxy/qbittorrent_creds.json")
        os.unlink(tmp_path)

        resp = requests.post(
            f"{self.base_url}/api/v1/download",
            json={"result_id": "test", "download_urls": ["magnet:?xt=urn:btih:8bb5455909752072cce7b2556b825d2faaf7c0fb"]},
            timeout=30,
        )

        # Restore correct credentials
        requests.post(
            f"{self.base_url}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin", "save": True},
            timeout=30,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "auth_failed"

    def test_download_endpoint_succeeds_with_valid_creds(self, fresh_magnet_uri):
        """POST /download must return initiated when qBittorrent accepts login.

        ``fresh_magnet_uri`` is a random 40-char-hex btih so
        qBittorrent can't duplicate-reject it if a previous run
        added the same synthetic torrent.
        """
        # Ensure correct credentials are saved
        requests.post(
            f"{self.base_url}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin", "save": True},
            timeout=30,
        )

        resp = requests.post(
            f"{self.base_url}/api/v1/download",
            json={"result_id": "test", "download_urls": [fresh_magnet_uri]},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "initiated"
        assert data["added_count"] >= 1


class TestPasswordScripts:
    """Verify password setup scripts are functional."""

    def test_fix_qbit_password_script_exists(self):
        import os
        assert os.path.isfile("fix-qbit-password.sh")

    def test_init_qbit_password_script_exists(self):
        import os
        assert os.path.isfile("init-qbit-password.sh")

    def test_fix_script_uses_correct_api(self):
        """fix-qbit-password.sh must use qBittorrent 5.x web_ui_password API."""
        with open("fix-qbit-password.sh") as f:
            content = f.read()
        assert 'json={"web_ui_password":"admin"}' in content
        assert "WebUI\\Password" not in content, "Old qBittorrent 4.x format detected"

    def test_init_script_uses_correct_api(self):
        """init-qbit-password.sh must use qBittorrent 5.x web_ui_password API."""
        with open("init-qbit-password.sh") as f:
            content = f.read()
        assert "web_ui_password" in content

    def test_start_script_uses_correct_api(self):
        """start.sh ensure_webui_password must use qBittorrent 5.x API."""
        with open("start.sh") as f:
            content = f.read()
        assert 'json={"web_ui_password":"admin"}' in content
        assert "WebUI.Password" not in content, "Old qBittorrent 4.x format detected"
