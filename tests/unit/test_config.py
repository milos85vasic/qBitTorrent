import sys
import os
import pytest
from unittest.mock import patch

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src")
)

from config import EnvConfig, load_env, get_config, reload_config


class TestEnvConfig:
    def test_defaults_with_empty_env(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_env()
            assert config.qbittorrent_host == "localhost"
            assert config.qbittorrent_port == 79085
            assert config.qbittorrent_username == "admin"
            assert config.qbittorrent_password == "admin"
            assert config.proxy_port == 78085
            assert config.log_level == "INFO"

    def test_explicit_user_pass_vars(self):
        with patch.dict(
            os.environ,
            {"QBITTORRENT_USER": "myuser", "QBITTORRENT_PASS": "mypass"},
            clear=True,
        ):
            config = load_env()
            assert config.qbittorrent_username == "myuser"
            assert config.qbittorrent_password == "mypass"

    def test_fallback_username_password(self):
        with patch.dict(
            os.environ,
            {"QBITTORRENT_USERNAME": "fbuser", "QBITTORRENT_PASSWORD": "fbpass"},
            clear=True,
        ):
            config = load_env()
            assert config.qbittorrent_username == "fbuser"
            assert config.qbittorrent_password == "fbpass"

    def test_explicit_takes_precedence_over_fallback(self):
        with patch.dict(
            os.environ,
            {
                "QBITTORRENT_USER": "explicit",
                "QBITTORRENT_USERNAME": "fallback",
                "QBITTORRENT_PASS": "explicit_pass",
                "QBITTORRENT_PASSWORD": "fallback_pass",
            },
            clear=True,
        ):
            config = load_env()
            assert config.qbittorrent_username == "explicit"
            assert config.qbittorrent_password == "explicit_pass"

    def test_custom_host_and_port(self):
        with patch.dict(
            os.environ,
            {"QBITTORRENT_HOST": "192.168.1.100", "QBITTORRENT_PORT": "9090"},
            clear=True,
        ):
            config = load_env()
            assert config.qbittorrent_host == "192.168.1.100"
            assert config.qbittorrent_port == 9090

    def test_tracker_credentials(self):
        with patch.dict(
            os.environ,
            {
                "RUTRACKER_USERNAME": "ru_user",
                "RUTRACKER_PASSWORD": "ru_pass",
                "KINOZAL_USERNAME": "kz_user",
                "KINOZAL_PASSWORD": "kz_pass",
                "NNMCLUB_COOKIES": "sid=abc123",
                "IPTORRENTS_USERNAME": "ip_user",
                "IPTORRENTS_PASSWORD": "ip_pass",
            },
            clear=True,
        ):
            config = load_env()
            assert config.rutracker_username == "ru_user"
            assert config.kinozal_username == "kz_user"
            assert config.nnmclub_cookies == "sid=abc123"
            assert config.iptorrents_username == "ip_user"

    def test_optional_api_keys_none_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_env()
            assert config.omdb_api_key is None
            assert config.tmdb_api_key is None
            assert config.anilist_client_id is None

    def test_api_keys_loaded(self):
        with patch.dict(
            os.environ,
            {
                "OMDB_API_KEY": "omdb123",
                "TMDB_API_KEY": "tmdb456",
            },
            clear=True,
        ):
            config = load_env()
            assert config.omdb_api_key == "omdb123"
            assert config.tmdb_api_key == "tmdb456"

    def test_get_config_singleton(self):
        reload_config()
        with patch.dict(os.environ, {}, clear=True):
            c1 = get_config()
            c2 = get_config()
            assert c1 is c2

    def test_reload_config(self):
        with patch.dict(os.environ, {"QBITTORRENT_HOST": "reloaded"}, clear=True):
            reload_config()
            c = get_config()
            assert c.qbittorrent_host == "reloaded"
