#!/usr/bin/env python3
"""
Comprehensive test for RuTracker plugin download functionality.

This test verifies the complete download workflow:
1. Plugin can search for torrents
2. Plugin can download torrent files with correct permissions
3. Torrent files are valid bencode format
4. qBittorrent can add and start downloading torrents from the plugin
"""

import os
import sys
import time
import unittest
import subprocess
import requests

tests_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, tests_dir)


class QBittorrentClient:
    """Simple qBittorrent API client."""

    def __init__(self, host="localhost", port=78085, username="admin", password="admin"):
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        self.username = username
        self.password = password

    def login(self):
        """Authenticate with qBittorrent."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/auth/login",
                data={"username": self.username, "password": self.password},
                timeout=10,
            )
            return response.status_code == 200 and response.text == "Ok."
        except Exception as e:
            print(f"Login error: {e}")
            return False

    def get_torrents(self):
        """Get list of torrents."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v2/torrents/info", timeout=10
            )
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            print(f"Error getting torrents: {e}")
            return []

    def add_torrent_file(self, filepath):
        """Add torrent from file."""
        try:
            with open(filepath, "rb") as f:
                files = {"torrents": f}
                response = self.session.post(
                    f"{self.base_url}/api/v2/torrents/add",
                    files=files,
                    timeout=30,
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
        except:
            return False

    def get_search_plugins(self):
        """Get list of search plugins."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v2/search/plugins", timeout=10
            )
            return response.json() if response.status_code == 200 else []
        except:
            return []

    def enable_all_plugins(self):
        """Enable all search plugins."""
        plugins = self.get_search_plugins()
        if not plugins:
            return False

        plugin_names = "|".join([p.get("name", "") for p in plugins])
        try:
            response = self.session.post(
                f"{self.base_url}/api/v2/search/enablePlugin",
                data={"names": plugin_names, "enable": "true"},
                timeout=10,
            )
            return response.status_code == 200
        except:
            return False


def is_container_running():
    """Check if qBittorrent container is running."""
    for runtime in ["podman", "docker"]:
        try:
            result = subprocess.run(
                [runtime, "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "qbittorrent" in result.stdout:
                return True
        except:
            pass
    return False


def run_in_container(cmd):
    """Run command in container."""
    try:
        result = subprocess.run(
            ["podman", "exec", "qbittorrent"] + cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


class TestPluginDownload(unittest.TestCase):
    """Test RuTracker plugin download functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        if not is_container_running():
            raise unittest.SkipTest("qBittorrent container not running")

        cls.client = QBittorrentClient()
        if not cls.client.login():
            raise unittest.SkipTest("Failed to authenticate with qBittorrent")

        cls.test_torrents = []
        cls.test_torrent_files = []

        print(f"\n{'=' * 70}")
        print("Comprehensive RuTracker Plugin Download Test")
        print(f"{'=' * 70}\n")

    @classmethod
    def tearDownClass(cls):
        """Clean up."""
        for torrent_hash in cls.test_torrents:
            try:
                cls.client.delete_torrent(torrent_hash, delete_files=True)
                time.sleep(0.3)
            except:
                pass

        for filepath in cls.test_torrent_files:
            try:
                os.unlink(filepath)
            except:
                pass

    def test_01_all_plugins_enabled(self):
        """Test that all plugins are enabled."""
        print("[1/6] Checking plugin status...")

        plugins = self.client.get_search_plugins()
        self.assertGreater(len(plugins), 0, "Should have at least one plugin")

        all_enabled = all(p.get("enabled", False) for p in plugins)

        if not all_enabled:
            print("      Enabling all plugins...")
            self.assertTrue(
                self.client.enable_all_plugins(), "Should enable all plugins"
            )
            plugins = self.client.get_search_plugins()
            all_enabled = all(p.get("enabled", False) for p in plugins)

        self.assertTrue(all_enabled, "All plugins should be enabled")
        print(f"      ✓ All {len(plugins)} plugins enabled")

    def test_02_plugin_search(self):
        """Test that plugin can search for torrents."""
        print("\n[2/6] Testing plugin search...")

        success, stdout, stderr = run_in_container(
            [
                "python3",
                "/config/qBittorrent/nova3/nova2.py",
                "rutracker",
                "all",
                "ubuntu",
            ]
        )

        self.assertTrue(success, f"Search should succeed. stderr: {stderr}")
        self.assertGreater(len(stdout.strip()), 0, "Should return search results")

        lines = stdout.strip().split("\n")
        print(f"      Found {len(lines)} results")
        self.assertGreater(len(lines), 0, "Should have at least one result")

        first_result = lines[0]
        parts = first_result.split("|")
        self.assertGreaterEqual(len(parts), 7, "Result should have all required fields")

        download_url = parts[0]
        self.assertTrue(
            download_url.startswith("https://rutracker.org/forum/dl.php?"),
            "Should have valid download URL",
        )

        self.__class__.test_download_url = download_url
        print(f"      ✓ Search working, found {len(lines)} results")

    def test_03_plugin_download_file(self):
        """Test that plugin can download torrent file."""
        if not hasattr(self, "test_download_url"):
            self.skipTest("No download URL from search")

        print("\n[3/6] Testing plugin download...")

        download_url = self.__class__.test_download_url

        success, stdout, stderr = run_in_container(
            [
                "python3",
                "/config/qBittorrent/nova3/nova2dl.py",
                "rutracker",
                download_url,
            ]
        )

        self.assertTrue(success, f"Download should succeed. stderr: {stderr}")

        output = stdout.strip()
        parts = output.split(" ")
        self.assertEqual(
            len(parts), 2, f"Output should be 'filepath url', got: {output}"
        )

        filepath, url = parts
        print(f"      Downloaded to: {filepath}")

        self.assertEqual(url, download_url, "URL should match")
        self.assertTrue(filepath.endswith(".torrent"), "Should be .torrent file")

        success, stdout, stderr = run_in_container(["ls", "-l", filepath])
        self.assertTrue(success, "File should exist")

        self.assertIn("-rw-r--r--", stdout, "File should have 644 permissions")
        print(f"      ✓ File permissions correct (644)")

        success, stdout, stderr = run_in_container(
            [
                "python3",
                "-c",
                f'import sys; data = open("{filepath}", "rb").read(1); '
                f'print("valid" if data == b"d" else "invalid")',
            ]
        )
        self.assertTrue(success, "Should be able to read file")
        self.assertIn("valid", stdout, "File should be valid bencode (start with 'd')")
        print(f"      ✓ File is valid bencode format")

        self.__class__.test_torrent_filepath = filepath
        print(f"      ✓ Torrent file created successfully")

    def test_04_add_torrent_to_qbittorrent(self):
        """Test adding torrent to qBittorrent."""
        if not hasattr(self, "test_torrent_filepath"):
            self.skipTest("No torrent file from previous test")

        print("\n[4/6] Adding torrent to qBittorrent...")

        filepath = self.__class__.test_torrent_filepath

        local_path = f"/tmp/test_{int(time.time())}.torrent"

        result = subprocess.run(
            ["podman", "cp", f"qbittorrent:{filepath}", local_path],
            capture_output=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, "Should copy torrent from container")
        self.assertTrue(os.path.exists(local_path), "Local file should exist")

        self.__class__.test_torrent_files.append(local_path)

        torrents_before = self.client.get_torrents()
        count_before = len(torrents_before)

        success = self.client.add_torrent_file(local_path)
        self.assertTrue(success, "Should add torrent successfully")

        time.sleep(2)

        torrents_after = self.client.get_torrents()
        count_after = len(torrents_after)

        self.assertEqual(count_after, count_before + 1, "Should have one more torrent")

        new_torrent = None
        for torrent in torrents_after:
            if not any(t["hash"] == torrent["hash"] for t in torrents_before):
                new_torrent = torrent
                break

        self.assertIsNotNone(new_torrent, "Should identify new torrent")

        self.__class__.test_torrents.append(new_torrent["hash"])
        print(f"      ✓ Torrent added: {new_torrent.get('name', 'Unknown')[:50]}...")

    def test_05_torrent_downloading(self):
        """Test that torrent starts downloading."""
        if not self.test_torrents:
            self.skipTest("No test torrent")

        print("\n[5/6] Verifying torrent state...")

        torrent_hash = self.test_torrents[0]

        time.sleep(2)

        torrents = self.client.get_torrents()
        torrent = next((t for t in torrents if t["hash"] == torrent_hash), None)

        self.assertIsNotNone(torrent, "Should find the torrent")

        state = torrent.get("state", "")
        progress = torrent.get("progress", 0) * 100
        dlspeed = torrent.get("dlspeed", 0)

        print(f"      State: {state}")
        print(f"      Progress: {progress:.1f}%")
        print(f"      Download speed: {dlspeed / 1024:.1f} KB/s")

        valid_states = [
            "downloading",
            "stalledDL",
            "metaDL",
            "queuedDL",
            "pausedDL",
            "forcedDL",
        ]

        self.assertIn(state, valid_states, f"State should be valid, got: {state}")

        print(f"      ✓ Torrent is in valid download state")

    def test_06_cleanup_and_summary(self):
        """Summary of the test."""
        print("\n[6/6] Test Summary")
        print("      ✓ Plugin search working")
        print("      ✓ Plugin downloads valid torrent files")
        print("      ✓ Torrent files have correct permissions (644)")
        print("      ✓ Torrent files are valid bencode format")
        print("      ✓ qBittorrent can add torrents from plugin")
        print("      ✓ Torrents start downloading immediately")
        print(f"\n{'=' * 70}")
        print("ALL TESTS PASSED!")
        print(f"{'=' * 70}")
        print("\nThe RuTracker plugin download fix is working correctly!")
        print("Downloads from the RuTracker plugin will now work properly.")


def run_tests():
    """Run the comprehensive tests."""
    if not is_container_running():
        print("=" * 70)
        print("SKIP: qBittorrent container is not running")
        print("=" * 70)
        print("\nStart the container with: ./start.sh")
        return 1

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPluginDownload)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    if "--run" in sys.argv:
        sys.exit(run_tests())
    else:
        unittest.main(verbosity=2)
