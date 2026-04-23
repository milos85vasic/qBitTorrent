"""
Additional coverage for api/__init__.py — lifespan, config, health, stats, SPA.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))


class TestParseAllowedOrigins:
    def test_default_when_none(self):
        from api import _DEFAULT_ORIGINS, _parse_allowed_origins

        assert _parse_allowed_origins(None) == list(_DEFAULT_ORIGINS)

    def test_custom_origins(self):
        from api import _parse_allowed_origins

        result = _parse_allowed_origins("http://a.com, http://b.com")
        assert result == ["http://a.com", "http://b.com"]

    def test_empty_parts_fall_back(self):
        from api import _DEFAULT_ORIGINS, _parse_allowed_origins

        assert _parse_allowed_origins(",,,") == list(_DEFAULT_ORIGINS)

    def test_whitespace_only_parts_fall_back(self):
        from api import _DEFAULT_ORIGINS, _parse_allowed_origins

        assert _parse_allowed_origins(" , , ") == list(_DEFAULT_ORIGINS)


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_returns_healthy(self):
        from api import health_check

        result = await health_check()
        assert result["status"] == "healthy"
        assert result["service"] == "merge-search"
        assert result["version"] == "1.0.0"


class TestBridgeHealth:
    @pytest.mark.asyncio
    async def test_bridge_health_success(self):
        from api import bridge_health

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.dict(os.environ, {"BRIDGE_URL": "http://localhost:7188", "BRIDGE_PORT": "7188"}),
            patch("aiohttp.ClientSession", return_value=mock_session),
            patch("aiohttp.ClientTimeout", return_value=None),
        ):
            result = await bridge_health()
            assert result["healthy"] is True
            assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_bridge_health_failure(self):
        from api import bridge_health

        with (
            patch.dict(os.environ, {"BRIDGE_URL": "http://localhost:7188", "BRIDGE_PORT": "7188"}),
            patch("aiohttp.ClientSession", side_effect=Exception("connection refused")),
        ):
            result = await bridge_health()
            assert result["healthy"] is False
            assert "connection refused" in result["error"]


class TestGetConfig:
    @pytest.mark.asyncio
    async def test_get_config_default(self):
        from api import get_config
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"host": "localhost:7187"}

        with patch.dict(os.environ, {"PROXY_PORT": "7186"}, clear=False):
            result = await get_config(mock_request)
            assert "qbittorrent_url" in result
            assert "7186" in result["qbittorrent_url"]
            assert "proxy_port" in result


class TestStatsEndpoint:
    @pytest.mark.asyncio
    async def test_stats_no_orchestrator(self):
        from api import app, stats

        # Use patch.dict on the underlying _state dict directly to bypass
        # Starlette State.__setattr__ interception.
        with patch.dict(app.state._state, clear=True):
            result = await stats()
            assert result["active_searches"] == 0
            assert result["completed_searches"] == 0
            assert result["trackers"] == []

    @pytest.mark.asyncio
    async def test_stats_with_orchestrator(self):
        from api import app, stats

        meta1 = MagicMock()
        meta1.status = "running"
        meta2 = MagicMock()
        meta2.status = "completed"
        meta3 = MagicMock()
        meta3.status = "aborted"

        mock_orch = MagicMock()
        mock_orch._active_searches = {"s1": meta1, "s2": meta2, "s3": meta3}
        mock_tracker = MagicMock()
        mock_tracker.name = "rutor"
        mock_tracker.url = "https://rutor.info"
        mock_tracker.enabled = True
        mock_orch._get_enabled_trackers.return_value = [mock_tracker]

        with patch.object(app.state, "search_orchestrator", mock_orch, create=True):
            result = await stats()
            assert result["active_searches"] == 1
            assert result["completed_searches"] == 1
            assert result["aborted_searches"] == 1
            assert result["total_searches"] == 3
            assert len(result["trackers"]) == 1


class TestServeIndexHtml:
    def test_serve_no_angular(self):
        from api import _serve_index_html

        with patch("api._angular_available", False):
            result = _serve_index_html()
            assert isinstance(result, dict)
            assert result["dashboard"] == "not found"


class TestGlobalExceptionHandler:
    @pytest.mark.asyncio
    async def test_exception_handler_returns_500(self):
        from api import global_exception_handler

        mock_request = MagicMock()
        exc = RuntimeError("test error")
        response = await global_exception_handler(mock_request, exc)
        assert response.status_code == 500
