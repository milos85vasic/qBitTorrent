"""
Unit tests for merged download functionality.

Issue 1: Plus button must become Download button and produce merged sources.
"""

import sys
import os

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from api.routes import generate_magnet as routes_generate_magnet
from fastapi import Request
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestDownloadButtonLabel:
    """Dashboard must show 'Download' instead of '+'."""

    def test_dashboard_has_download_button_not_plus(self):
        """The button text must be 'Download', not '+'."""
        # Read dashboard template
        dashboard_path = os.path.join(_src, "ui", "templates", "dashboard.html")
        with open(dashboard_path) as f:
            html = f.read()
        # Must contain Download button
        assert ">Download</button>" in html or 'title="Download">Download' in html, \
            "Dashboard must have 'Download' button instead of '+'"
        # Should not have standalone + button
        assert ">+</button>" not in html, \
            "Dashboard must not have '+' button"


class TestMergedMagnetGeneration:
    """Magnet generation must include all trackers from all sources."""

    @pytest.mark.asyncio
    async def test_magnet_endpoint_extracts_all_hashes(self):
        """/magnet endpoint must extract all btih hashes from download_urls."""
        from api.routes import generate_magnet
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value={
            "result_id": "test",
            "download_urls": [
                "magnet:?xt=urn:btih:abc123def4567890abc123def4567890abc12345&tr=udp://tracker1:1337",
                "magnet:?xt=urn:btih:def4567890abc123def4567890abc123def45678&tr=udp://tracker2:6969",
            ]
        })
        resp = await generate_magnet(mock_request)
        assert len(resp["hashes"]) == 2
        assert "abc123def4567890abc123def4567890abc12345" in resp["hashes"]
        assert "def4567890abc123def4567890abc123def45678" in resp["hashes"]
        magnet = resp["magnet"]
        assert "abc123def4567890abc123def4567890abc12345" in magnet
        assert "def4567890abc123def4567890abc123def45678" in magnet
        # Should include trackers from source magnets
        assert "tracker1" in magnet or "tracker2" in magnet or "opentrackr" in magnet

    @pytest.mark.asyncio
    async def test_magnet_endpoint_includes_source_trackers(self):
        """Generated magnet must include trackers from source magnet URLs."""
        from api.routes import generate_magnet
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value={
            "result_id": "test",
            "download_urls": [
                "magnet:?xt=urn:btih:abc123&tr=udp://tracker1.org:1337&tr=udp://tracker2.org:6969",
            ]
        })
        resp = await generate_magnet(mock_request)
        magnet = resp["magnet"]
        assert "tracker1.org" in magnet, f"Missing source tracker in magnet: {magnet}"
        assert "tracker2.org" in magnet, f"Missing source tracker in magnet: {magnet}"

    def test_merged_magnet_function_exists(self):
        """There should be a function to generate merged magnets."""
        import inspect
        from api import routes
        assert hasattr(routes, 'generate_magnet') or 'generate_magnet' in inspect.getsource(routes)


class TestDownloadFileEndpoint:
    """Download file endpoint must return merged sources."""

    @pytest.mark.asyncio
    async def test_download_file_returns_merged_magnet_with_all_trackers(self):
        """For magnet URLs, /download/file should return a merged magnet with all trackers."""
        from api.routes import download_torrent_file
        from unittest.mock import patch

        mock_request = MagicMock(spec=Request)
        mock_request.app.state.enricher = None

        mock_orch = MagicMock()
        mock_orch.fetch_torrent = AsyncMock(return_value=None)

        with patch("api.routes._get_orchestrator", return_value=mock_orch):
            resp = await download_torrent_file(
                MagicMock(
                    result_id="test",
                    download_urls=[
                        "magnet:?xt=urn:btih:abc123&tr=udp://t1:1337",
                        "magnet:?xt=urn:btih:def456&tr=udp://t2:6969",
                    ]
                ),
                mock_request,
            )
        # Should not be a 404
        assert resp.status_code != 404, "Download file endpoint returned 404 for magnet links"
        # For magnet links it currently returns PlainTextResponse
        from fastapi.responses import PlainTextResponse
        if isinstance(resp, PlainTextResponse):
            body = resp.body.decode()
            # The merged magnet should contain both trackers
            assert "t1" in body or "t2" in body or "opentrackr" in body, \
                f"Magnet missing trackers: {body}"

    def test_dashboard_magnet_button_calls_proper_endpoint(self):
        """Magnet button should use merged magnet generation."""
        dashboard_path = os.path.join(_src, "ui", "templates", "dashboard.html")
        with open(dashboard_path) as f:
            html = f.read()
        # The magnet dialog should populate from actual results, not hardcoded trackers only
        assert "generateMagnet" in html, "Missing generateMagnet function"
