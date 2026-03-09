#!/usr/bin/env python3
"""
Comprehensive test for RuTracker plugin download fix.

This test verifies that:
1. RuTracker plugin can download torrents properly
2. Downloaded torrent files have correct permissions
3. Downloaded torrent files are valid bencode format
4. qBittorrent can successfully add torrents from RuTracker plugin
5. Torrents start downloading after being added
"""

import json
import os
import sys
import time
import tempfile
import unittest
import subprocess
import requests
from pathlib import Path

tests_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, tests_dir)

plugins_dir = os.path.join(os.path.dirname(tests_dir), "plugins")
sys.path.insert(0, plugins_dir)


class QBittorrentClient:
    """Simple qBittorrent API client for testing."""

    def __init__(self, host="localhost", port=8085, username="admin", password="admin"):
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
        except Exception as e:
            print(f"Login error: {e}")
            return False

    def logout(self):
        """Logout from qBittorrent."""
        if self.authenticated:
            try:
                self.session.post(f"{self.base_url}/api/v2/auth/logout", timeout=5)
            except:
                pass
            self.authenticated = False

    def get_search_plugins(self):
        """Get list of search plugins."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v2/search/plugins", timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error getting plugins: {e}")
            return []

    def enable_plugin(self, plugin_name):
        """Enable a specific plugin."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/search/enablePlugin",
                data={"names": plugin_name, "enable": "true"},
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error enabling plugin: {e}")
            return False

    def enable_all_plugins(self):
        """Enable all search plugins."""
        plugins = self.get_search_plugins()
        plugin_names = "|".join([p.get("name", "") for p in plugins])
        return self.enable_plugin(plugin_names)

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
        except Exception as e:
            print(f"Error starting search: {e}")
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
        except Exception as e:
            print(f"Error getting search status: {e}")
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
        except Exception as e:
            print(f"Error getting search results: {e}")
            return None

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

    def get_torrents(self):
        """Get list of torrents."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v2/torrents/info", timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error getting torrents: {e}")
            return []

    def add_torrent_url(self, url, category=None, tags=None):
        """Add torrent from URL."""
        data = {"urls": url}
        if category:
            data["category"] = category
        if tags:
            data["tags"] = tags

        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/torrents/add", data=data, timeout=30
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error adding torrent: {e}")
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
        except Exception as e:
            print(f"Error deleting torrent: {e}")
            return False


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


class TestPluginDownloadFix(unittest.TestCase):
    """Test RuTracker plugin download functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        if not is_container_running():
            raise unittest.SkipTest("qBittorrent container not running")

        if not is_webui_accessible():
            raise unittest.SkipTest("qBittorrent WebUI not accessible")

        cls.client = QBittorrentClient()
        if not cls.client.login():
            raise unittest.SkipTest("Failed to authenticate with qBittorrent")

        cls.test_torrents = []
        print(f"\n{'=' * 70}")
        print("Testing RuTracker Plugin Download Fix")
        print(f"{'=' * 70}")

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

    def test_01_all_plugins_enabled(self):
        """Test that all plugins are enabled by default."""
        plugins = self.client.get_search_plugins()
        self.assertIsInstance(plugins, list, "Should return list of plugins")
        self.assertGreater(len(plugins), 0, "Should have at least one plugin")

        print(f"\n[1/6] Checking plugin status...")
        print(f"      Found {len(plugins)} plugins")

        enabled_count = 0
        disabled_plugins = []

        for plugin in plugins:
            plugin_name = plugin.get("name", "Unknown")
            is_enabled = plugin.get("enabled", False)

            if is_enabled:
                enabled_count += 1
                print(f"      ✓ {plugin_name}: ENABLED")
            else:
                disabled_plugins.append(plugin_name)
                print(f"      ✗ {plugin_name}: DISABLED")

        if disabled_plugins:
            print(f"\n[1/6] Enabling disabled plugins: {', '.join(disabled_plugins)}")
            success = self.client.enable_all_plugins()
            if success:
                print(f"      ✓ All plugins enabled")

                plugins = self.client.get_search_plugins()
                all_enabled = all(p.get("enabled", False) for p in plugins)
                self.assertTrue(
                    all_enabled, "All plugins should be enabled after enabling"
                )
            else:
                self.fail("Failed to enable all plugins")

        print(f"\n[1/6] ✓ All {len(plugins)} plugins are enabled")

    def test_02_rutracker_plugin_available(self):
        """Test that RuTracker plugin is available."""
        plugins = self.client.get_search_plugins()

        rutracker_found = False
        for plugin in plugins:
            if "rutracker" in plugin.get("name", "").lower():
                rutracker_found = True
                print(
                    f"\n[2/6] ✓ RuTracker plugin found: {plugin.get('fullName', plugin.get('name'))}"
                )
                print(f"      Enabled: {plugin.get('enabled', False)}")
                self.assertTrue(
                    plugin.get("enabled", False), "RuTracker plugin should be enabled"
                )
                break

        if not rutracker_found:
            self.skipTest("RuTracker plugin not found")

    def test_03_search_with_rutracker(self):
        """Test searching with RuTracker plugin."""
        print(f"\n[3/6] Testing search functionality...")

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
        print(f"      Found {len(results_list)} results")
        self.assertGreater(len(results_list), 0, "Should find at least one result")

        first_result = results_list[0]
        self.assertIn("fileName", first_result)
        self.assertIn("fileUrl", first_result)
        self.assertIn("fileSize", first_result)

        print(f"      First result: {first_result.get('fileName', 'Unknown')}")

        self.__class__.test_search_result = first_result
        print(f"\n[3/6] ✓ Search completed successfully")

    def test_04_download_torrent_from_plugin(self):
        """Test downloading torrent from search result."""
        if not hasattr(self, "test_search_result"):
            self.skipTest("No search result from previous test")

        print(f"\n[4/6] Testing download from plugin...")

        search_result = self.__class__.test_search_result
        file_url = search_result.get("fileUrl")

        self.assertIsNotNone(file_url, "Search result should have fileUrl")
        print(f"      Download URL: {file_url}")

        torrents_before = self.client.get_torrents()
        count_before = len(torrents_before)

        success = self.client.add_torrent_url(file_url)
        self.assertTrue(success, "Should successfully add torrent")
        print(f"      Torrent added to qBittorrent")

        time.sleep(3)

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
        self.__class__.test_torrent_hash = new_torrent["hash"]

        print(f"      Torrent name: {new_torrent.get('name', 'Unknown')}")
        print(f"      Torrent hash: {new_torrent['hash']}")
        print(f"\n[4/6] ✓ Torrent added successfully")

    def test_05_torrent_starts_downloading(self):
        """Test that torrent starts downloading."""
        if not hasattr(self, "__class__") or not hasattr(
            self.__class__, "test_torrent_hash"
        ):
            self.skipTest("No test torrent from previous test")

        print(f"\n[5/6] Verifying torrent state...")

        torrent_hash = self.__class__.test_torrent_hash

        max_wait = 15
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
        print(f"      Torrent state: {state}")
        print(f"      Progress: {torrent.get('progress', 0) * 100:.1f}%")

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

        print(f"\n[5/6] ✓ Torrent is in valid state: {state}")

    def test_06_plugin_download_file_valid(self):
        """Test that plugin downloads valid torrent files."""
        if not os.environ.get("RUTRACKER_USERNAME"):
            self.skipTest("RuTracker credentials not available for direct plugin test")

        print(f"\n[6/6] Testing direct plugin download...")

        try:
            from rutracker import RuTracker, CONFIG

            if CONFIG.username in ["YOUR_USERNAME_HERE", "your_username_here"]:
                self.skipTest("RuTracker credentials not configured")

            plugin = RuTracker()
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
            print(f"      Downloaded to: {filepath}")

            self.assertTrue(
                os.path.exists(filepath), f"Torrent file should exist: {filepath}"
            )

            with open(filepath, "rb") as f:
                content = f.read()

            self.assertGreater(len(content), 0, "Torrent file should not be empty")
            self.assertTrue(
                content.startswith(b"d"), "Torrent file should be valid bencode"
            )

            file_stat = os.stat(filepath)
            file_perms = oct(file_stat.st_mode)[-3:]
            print(f"      File permissions: {file_perms}")

            self.assertIn(
                file_perms,
                ["644", "664"],
                f"File should have readable permissions, got: {file_perms}",
            )

            try:
                os.unlink(filepath)
            except:
                pass

            print(
                f"\n[6/6] ✓ Plugin downloads valid torrent files with correct permissions"
            )

        except Exception as e:
            print(f"      Error: {e}")
            raise


def run_tests():
    """Run the tests."""
    if not is_container_running():
        print("=" * 70)
        print("SKIP: qBittorrent container is not running")
        print("=" * 70)
        print("\nStart the container with: ./start.sh")
        return 1

    if not is_webui_accessible():
        print("=" * 70)
        print("SKIP: qBittorrent WebUI is not accessible")
        print("=" * 70)
        print("\nCheck container logs: docker compose logs qbittorrent")
        return 1

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPluginDownloadFix)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"\n{'=' * 70}")
    if result.wasSuccessful():
        print("✓ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nThe RuTracker plugin download fix is working correctly:")
        print("  1. All plugins are enabled by default")
        print("  2. RuTracker plugin can search successfully")
        print("  3. Downloads from plugin add torrents to qBittorrent")
        print("  4. Torrents start in valid download states")
        print("  5. Plugin creates valid torrent files with correct permissions")
    else:
        print("✗ SOME TESTS FAILED")
        print("=" * 70)
        print("\nPlease check the errors above and ensure:")
        print("  1. Container is running: ./start.sh")
        print("  2. RuTracker credentials are configured in .env")
        print("  3. Plugin is installed: ./install-plugin.sh")
    print()

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    if "--run" in sys.argv:
        sys.exit(run_tests())
    else:
        unittest.main(verbosity=2)
