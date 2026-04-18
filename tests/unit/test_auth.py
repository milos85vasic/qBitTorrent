"""
Tests for the auth module — CAPTCHA proxy and tracker authentication.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src")
)


class TestAuthRouter:
    def test_router_exists(self):
        from api.auth import router

        assert router is not None
        assert router.prefix == "/auth"

    def test_pending_captchas_dict(self):
        from api.auth import _pending_captchas

        assert isinstance(_pending_captchas, dict)

    def test_captcha_login_request_model(self):
        from api.auth import CaptchaLoginRequest

        req = CaptchaLoginRequest(
            cap_sid="test_sid",
            cap_code_field="cap_code_123",
            captcha_text="abc123",
            captcha_token="token123",
        )
        assert req.cap_sid == "test_sid"
        assert req.captcha_text == "abc123"
        assert req.captcha_token == "token123"

    def test_cookie_login_request_model(self):
        from api.auth import CookieLoginRequest

        req = CookieLoginRequest(cookie_string="bb_session=xxx; sid=yyy")
        assert "bb_session" in req.cookie_string


class TestTrackerDomains:
    def test_iptorrents_in_tracker_domains(self):
        from api.routes import TRACKER_DOMAINS

        assert "iptorrents.com" in TRACKER_DOMAINS
        assert "iptorrents.me" in TRACKER_DOMAINS

    def test_iptorrents_detected_as_tracker(self):
        from api.routes import _is_tracker_url

        assert (
            _is_tracker_url(
                "https://iptorrents.com/download.php/12345/filename.torrent"
            )
            == "iptorrents"
        )
        assert (
            _is_tracker_url("https://iptorrents.me/details.php?id=12345")
            == "iptorrents"
        )

    def test_rutracker_still_detected(self):
        from api.routes import _is_tracker_url

        assert (
            _is_tracker_url("https://rutracker.org/forum/dl.php?t=12345") == "rutracker"
        )
        assert (
            _is_tracker_url("https://rutracker.nl/forum/dl.php?t=12345") == "rutracker"
        )

    def test_kinozal_still_detected(self):
        from api.routes import _is_tracker_url

        assert _is_tracker_url("https://kinozal.tv/download.php?id=12345") == "kinozal"

    def test_nnmclub_still_detected(self):
        from api.routes import _is_tracker_url

        assert _is_tracker_url("https://nnmclub.to/forum/topic12345") == "nnmclub"

    def test_non_tracker_returns_none(self):
        from api.routes import _is_tracker_url

        assert _is_tracker_url("https://example.com/file.torrent") is None
        assert _is_tracker_url("magnet:?xt=urn:btih:abc123") is None


class TestCaptchaParsing:
    def test_detect_captcha_image_url(self):
        import re

        html = '<img src="https://static.rutracker.cc/captcha/12345.png" alt="captcha">'
        match = re.search(
            r'<img[^>]+src="(https://static\.rutracker\.cc/captcha/[^"]+)"', html
        )
        assert match is not None
        assert "static.rutracker.cc/captcha/" in match.group(1)

    def test_detect_cap_sid(self):
        import re

        html = '<input type="hidden" name="cap_sid" value="abc123def">'
        match = re.search(r'name="cap_sid"\s+value="([^"]+)"', html)
        assert match is not None
        assert match.group(1) == "abc123def"

    def test_detect_cap_code_field(self):
        import re

        html = '<input type="text" name="cap_code_67890" size="25">'
        match = re.search(r'name="(cap_code_[^"]+)"', html)
        assert match is not None
        assert match.group(1) == "cap_code_67890"

    def test_no_captcha_in_page(self):
        import re

        html = "<html><body>No captcha here</body></html>"
        match = re.search(
            r'<img[^>]+src="(https://static\.rutracker\.cc/captcha/[^"]+)"', html
        )
        assert match is None


class TestQbitCredentialsFallback:
    def test_load_qbit_credentials_from_env(self):
        from api.auth import _load_qbit_credentials

        with patch.dict(os.environ, {"QBITTORRENT_USER": "envuser", "QBITTORRENT_PASS": "envpass"}, clear=False):
            creds = _load_qbit_credentials()
            assert creds is not None
            assert creds["username"] == "envuser"
            assert creds["password"] == "envpass"

    def test_load_qbit_credentials_prefers_json_over_env(self):
        from api.auth import _load_qbit_credentials
        import json
        from io import StringIO

        json_data = json.dumps({"username": "jsonuser", "password": "jsonpass"})

        with patch("api.auth.os.path.exists", return_value=True), \
             patch("builtins.open", return_value=StringIO(json_data)):
            creds = _load_qbit_credentials()
            assert creds["username"] == "jsonuser"
            assert creds["password"] == "jsonpass"

    def test_load_qbit_credentials_returns_none_when_no_source(self):
        from api.auth import _load_qbit_credentials

        with patch("api.auth.os.path.exists", return_value=False), \
             patch("api.auth.os.getenv", return_value=None):
            creds = _load_qbit_credentials()
            assert creds is None
