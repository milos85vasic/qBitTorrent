import sys
import os
import pytest

import importlib.util

spec = importlib.util.spec_from_file_location(
    "webui_bridge",
    os.path.join(os.path.dirname(__file__), "..", "..", "webui-bridge.py")
)
wb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wb)

WebUIBridgeHandler = wb.WebUIBridgeHandler
PRIVATE_TRACKERS = wb.PRIVATE_TRACKERS
BRIDGE_PORT = wb.BRIDGE_PORT
QBITTORRENT_PORT = wb.QBITTORRENT_PORT

class TestPrivateTrackersConfig:
    def test_all_expected_trackers_present(self):
        assert "rutracker" in PRIVATE_TRACKERS
        assert "kinozal" in PRIVATE_TRACKERS
        assert "nnmclub" in PRIVATE_TRACKERS
        assert "iptorrents" in PRIVATE_TRACKERS

    def test_rutracker_domains(self):
        assert "rutracker.org" in PRIVATE_TRACKERS["rutracker"]

    def test_nnmclub_domains_include_me(self):
        assert "nnm-club.me" in PRIVATE_TRACKERS["nnmclub"]

    def test_iptorrents_domains(self):
        assert "iptorrents.com" in PRIVATE_TRACKERS["iptorrents"]

class TestIdentifyPlugin:
    def setup_method(self):
        self.handler = WebUIBridgeHandler.__new__(WebUIBridgeHandler)

    def test_rutracker_org(self):
        assert self.handler.identify_plugin("https://rutracker.org/forum/dl.php?t=123") == "rutracker"

    def test_kinozal(self):
        assert self.handler.identify_plugin("https://kinozal.tv/details.php?id=456") == "kinozal"

    def test_nnmclub_to(self):
        assert self.handler.identify_plugin("https://nnmclub.to/forum/viewtopic.php?t=1") == "nnmclub"

    def test_nnmclub_me(self):
        assert self.handler.identify_plugin("https://nnm-club.me/forum/viewtopic.php?t=1") == "nnmclub"

    def test_iptorrents(self):
        assert self.handler.identify_plugin("https://iptorrents.com/t/12345") == "iptorrents"

    def test_unknown(self):
        assert self.handler.identify_plugin("https://example.com/file.torrent") is None

    def test_empty(self):
        assert self.handler.identify_plugin("") is None

    def test_case_insensitive(self):
        assert self.handler.identify_plugin("HTTPS://RUTRACKER.ORG/forum") == "rutracker"

class TestDefaultPorts:
    def test_bridge_port(self):
        assert BRIDGE_PORT == 78666

    def test_qbittorrent_port(self):
        assert QBITTORRENT_PORT == 79085