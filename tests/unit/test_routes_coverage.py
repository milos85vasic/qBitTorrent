"""
Additional coverage for api/routes.py — search endpoints, download, magnet.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))


class TestDetectQualityFallback:
    def test_uhd_4k_by_size(self):
        from api.routes import _detect_quality

        assert _detect_quality("some movie", "50 TB") == "uhd_4k"

    def test_hd_by_size(self):
        from api.routes import _detect_quality

        assert _detect_quality("some movie", "3 GB") == "hd"

    def test_sd_by_size_exact_boundary(self):
        from api.routes import _detect_quality

        assert _detect_quality("some movie", "300 MB") == "sd"


class TestGetSearch:
    @pytest.mark.asyncio
    async def test_search_not_found(self):
        from api.routes import get_search

        mock_orch = MagicMock()
        mock_orch.get_search_status.return_value = None
        mock_req = MagicMock()

        with patch("api.routes._get_orchestrator", return_value=mock_orch):
            with pytest.raises(Exception) as exc_info:
                await get_search("nonexistent", mock_req)
            assert exc_info.value.status_code == 404


class TestAbortSearch:
    @pytest.mark.asyncio
    async def test_abort_existing(self):
        from api.routes import abort_search

        mock_orch = MagicMock()
        mock_meta = MagicMock()
        mock_orch._active_searches = {"s1": mock_meta}
        mock_req = MagicMock()

        with patch("api.routes._get_orchestrator", return_value=mock_orch):
            result = await abort_search("s1", mock_req)
            assert result["status"] == "aborted"

    @pytest.mark.asyncio
    async def test_abort_not_found(self):
        from api.routes import abort_search

        mock_orch = MagicMock()
        mock_orch._active_searches = {}
        mock_req = MagicMock()

        with patch("api.routes._get_orchestrator", return_value=mock_orch):
            result = await abort_search("nonexistent", mock_req)
            assert result["status"] == "not_found"


class TestSearchStream:
    @pytest.mark.asyncio
    async def test_search_not_found_stream(self):
        from api.routes import search_stream

        mock_orch = MagicMock()
        mock_orch._active_searches = {}
        mock_req = MagicMock()

        with patch("api.routes._get_orchestrator", return_value=mock_orch):
            with pytest.raises(Exception) as exc_info:
                await search_stream("nonexistent", mock_req)
            assert exc_info.value.status_code == 404


class TestSaveLoadCredentials:
    def test_save_creates_file(self, tmp_path):
        import json

        from api.routes import _save_qbit_credentials

        creds_file = str(tmp_path / "creds.json")
        data = {"username": "admin", "password": "secret"}
        _save_qbit_credentials(creds_file, data)

        with open(creds_file) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_load_missing_file(self):
        from api.routes import _load_saved_qbit_credentials

        with patch("os.path.isfile", return_value=False):
            assert _load_saved_qbit_credentials() is None

    def test_load_corrupt_file(self):
        from api.routes import _load_saved_qbit_credentials

        with patch("os.path.isfile", return_value=True), patch("builtins.open", side_effect=Exception("read error")):
            assert _load_saved_qbit_credentials() is None


class TestGetQbitUsernamePassword:
    def test_username_from_saved(self):
        from api.routes import _get_qbit_username

        with patch("api.routes._load_saved_qbit_credentials", return_value={"username": "saved_user", "password": "p"}):
            assert _get_qbit_username() == "saved_user"

    def test_username_from_env(self):
        from api.routes import _get_qbit_username

        with (
            patch("api.routes._load_saved_qbit_credentials", return_value=None),
            patch.dict(os.environ, {"QBITTORRENT_USER": "env_user"}, clear=False),
        ):
            assert _get_qbit_username() == "env_user"

    def test_password_from_saved(self):
        from api.routes import _get_qbit_password

        with patch("api.routes._load_saved_qbit_credentials", return_value={"username": "u", "password": "saved_pass"}):
            assert _get_qbit_password() == "saved_pass"

    def test_password_from_env(self):
        from api.routes import _get_qbit_password

        with (
            patch("api.routes._load_saved_qbit_credentials", return_value=None),
            patch.dict(os.environ, {"QBITTORRENT_PASS": "env_pass"}, clear=False),
        ):
            assert _get_qbit_password() == "env_pass"


class TestGenerateMagnet:
    @pytest.mark.asyncio
    async def test_generate_magnet_with_hash(self):
        from api.routes import generate_magnet

        mock_req = MagicMock()
        mock_req.json = AsyncMock(
            return_value={
                "result_id": "test_result",
                "download_urls": ["magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abcd"],
            }
        )

        result = await generate_magnet(mock_req)
        assert "magnet:" in result["magnet"]
        assert len(result["hashes"]) == 1

    @pytest.mark.asyncio
    async def test_generate_magnet_invalid_request(self):
        from api.routes import generate_magnet

        mock_req = MagicMock()
        mock_req.json = AsyncMock(side_effect=Exception("bad json"))

        result = await generate_magnet(mock_req)
        assert result.status_code == 400


class TestInitiateDownload:
    @pytest.mark.asyncio
    async def test_auth_failed(self):
        from api.routes import initiate_download
        from api.routes import DownloadRequest

        mock_resp = AsyncMock()
        mock_resp.text = AsyncMock(return_value="Fail")
        mock_resp.status = 403
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_req = MagicMock()
        req = DownloadRequest(result_id="test", download_urls=["https://example.com/file.torrent"])

        with (
            patch("api.routes._get_orchestrator", return_value=MagicMock()),
            patch("api.routes._get_qbit_username", return_value="admin"),
            patch("api.routes._get_qbit_password", return_value="admin"),
            patch("api.hooks.dispatch_event", new_callable=AsyncMock),
            patch("aiohttp.ClientSession", return_value=mock_session),
        ):
            result = await initiate_download(req, mock_req)
            assert result["status"] == "auth_failed"


class TestActiveDownloads:
    @pytest.mark.asyncio
    async def test_auth_failure(self):
        from api.routes import get_active_downloads

        mock_resp = AsyncMock()
        mock_resp.text = AsyncMock(return_value="Fail")
        mock_resp.status = 403
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("api.routes._get_qbit_username", return_value="admin"),
            patch("api.routes._get_qbit_password", return_value="admin"),
            patch("aiohttp.ClientSession", return_value=mock_session),
        ):
            result = await get_active_downloads()
            assert result["downloads"] == []
            assert result.get("error") == "auth failed"

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        from api.routes import get_active_downloads

        with (
            patch("api.routes._get_qbit_username", return_value="admin"),
            patch("api.routes._get_qbit_password", return_value="admin"),
            patch("aiohttp.ClientSession", side_effect=Exception("no connection")),
        ):
            result = await get_active_downloads()
            assert result["downloads"] == []
            assert result.get("error") == "unavailable"
