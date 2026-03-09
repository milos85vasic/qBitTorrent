#!/usr/bin/env python3
"""End-to-end tests for RuTracker plugin with qBittorrent API."""

import json
import os
import sys
import time
import unittest
import subprocess
import requests
from urllib.parse import quote

try:
    import pytest

    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

tests_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, tests_dir)

plugins_dir = os.path.join(os.path.dirname(tests_dir), "plugins")
sys.path.insert(0, plugins_dir)


class QBittorrentAPIClient:
    """Client for qBittorrent Web API."""

    def __init__(
        self, host="localhost", port=8085, username="admin", password="adminadmin"
    ):
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        self.username = username
        self.password = password
        self.authenticated = False

    def login(self):
        """Authenticate with qBittorrent."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/auth/login",
                data={"username": self.username, "password": self.password},
                timeout=10,
            )
            if response.status_code == 200 and response.text == "Ok.":
                self.authenticated = True
                return True
            return False
        except requests.exceptions.RequestException:
            return False

    def logout(self):
        """Logout from qBittorrent."""
        if self.authenticated:
            try:
                self.session.post(f"{self.base_url}/api/v2/auth/logout", timeout=5)
            except:
                pass
            self.authenticated = False

    def get_api_version(self):
        """Get API version."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v2/app/webapiVersion", timeout=5
            )
            if response.status_code == 200:
                return response.text
            return None
        except:
            return None

    def get_torrents(self):
        """Get list of torrents."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v2/torrents/info", timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return []
        except:
            return []

    def get_torrent_properties(self, torrent_hash):
        """Get torrent properties."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v2/torrents/properties",
                params={"hash": torrent_hash},
                timeout=10,
            )
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def add_torrent_url(self, url, category=None, tags=None, is_skip_checking=False):
        """Add torrent from URL."""
        data = {"urls": url}
        if category:
            data["category"] = category
        if tags:
            data["tags"] = tags
        if is_skip_checking:
            data["is_skip_checking"] = "true"

        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/torrents/add", data=data, timeout=30
            )
            return response.status_code == 200
        except:
            return False

    def add_torrent_file(self, filepath, category=None):
        """Add torrent from file."""
        try:
            with open(filepath, "rb") as f:
                files = {"torrents": f}
                data = {}
                if category:
                    data["category"] = category

                response = self.session.post(
                    f"{self.base_url}/api/v2/torrents/add",
                    files=files,
                    data=data,
                    timeout=30,
                )
                return response.status_code == 200
        except:
            return False

    def delete_torrent(self, torrent_hash, delete_files=True):
        """Delete torrent."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/torrents/delete",
                data={
                    "hashes": torrent_hash,
                    "deleteFiles": "true" if delete_files else "false",
                },
                timeout=10,
            )
            return response.status_code == 200
        except:
            return False

    def pause_torrent(self, torrent_hash):
        """Pause torrent."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/torrents/pause",
                data={"hashes": torrent_hash},
                timeout=10,
            )
            return response.status_code == 200
        except:
            return False

    def resume_torrent(self, torrent_hash):
        """Resume torrent."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/torrents/resume",
                data={"hashes": torrent_hash},
                timeout=10,
            )
            return response.status_code == 200
        except:
            return False

    def search_start(self, pattern, plugins="all"):
        """Start search job."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/search/start",
                data={"pattern": pattern, "plugins": plugins},
                timeout=30,
            )
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def search_status(self, search_id):
        """Get search job status."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/search/status",
                data={"id": search_id},
                timeout=10,
            )
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def search_results(self, search_id, limit=50, offset=0):
        """Get search results."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/search/results",
                data={"id": search_id, "limit": limit, "offset": offset},
                timeout=10,
            )
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def search_stop(self, search_id):
        """Stop search job."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/search/stop",
                data={"id": search_id},
                timeout=10,
            )
            return response.status_code == 200
        except:
            return False

    def search_delete(self, search_id):
        """Delete search job."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/search/delete",
                data={"id": search_id},
                timeout=10,
            )
            return response.status_code == 200
        except:
            return False

    def get_search_plugins(self):
        """Get list of search plugins."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v2/search/plugins", timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return []
        except:
            return []


def is_container_running():
    """Check if qBittorrent container is running."""
    try:
        result = subprocess.run(
            ["podman", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "qbittorrent" in result.stdout:
            return True
    except:
        pass

    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "qbittorrent" in result.stdout:
            return True
    except:
        pass

    return False


def is_webui_accessible():
    """Check if WebUI is accessible."""
    try:
        response = requests.get("http://localhost:8085", timeout=5)
        return response.status_code in [200, 401, 403]
    except:
        return False


@unittest.skipIf(
    not is_container_running() or not is_webui_accessible(),
    "qBittorrent container not running or WebUI not accessible",
)
class TestE2EDownload(unittest.TestCase):
    """End-to-end tests with qBittorrent API."""

    @classmethod
    def setUpClass(cls):
        """Set up test class with API client."""
        cls.client = QBittorrentAPIClient()
        cls.test_torrents = []

        if not cls.client.login():
            raise unittest.SkipTest("Failed to authenticate with qBittorrent API")

        api_version = cls.client.get_api_version()
        if not api_version:
            raise unittest.SkipTest("Failed to get qBittorrent API version")

        print(f"\nConnected to qBittorrent API version: {api_version}")

    @classmethod
    def tearDownClass(cls):
        """Clean up test torrents."""
        for torrent_hash in cls.test_torrents:
            try:
                cls.client.delete_torrent(torrent_hash, delete_files=True)
                time.sleep(0.5)
            except:
                pass
        cls.client.logout()

    def test_01_api_connection(self):
        """Test API connection is working."""
        self.assertTrue(self.client.authenticated, "API should be authenticated")
        api_version = self.client.get_api_version()
        self.assertIsNotNone(api_version, "Should get API version")

    def test_02_search_plugins_available(self):
        """Test that search plugins are available."""
        plugins = self.client.get_search_plugins()
        self.assertIsInstance(plugins, list, "Should return list of plugins")

        plugin_names = [p.get("name", "") for p in plugins]
        print(f"\nAvailable plugins: {plugin_names}")

        self.assertTrue(len(plugins) > 0, "Should have at least one plugin")

    def test_03_rutracker_plugin_enabled(self):
        """Test that RuTracker plugin is enabled."""
        plugins = self.client.get_search_plugins()

        rutracker_found = False
        for plugin in plugins:
            if "rutracker" in plugin.get("name", "").lower():
                rutracker_found = True
                self.assertTrue(
                    plugin.get("enabled", False), "RuTracker plugin should be enabled"
                )
                print(
                    f"\nRuTracker plugin found: {plugin.get('fullName', plugin.get('name'))}"
                )
                break

        if not rutracker_found:
            self.skipTest("RuTracker plugin not found in search plugins")

    def test_04_search_with_rutracker(self):
        """Test searching with RuTracker plugin."""
        search_result = self.client.search_start("ubuntu", plugins="rutracker")

        if not search_result:
            self.skipTest("Failed to start search")

        search_id = search_result.get("id")
        self.assertIsNotNone(search_id, "Should get search ID")

        max_wait = 30
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status = self.client.search_status(search_id)
            if status and isinstance(status, list) and len(status) > 0:
                job_status = status[0]
                if job_status.get("status") == "Stopped":
                    break
            time.sleep(2)

        results = self.client.search_results(search_id)

        self.client.search_delete(search_id)

        self.assertIsNotNone(results, "Should get search results")
        self.assertIn("results", results, "Results should have 'results' key")

        results_list = results.get("results", [])
        print(f"\nFound {len(results_list)} results from RuTracker")

        self.assertGreater(len(results_list), 0, "Should find at least one result")

        first_result = results_list[0]
        self.assertIn("fileName", first_result)
        self.assertIn("fileUrl", first_result)
        self.assertIn("fileSize", first_result)

        self.__class__.test_search_result = first_result

    def test_05_download_from_search_result(self):
        """Test downloading torrent from search result."""
        if not hasattr(self, "test_search_result"):
            self.skipTest("No search result from previous test")

        search_result = self.__class__.test_search_result
        file_url = search_result.get("fileUrl")

        self.assertIsNotNone(file_url, "Search result should have fileUrl")

        torrents_before = self.client.get_torrents()
        count_before = len(torrents_before)

        success = self.client.add_torrent_url(file_url)
        self.assertTrue(success, "Should successfully add torrent")

        time.sleep(2)

        torrents_after = self.client.get_torrents()
        count_after = len(torrents_after)

        self.assertEqual(count_after, count_before + 1, "Should have one more torrent")

        new_torrent = None
        for torrent in torrents_after:
            found_in_before = any(t["hash"] == torrent["hash"] for t in torrents_before)
            if not found_in_before:
                new_torrent = torrent
                break

        self.assertIsNotNone(new_torrent, "Should identify the newly added torrent")

        self.__class__.test_torrents.append(new_torrent["hash"])

        print(f"\nAdded torrent: {new_torrent.get('name', 'Unknown')}")

    def test_06_torrent_starts_downloading(self):
        """Test that torrent starts downloading (or at least gets added properly)."""
        if not hasattr(self, "__class__") or not self.__class__.test_torrents:
            self.skipTest("No test torrent from previous test")

        torrent_hash = self.__class__.test_torrents[0]

        max_wait = 10
        start_time = time.time()

        torrent = None
        while time.time() - start_time < max_wait:
            torrents = self.client.get_torrents()
            for t in torrents:
                if t["hash"] == torrent_hash:
                    torrent = t
                    break
            if torrent:
                break
            time.sleep(1)

        self.assertIsNotNone(torrent, "Should find the torrent")

        state = torrent.get("state", "")
        print(f"\nTorrent state: {state}")

        valid_states = [
            "downloading",
            "stalledDL",
            "metaDL",
            "queuedDL",
            "pausedDL",
            "forcedDL",
        ]
        self.assertIn(
            state, valid_states, f"Torrent should be in a valid state, got: {state}"
        )

        self.assertIsNotNone(torrent.get("name"), "Torrent should have a name")
        self.assertGreater(torrent.get("size", 0), 0, "Torrent should have a size")

    def test_07_torrent_properties_accessible(self):
        """Test that torrent properties are accessible."""
        if not hasattr(self, "__class__") or not self.__class__.test_torrents:
            self.skipTest("No test torrent from previous test")

        torrent_hash = self.__class__.test_torrents[0]
        properties = self.client.get_torrent_properties(torrent_hash)

        self.assertIsNotNone(properties, "Should get torrent properties")

        self.assertIn("total_size", properties)
        self.assertGreater(properties["total_size"], 0, "Torrent should have content")


class TestE2EPluginDirect(unittest.TestCase):
    """Test plugin directly with qBittorrent running."""

    @classmethod
    def setUpClass(cls):
        """Check if container is running."""
        if not is_container_running():
            raise unittest.SkipTest("qBittorrent container not running")

    @unittest.skipIf(
        not os.path.exists(os.path.expanduser("~/.qbit.env"))
        and not os.environ.get("RUTRACKER_USERNAME"),
        "RuTracker credentials not available",
    )
    def test_plugin_download_and_add_to_qbittorrent(self):
        """Test downloading via plugin and adding to qBittorrent."""
        from rutracker import RuTracker, CONFIG

        if CONFIG.username in ["YOUR_USERNAME_HERE", "your_username_here"]:
            self.skipTest("RuTracker credentials not configured")

        try:
            plugin = RuTracker()
        except Exception as e:
            self.skipTest(f"Failed to initialize RuTracker plugin: {e}")

        plugin.results = {}
        plugin.search("ubuntu")

        if not plugin.results:
            self.skipTest("No search results from RuTracker")

        first_result = list(plugin.results.values())[0]
        download_url = first_result["link"]

        captured = []
        original_stdout = sys.stdout

        class CaptureOutput:
            def write(self, text):
                captured.append(text)

            def flush(self):
                pass

        sys.stdout = CaptureOutput()

        try:
            plugin.download_torrent(download_url)
        finally:
            sys.stdout = original_stdout

        output = "".join(captured).strip()
        parts = output.split(" ")

        self.assertEqual(
            len(parts), 2, f"Output format should be 'filepath url', got: {output}"
        )

        filepath = parts[0]
        torrent_url = parts[1]

        self.assertTrue(
            os.path.exists(filepath), f"Torrent file should exist: {filepath}"
        )
        self.assertEqual(torrent_url, download_url)

        client = QBittorrentAPIClient()
        if not client.login():
            try:
                os.unlink(filepath)
            except:
                pass
            self.skipTest("Failed to authenticate with qBittorrent")

        try:
            success = client.add_torrent_file(filepath)
            self.assertTrue(success, "Should add torrent to qBittorrent")

            time.sleep(2)

            torrents = client.get_torrents()
            self.assertGreater(len(torrents), 0, "Should have torrents in qBittorrent")

            test_torrent_hash = None
            for torrent in torrents:
                if "ubuntu" in torrent.get("name", "").lower():
                    test_torrent_hash = torrent["hash"]
                    print(f"\nSuccessfully added torrent: {torrent['name']}")
                    print(f"State: {torrent['state']}")
                    break

            if test_torrent_hash:
                self.__class__.test_torrent_hash = test_torrent_hash

        finally:
            try:
                os.unlink(filepath)
            except:
                pass
            client.logout()

    @classmethod
    def tearDownClass(cls):
        """Clean up test torrent."""
        if hasattr(cls, "test_torrent_hash"):
            client = QBittorrentAPIClient()
            if client.login():
                client.delete_torrent(cls.test_torrent_hash, delete_files=True)
                client.logout()


def run_e2e_tests():
    """Run E2E tests with custom runner."""
    if not is_container_running():
        print("=" * 70)
        print("SKIP: qBittorrent container is not running")
        print("=" * 70)
        print("\nStart the container with: ./start.sh")
        return 0

    if not is_webui_accessible():
        print("=" * 70)
        print("SKIP: qBittorrent WebUI is not accessible")
        print("=" * 70)
        print("\nCheck container logs: docker compose logs qbittorrent")
        return 0

    print("=" * 70)
    print("Running E2E Tests with qBittorrent")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestE2EDownload))
    suite.addTests(loader.loadTestsFromTestCase(TestE2EPluginDirect))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    if "--direct" in sys.argv:
        sys.exit(run_e2e_tests())
    else:
        unittest.main(verbosity=2)
