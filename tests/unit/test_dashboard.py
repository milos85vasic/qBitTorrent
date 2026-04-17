import sys
import os
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))

# Work around pytest importlib mode creating namespace package for 'api'
if "api" in sys.modules and not getattr(sys.modules.get("api"), "__file__", None):
    del sys.modules["api"]

from api import app
from fastapi.testclient import TestClient


client = TestClient(app)


class TestDashboardEndpoint:
    def test_root_returns_html(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_dashboard_returns_html(self):
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_dashboard_contains_results_table(self):
        response = client.get("/dashboard")
        html = response.text
        assert "results-table" in html
        assert "data-sort=" in html


class TestConfigEndpoint:
    def test_config_returns_qbittorrent_url(self):
        response = client.get("/api/v1/config")
        assert response.status_code == 200
        data = response.json()
        assert "qbittorrent_url" in data
        assert "qbittorrent_host" in data
        assert data["qbittorrent_port"] == 7185


class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestStatsEndpoint:
    def test_stats_endpoint(self):
        response = client.get("/api/v1/stats")
        assert response.status_code == 200


class TestQBitAuthEndpoint:
    def test_qbittorrent_auth_endpoint_exists(self):
        response = client.post("/api/v1/auth/qbittorrent", json={"username": "admin", "password": "admin"})
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_qbittorrent_login_modal_in_html(self):
        response = client.get("/dashboard")
        html = response.text
        assert "qbit-login-modal" in html
        assert 'id="qbit-username"' in html
        assert 'id="qbit-password"' in html

    def test_qbittorrent_login_functions_defined(self):
        response = client.get("/dashboard")
        html = response.text
        assert "function openQbitLogin()" in html
        assert "function closeQbitLogin()" in html
        assert "function submitQbitLogin()" in html
