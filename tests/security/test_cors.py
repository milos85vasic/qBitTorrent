from __future__ import annotations

import importlib
import os
import sys

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


def _make_client(allowed_origins_env: str | None) -> TestClient:
    if allowed_origins_env is not None:
        os.environ["ALLOWED_ORIGINS"] = allowed_origins_env
    else:
        os.environ.pop("ALLOWED_ORIGINS", None)

    import api as api_mod

    api_mod = importlib.reload(api_mod)
    return TestClient(api_mod.app)


@pytest.fixture(autouse=True)
def _restore_env():
    saved = os.environ.get("ALLOWED_ORIGINS")
    yield
    if saved is not None:
        os.environ["ALLOWED_ORIGINS"] = saved
    else:
        os.environ.pop("ALLOWED_ORIGINS", None)


@pytest.mark.security
class TestCORSWildcardDefault:
    """Default CORS is wildcard (*) for local-dev convenience (dashboard from phone/LAN)."""

    def test_default_allows_any_origin(self):
        client = _make_client(None)
        resp = client.get("/health", headers={"Origin": "http://192.168.1.100:7187"})
        acao = resp.headers.get("access-control-allow-origin")
        assert acao == "*"

    def test_default_allows_localhost(self):
        client = _make_client(None)
        resp = client.get("/health", headers={"Origin": "http://localhost:7187"})
        acao = resp.headers.get("access-control-allow-origin")
        assert acao == "*"


@pytest.mark.security
class TestCORSAllowsConfiguredOrigins:
    def test_localhost_7187_allowed(self):
        client = _make_client("http://localhost:7186,http://localhost:7187")
        resp = client.get("/health", headers={"Origin": "http://localhost:7187"})
        acao = resp.headers.get("access-control-allow-origin")
        assert acao == "http://localhost:7187"

    def test_localhost_7186_allowed(self):
        client = _make_client("http://localhost:7186,http://localhost:7187")
        resp = client.get("/health", headers={"Origin": "http://localhost:7186"})
        acao = resp.headers.get("access-control-allow-origin")
        assert acao == "http://localhost:7186"

    def test_unknown_origin_not_allowed(self):
        client = _make_client("http://localhost:7186,http://localhost:7187")
        resp = client.get("/health", headers={"Origin": "http://evil.example.com"})
        acao = resp.headers.get("access-control-allow-origin")
        assert acao is None
