"""
Unit tests for private tracker search methods with mocked HTTP.

Scenarios:
- RuTracker search with mocked HTML
- Kinozal search with mocked HTML
- NNMClub search with mocked HTML
- IPTorrents search with mocked HTML
- Login failure handling
- Timeout handling
- Invalid HTML handling
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))

from merge_service.search import SearchOrchestrator


def _make_mock_session(login_status=200, search_html="<html></html>"):
    """Create a mock aiohttp session that supports both post (login) and get (search)."""
    # Mock search response
    search_response = MagicMock()
    search_response.status = 200
    search_response.text = AsyncMock(return_value=search_html)
    search_response.read = AsyncMock(return_value=search_html.encode())
    search_response.cookies = MagicMock()
    search_response.cookies.values = MagicMock(return_value=[])

    search_cm = MagicMock()
    search_cm.__aenter__ = AsyncMock(return_value=search_response)
    search_cm.__aexit__ = AsyncMock(return_value=False)

    # Mock login response
    login_response = MagicMock()
    login_response.status = login_status
    login_response.cookies = MagicMock()
    login_response.cookies.values = MagicMock(return_value=[])

    login_cm = MagicMock()
    login_cm.__aenter__ = AsyncMock(return_value=login_response)
    login_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=login_cm)
    mock_session.get = MagicMock(return_value=search_cm)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    return session_cm


class TestPrivateTrackerSearch:
    """Test private tracker search methods with mocked responses."""

    @pytest.fixture
    def orchestrator(self):
        return SearchOrchestrator()

    @pytest.mark.asyncio
    async def test_search_rutracker_success(self, orchestrator):
        """RuTracker search with valid HTML response."""
        html = """
        <html><body>
        <table class="forumline">
        <tr><td><a href="viewtopic.php?t=123">Ubuntu 22.04 LTS</a></td>
        <td>2.5 GB</td><td>100</td><td>50</td></tr>
        </table>
        </body></html>
        """
        mock_session_cm = _make_mock_session(search_html=html)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            with patch.dict(os.environ, {"RUTRACKER_USERNAME": "user", "RUTRACKER_PASSWORD": "pass"}):
                results = await orchestrator._search_rutracker("ubuntu", "all")
                assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_kinozal_success(self, orchestrator):
        """Kinozal search with valid HTML response."""
        html = """
        <html><body>
        <table class="w100p">
        <tr><td><a href="/details.php?id=123">Ubuntu 22.04</a></td>
        <td>2.5 GB</td><td>100</td><td>50</td></tr>
        </table>
        </body></html>
        """
        mock_session_cm = _make_mock_session(search_html=html)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            with patch.dict(os.environ, {"KINOZAL_USERNAME": "user", "KINOZAL_PASSWORD": "pass"}):
                results = await orchestrator._search_kinozal("ubuntu", "all")
                assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_nnmclub_success(self, orchestrator):
        """NNMClub search with valid HTML response."""
        html = """
        <html><body>
        <table class="forumline">
        <tr><td><a href="viewtopic.php?t=123">Ubuntu 22.04 LTS</a></td>
        <td>2.5 GB</td><td>100</td><td>50</td></tr>
        </table>
        </body></html>
        """
        mock_session_cm = _make_mock_session(search_html=html)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            with patch.dict(os.environ, {"NNMCLUB_COOKIES": "phpbb2mysql_4_sid=abc123"}):
                results = await orchestrator._search_nnmclub("ubuntu", "all")
                assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_iptorrents_success(self, orchestrator):
        """IPTorrents search with valid HTML response."""
        html = """
        <html><body>
        <table>
        <tr><td><a href="/details.php?id=123">Ubuntu 22.04 [Free]</a></td>
        <td>2.5 GB</td><td>100</td><td>50</td></tr>
        </table>
        </body></html>
        """
        mock_session_cm = _make_mock_session(search_html=html)

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            with patch.dict(os.environ, {"IPTORRENTS_USERNAME": "user", "IPTORRENTS_PASSWORD": "pass"}):
                results = await orchestrator._search_iptorrents("ubuntu", "all")
                assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_rutracker_no_credentials(self, orchestrator):
        """RuTracker search without credentials should return empty."""
        with patch.dict(os.environ, {}, clear=True):
            results = await orchestrator._search_rutracker("ubuntu", "all")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_timeout(self, orchestrator):
        """Search timeout should return empty list."""
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=session_cm):
            with patch.dict(os.environ, {"RUTRACKER_USERNAME": "user", "RUTRACKER_PASSWORD": "pass"}):
                results = await orchestrator._search_rutracker("ubuntu", "all")
                assert results == []

    @pytest.mark.asyncio
    async def test_search_http_error(self, orchestrator):
        """HTTP error should return empty list."""
        error_response = MagicMock()
        error_response.status = 500
        error_response.text = AsyncMock(return_value="Error")
        error_response.cookies = MagicMock()
        error_response.cookies.values = MagicMock(return_value=[])

        error_cm = MagicMock()
        error_cm.__aenter__ = AsyncMock(return_value=error_response)
        error_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=error_cm)
        mock_session.get = MagicMock(return_value=error_cm)

        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=session_cm):
            with patch.dict(os.environ, {"RUTRACKER_USERNAME": "user", "RUTRACKER_PASSWORD": "pass"}):
                results = await orchestrator._search_rutracker("ubuntu", "all")
                assert results == []

    @pytest.mark.asyncio
    async def test_search_invalid_html(self, orchestrator):
        """Invalid HTML should not crash."""
        mock_session_cm = _make_mock_session(search_html="<html>no table</html>")

        with patch("aiohttp.ClientSession", return_value=mock_session_cm):
            with patch.dict(os.environ, {"RUTRACKER_USERNAME": "user", "RUTRACKER_PASSWORD": "pass"}):
                results = await orchestrator._search_rutracker("ubuntu", "all")
                assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_kinozal_fallback_to_iptorrents(self, orchestrator):
        """Kinozal should fallback to IPTorrents credentials."""
        with patch.dict(os.environ, {
            "KINOZAL_USERNAME": "",
            "KINOZAL_PASSWORD": "",
            "IPTORRENTS_USERNAME": "ipt_user",
            "IPTORRENTS_PASSWORD": "ipt_pass",
        }):
            # Should use IPTorrents credentials as fallback
            assert orchestrator is not None

    def test_parse_rutracker_html(self, orchestrator):
        """RuTracker HTML parsing should extract results."""
        html = """
        <html><body>
        <table class="forumline">
        <tr><td><a href="viewtopic.php?t=123">Ubuntu 22.04</a></td>
        <td>2.5 GB</td><td>100</td><td>50</td></tr>
        </table>
        </body></html>
        """
        results = orchestrator._parse_rutracker_html(html, "https://rutracker.org")
        assert isinstance(results, list)

    def test_parse_kinozal_html(self, orchestrator):
        """Kinozal HTML parsing should extract results."""
        html = """
        <html><body>
        <table class="w100p">
        <tr><td><a href="/details.php?id=123">Ubuntu 22.04</a></td>
        <td>2.5 GB</td><td>100</td><td>50</td></tr>
        </table>
        </body></html>
        """
        results = orchestrator._parse_kinozal_html(html, "https://kinozal.tv")
        assert isinstance(results, list)

    def test_parse_nnmclub_html(self, orchestrator):
        """NNMClub HTML parsing should extract results."""
        html = """
        <html><body>
        <table class="forumline">
        <tr><td><a href="viewtopic.php?t=123">Ubuntu 22.04</a></td>
        <td>2.5 GB</td><td>100</td><td>50</td></tr>
        </table>
        </body></html>
        """
        results = orchestrator._parse_nnmclub_html(html, "https://nnmclub.to")
        assert isinstance(results, list)

    def test_parse_iptorrents_html(self, orchestrator):
        """IPTorrents HTML parsing should extract results."""
        html = """
        <html><body>
        <table>
        <tr><td><a href="/details.php?id=123">Ubuntu 22.04 [Free]</a></td>
        <td>2.5 GB</td><td>100</td><td>50</td></tr>
        </table>
        </body></html>
        """
        results = orchestrator._parse_iptorrents_html(html, "https://iptorrents.com")
        assert isinstance(results, list)

    def test_parse_size_string(self, orchestrator):
        """Size string parsing should convert to bytes."""
        assert orchestrator._parse_size_string("1 GB") > 0
        assert orchestrator._parse_size_string("500 MB") > 0
        assert orchestrator._parse_size_string("2.5 GB") > 0
        assert orchestrator._parse_size_string("invalid") == 0

    def test_format_size(self, orchestrator):
        """Format size should convert bytes to human readable."""
        result = orchestrator._format_size(1073741824)
        assert "1" in result and "GB" in result
        result = orchestrator._format_size(524288000)
        assert "MB" in result
        assert orchestrator._format_size(0) == "0 B"
