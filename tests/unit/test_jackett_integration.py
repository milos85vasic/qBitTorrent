"""Tests for Jackett auto-discovery and integration.

Covers:
1. Jackett plugin env-var override (JACKETT_API_KEY, JACKETT_URL)
2. Key extraction from Jackett ServerConfig.json
3. Merge-service tracker registration when key is present
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")
_MS_PATH = os.path.join(_SRC_PATH, "merge_service")

if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

sys.modules.setdefault("merge_service", type(sys)("merge_service"))
sys.modules["merge_service"].__path__ = [_MS_PATH]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _import_search_module():
    spec = importlib.util.spec_from_file_location("merge_service.search", os.path.join(_MS_PATH, "search.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["merge_service.search"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def search_mod():
    return _import_search_module()


# ---------------------------------------------------------------------------
# 1. Jackett plugin env-var override
# ---------------------------------------------------------------------------
class TestJackettPluginEnvOverride:
    def _run_plugin_in_subprocess(self, tmpdir: str, env: dict | None = None) -> subprocess.CompletedProcess:
        """Copy the real jackett plugin into tmpdir with stubs and run it."""
        plugin_src = os.path.join(_REPO_ROOT, "plugins", "community", "jackett.py")

        # Minimal stubs for qBittorrent plugin dependencies
        helpers_py = os.path.join(tmpdir, "helpers.py")
        with open(helpers_py, "w") as f:
            f.write(
                "def enable_socks_proxy(enable): pass\n"
                "def download_file(url): return url\n"
            )

        novaprinter_py = os.path.join(tmpdir, "novaprinter.py")
        with open(novaprinter_py, "w") as f:
            f.write("def prettyPrinter(d): pass\n")

        # Copy plugin
        plugin_dst = os.path.join(tmpdir, "jackett.py")
        with open(plugin_src) as f:
            src = f.read()
        with open(plugin_dst, "w") as f:
            f.write(src)

        script = (
            "import sys\n"
            f"sys.path.insert(0, '{tmpdir}')\n"
            "import jackett\n"
            "print(jackett.jackett.api_key + '|' + jackett.jackett.url)\n"
        )
        return subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_env_api_key_overrides_json(self):
        """When JACKETT_API_KEY is set, the plugin must use it instead of the JSON file value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "jackett.json")
            with open(json_path, "w") as f:
                json.dump({"api_key": "json-key", "url": "http://127.0.0.1:9117", "tracker_first": False}, f)

            env = os.environ.copy()
            env["JACKETT_API_KEY"] = "env-key-123"
            result = self._run_plugin_in_subprocess(tmpdir, env)
            assert result.returncode == 0, f"stderr: {result.stderr}"
            api_key, url = result.stdout.strip().split("|")
            assert api_key == "env-key-123"
            assert url == "http://127.0.0.1:9117"

    def test_env_url_overrides_json(self):
        """When JACKETT_URL is set, the plugin must use it instead of the JSON file value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "jackett.json")
            with open(json_path, "w") as f:
                json.dump({"api_key": "k", "url": "http://old:9117", "tracker_first": False}, f)

            env = {k: v for k, v in os.environ.items() if not k.startswith("JACKETT_")}
            env["JACKETT_URL"] = "http://jackett:9117"
            result = self._run_plugin_in_subprocess(tmpdir, env)
            assert result.returncode == 0, f"stderr: {result.stderr}"
            api_key, url = result.stdout.strip().split("|")
            assert api_key == "k"
            assert url == "http://jackett:9117"

    def test_no_env_uses_json_value(self):
        """Without env vars, the plugin must use the JSON file value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "jackett.json")
            with open(json_path, "w") as f:
                json.dump({"api_key": "json-key", "url": "http://json:9117", "tracker_first": False}, f)

            env = {k: v for k, v in os.environ.items() if not k.startswith("JACKETT_")}
            result = self._run_plugin_in_subprocess(tmpdir, env)
            assert result.returncode == 0, f"stderr: {result.stderr}"
            api_key, url = result.stdout.strip().split("|")
            assert api_key == "json-key"
            assert url == "http://json:9117"


# ---------------------------------------------------------------------------
# 2. Key extraction script
# ---------------------------------------------------------------------------
class TestExtractJackettKey:
    def test_extracts_valid_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, "config", "jackett", "Jackett")
            os.makedirs(config_dir)
            config_file = os.path.join(config_dir, "ServerConfig.json")
            with open(config_file, "w") as f:
                json.dump({"APIKey": "abc123", "Port": 9117}, f)

            script_path = os.path.join(_REPO_ROOT, "scripts", "extract-jackett-key.py")
            env = os.environ.copy()
            env["JACKETT_POLL_INTERVAL"] = "0.05"
            env["JACKETT_POLL_MAX_SECONDS"] = "1"
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                cwd=tmpdir,
                env=env,
            )
            assert result.returncode == 0
            assert result.stdout.strip() == "abc123"

    def test_ignores_placeholder_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, "config", "jackett", "Jackett")
            os.makedirs(config_dir)
            config_file = os.path.join(config_dir, "ServerConfig.json")
            with open(config_file, "w") as f:
                json.dump({"APIKey": "YOUR_API_KEY_HERE", "Port": 9117}, f)

            script_path = os.path.join(_REPO_ROOT, "scripts", "extract-jackett-key.py")
            env = os.environ.copy()
            env["JACKETT_POLL_INTERVAL"] = "0.05"
            env["JACKETT_POLL_MAX_SECONDS"] = "1"
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                cwd=tmpdir,
                env=env,
            )
            assert result.returncode == 0
            assert result.stdout.strip() == ""

    def test_empty_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(_REPO_ROOT, "scripts", "extract-jackett-key.py")
            env = os.environ.copy()
            env["JACKETT_POLL_INTERVAL"] = "0.05"
            env["JACKETT_POLL_MAX_SECONDS"] = "1"
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                cwd=tmpdir,
                env=env,
            )
            assert result.returncode == 0
            assert result.stdout.strip() == ""

    def test_polls_until_key_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, "config", "jackett", "Jackett")
            os.makedirs(config_dir)
            config_file = os.path.join(config_dir, "ServerConfig.json")

            script_path = os.path.join(_REPO_ROOT, "scripts", "extract-jackett-key.py")
            env = os.environ.copy()
            env["JACKETT_POLL_INTERVAL"] = "0.1"
            env["JACKETT_POLL_MAX_SECONDS"] = "5"
            # Start the extractor in the background; it will poll
            proc = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=tmpdir,
                env=env,
            )

            # Write the config file after a short delay
            import time
            time.sleep(0.3)
            with open(config_file, "w") as f:
                json.dump({"APIKey": "delayed-key", "Port": 9117}, f)

            try:
                stdout, stderr = proc.communicate(timeout=10)
                assert proc.returncode == 0
                assert stdout.strip() == "delayed-key"
            except subprocess.TimeoutExpired:
                proc.kill()
                pytest.fail("extract-jackett-key.py did not finish polling")


# ---------------------------------------------------------------------------
# 3. Merge-service integration
# ---------------------------------------------------------------------------
class TestMergeServiceJackettIntegration:
    def test_jackett_enabled_when_env_key_present(self, search_mod, monkeypatch):
        orch = search_mod.SearchOrchestrator()
        monkeypatch.setenv("JACKETT_API_KEY", "auto-discovered-key")
        trackers = orch._get_enabled_trackers()
        names = [t.name for t in trackers]
        assert "jackett" in names

    def test_jackett_url_is_localhost_9117(self, search_mod, monkeypatch):
        orch = search_mod.SearchOrchestrator()
        monkeypatch.setenv("JACKETT_API_KEY", "auto-discovered-key")
        trackers = orch._get_enabled_trackers()
        jackett = next((t for t in trackers if t.name == "jackett"), None)
        assert jackett is not None
        assert jackett.url == "http://localhost:9117"

    def test_jackett_disabled_when_placeholder(self, search_mod, monkeypatch):
        orch = search_mod.SearchOrchestrator()
        monkeypatch.setenv("JACKETT_API_KEY", "YOUR_API_KEY_HERE")
        trackers = orch._get_enabled_trackers()
        names = [t.name for t in trackers]
        assert "jackett" not in names

    def test_jackett_routed_to_public_tracker_search(self, search_mod):
        import asyncio
        from unittest.mock import AsyncMock, patch

        orch = search_mod.SearchOrchestrator()
        tracker = search_mod.TrackerSource(name="jackett", url="http://localhost:9117", enabled=True)

        with patch.object(orch, "_search_public_tracker", new_callable=AsyncMock) as mock:
            mock.return_value = []
            asyncio.run(orch._search_tracker(tracker, "test", "all"))
            mock.assert_called_once_with("jackett", "test", "all")
