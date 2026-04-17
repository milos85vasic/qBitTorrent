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
import subprocess
import time


BASE_URL = "http://localhost:7187"
QBIT_URL = "http://localhost:7185"


class TestQbitDefaultPassword:
    """Verify admin/admin is the default qBittorrent password."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_admin_admin_login_succeeds(self):
        """qBittorrent must accept admin/admin credentials."""
        resp = requests.post(
            f"{QBIT_URL}/api/v2/auth/login",
            data={"username": "admin", "password": "admin"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.text.strip() == "Ok.", f"Unexpected response: {resp.text!r}"

    def test_wrong_password_rejected(self):
        """Wrong password must be rejected."""
        resp = requests.post(
            f"{QBIT_URL}/api/v2/auth/login",
            data={"username": "admin", "password": "wrong"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.text.strip() == "Fails."

    def test_auth_grants_api_access(self):
        """Successful login must grant access to protected API."""
        session = requests.Session()
        login = session.post(
            f"{QBIT_URL}/api/v2/auth/login",
            data={"username": "admin", "password": "admin"},
            timeout=5,
        )
        assert login.text.strip() == "Ok."

        version = session.get(f"{QBIT_URL}/api/v2/app/version", timeout=5)
        assert version.status_code == 200
        assert version.text.startswith("v")

    def test_auth_status_reflects_session(self):
        """Merge service auth status must reflect live qBittorrent session."""
        # First ensure we have valid saved credentials
        requests.post(
            f"{BASE_URL}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin", "save": True},
            timeout=5,
        )

        status = requests.get(f"{BASE_URL}/api/v1/auth/status", timeout=5).json()
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

        status = requests.get(f"{BASE_URL}/api/v1/auth/status", timeout=5).json()
        qbit = status["trackers"]["qbittorrent"]

        # Restore correct credentials
        requests.post(
            f"{BASE_URL}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin", "save": True},
            timeout=5,
        )

        assert qbit["has_session"] is False, "Expected qBittorrent session to be inactive with wrong creds"


class TestServiceLinksAccessibility:
    """Verify service links are accessible."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_merge_search_dashboard_accessible(self):
        """Merge Search dashboard (port 7187) must be accessible."""
        r = requests.get(f"{BASE_URL}/dashboard", timeout=5)
        assert r.status_code == 200
        assert "Merge Search Dashboard" in r.text

    def test_qbittorrent_webui_accessible(self):
        """qBittorrent WebUI (port 7185) must respond."""
        r = requests.get(QBIT_URL, timeout=5)
        # qBittorrent returns 200 for the login page or 403 if already authenticated
        assert r.status_code in (200, 403)

    def test_download_proxy_accessible(self):
        """Download proxy (port 7186) must respond."""
        try:
            r = requests.get("http://localhost:7186", timeout=5)
            # Proxy might return various status codes
            assert r.status_code < 500
        except requests.ConnectionError:
            pytest.skip("Download proxy not accessible")

    def test_dashboard_has_service_links(self):
        """Dashboard must contain service link elements."""
        r = requests.get(f"{BASE_URL}/dashboard", timeout=5)
        assert r.status_code == 200
        assert "qBittorrent WebUI" in r.text
        assert "Download Proxy" in r.text
        assert "Merge Search" in r.text
        assert "WebUI Bridge" in r.text

    def test_service_links_use_dynamic_host(self):
        """Service links must use window.location.hostname for dynamic resolution."""
        r = requests.get(f"{BASE_URL}/dashboard", timeout=5)
        assert "window.location.hostname" in r.text
        assert "http://' + host + ':7185" in r.text
        assert "http://' + host + ':7186" in r.text
        assert "http://' + host + ':7187" in r.text
        assert "http://' + host + ':7188" in r.text


class TestAuthEndpointBehavior:
    """Test auth endpoint behavior with different qBittorrent states."""

    @pytest.fixture(autouse=True)
    def setup(self):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            r.raise_for_status()
        except (requests.ConnectionError, requests.Timeout):
            pytest.skip("Merge service not available")

    def test_qbittorrent_login_endpoint_accepts_valid(self):
        """POST /auth/qbittorrent must return authenticated for valid creds."""
        resp = requests.post(
            f"{BASE_URL}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin", "save": False},
            timeout=5,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "authenticated"
        assert data["version"].startswith("v")

    def test_qbittorrent_login_endpoint_rejects_invalid(self):
        """POST /auth/qbittorrent must return failed for invalid creds."""
        resp = requests.post(
            f"{BASE_URL}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "wrong", "save": False},
            timeout=5,
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
            f"{BASE_URL}/api/v1/download",
            json={"result_id": "test", "download_urls": ["magnet:?xt=urn:btih:abc123"]},
            timeout=10,
        )

        # Restore correct credentials
        requests.post(
            f"{BASE_URL}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin", "save": True},
            timeout=5,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "auth_failed"

    def test_download_endpoint_succeeds_with_valid_creds(self):
        """POST /download must return initiated when qBittorrent accepts login."""
        # Ensure correct credentials are saved
        requests.post(
            f"{BASE_URL}/api/v1/auth/qbittorrent",
            json={"username": "admin", "password": "admin", "save": True},
            timeout=5,
        )

        resp = requests.post(
            f"{BASE_URL}/api/v1/download",
            json={"result_id": "test", "download_urls": ["magnet:?xt=urn:btih:abc123"]},
            timeout=10,
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
        assert "WebUI\\\\Password" not in content, "Old qBittorrent 4.x format detected"

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
