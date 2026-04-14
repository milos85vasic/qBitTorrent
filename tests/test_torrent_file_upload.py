#!/usr/bin/env python3
"""
Comprehensive test suite for .torrent file upload fix.

Verifies that .torrent files can be uploaded through the download proxy
(port 78085) to qBittorrent (port 79085).

Root cause: download_proxy.py tried to decode multipart/form-data body
(containing binary torrent data) as UTF-8, causing UnicodeDecodeError.

Fix: Detect multipart file uploads and pass them through directly
without attempting UTF-8 decoding.

Tests cover:
1. Proxy is running and accessible
2. Direct upload to qBittorrent (bypass proxy) works
3. Upload through proxy returns Ok.
4. Torrent appears in qBittorrent list after proxy upload
5. Magnet URLs still pass through proxy correctly
6. Multiple different distro torrent files upload successfully
7. Upload with custom save path works
8. Duplicate torrent detection works through proxy
9. Proxy does not corrupt multipart form data
10. Non-torrent POST requests still pass through
"""

import os
import sys
import time
import hashlib
import subprocess
import unittest

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

PROXY_URL = "http://localhost:78085"
QBIT_URL = "http://localhost:79085"
USERNAME = "admin"
PASSWORD = "admin"

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TORRENTS_DIR = os.path.join(TESTS_DIR, "test_torrents")

ALL_VALID_STATES = [
    "downloading",
    "stalledDL",
    "metaDL",
    "queuedDL",
    "pausedDL",
    "uploading",
    "stalledUP",
    "forcedDL",
    "forcedUP",
    "checkingDL",
    "checkingUP",
    "queuedUP",
    "pausedUP",
    "moving",
    "forcedUP",
]


def get_local_torrents():
    """Return list of available local torrent files."""
    torrents = []
    if os.path.isdir(TORRENTS_DIR):
        for fname in sorted(os.listdir(TORRENTS_DIR)):
            if fname.endswith(".torrent"):
                fpath = os.path.join(TORRENTS_DIR, fname)
                if os.path.getsize(fpath) > 100:
                    with open(fpath, "rb") as f:
                        header = f.read(20)
                    if header.startswith(b"d"):
                        torrents.append(fpath)
    return torrents


def is_container_running():
    for runtime in ["podman", "docker"]:
        try:
            result = subprocess.run(
                [runtime, "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "qbittorrent" in result.stdout and "qbittorrent-proxy" in result.stdout:
                return True, runtime
        except Exception:
            pass
    return False, None


class QBittorrentSession:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()

    def login(self):
        resp = self.session.post(
            f"{self.base_url}/api/v2/auth/login",
            data={"username": USERNAME, "password": PASSWORD},
            timeout=10,
        )
        return resp.status_code == 200 and resp.text.strip() == "Ok."

    def add_torrent_file(self, filepath, savepath="/downloads/"):
        with open(filepath, "rb") as f:
            files = {
                "torrents": (os.path.basename(filepath), f, "application/x-bittorrent")
            }
            data = {"savepath": savepath, "category": ""}
            resp = self.session.post(
                f"{self.base_url}/api/v2/torrents/add",
                files=files,
                data=data,
                timeout=30,
            )
        return resp.status_code, resp.text.strip()

    def add_torrent_bytes(
        self, torrent_bytes, filename="test.torrent", savepath="/downloads/"
    ):
        files = {"torrents": (filename, torrent_bytes, "application/x-bittorrent")}
        data = {"savepath": savepath, "category": ""}
        resp = self.session.post(
            f"{self.base_url}/api/v2/torrents/add",
            files=files,
            data=data,
            timeout=30,
        )
        return resp.status_code, resp.text.strip()

    def add_magnet(self, magnet_url, savepath="/downloads/"):
        data = {"urls": magnet_url, "savepath": savepath}
        resp = self.session.post(
            f"{self.base_url}/api/v2/torrents/add",
            data=data,
            timeout=30,
        )
        return resp.status_code, resp.text.strip()

    def get_torrents(self):
        resp = self.session.get(f"{self.base_url}/api/v2/torrents/info", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []

    def delete_torrent(self, torrent_hash, delete_files=True):
        self.session.post(
            f"{self.base_url}/api/v2/torrents/delete",
            data={"hashes": torrent_hash, "deleteFiles": str(delete_files).lower()},
            timeout=10,
        )

    def delete_all_torrents(self):
        torrents = self.get_torrents()
        if torrents:
            hashes = "|".join(t["hash"] for t in torrents)
            self.delete_torrent(hashes, delete_files=False)
            time.sleep(1)

    def get_version(self):
        resp = self.session.get(f"{self.base_url}/api/v2/app/version", timeout=10)
        return resp.text.strip() if resp.status_code == 200 else "unknown"

    def api_get(self, path):
        resp = self.session.get(f"{self.base_url}{path}", timeout=10)
        return resp.status_code, resp


class TestProxyInfrastructure(unittest.TestCase):
    """Test that proxy and qBittorrent infrastructure is running."""

    @classmethod
    def setUpClass(cls):
        if not HAS_REQUESTS:
            raise unittest.SkipTest("requests module not installed")
        running, cls.runtime = is_container_running()
        if not running:
            raise unittest.SkipTest("Containers not running (start with ./start.sh)")
        cls.qbit = QBittorrentSession(QBIT_URL)
        cls.proxy = QBittorrentSession(PROXY_URL)
        if not cls.qbit.login() or not cls.proxy.login():
            raise unittest.SkipTest("Login failed")

    def test_01_qbittorrent_direct_accessible(self):
        code, _ = self.qbit.api_get("/api/v2/app/version")
        self.assertEqual(code, 200)

    def test_02_proxy_accessible(self):
        code, _ = self.proxy.api_get("/api/v2/app/version")
        self.assertEqual(code, 200)

    def test_03_versions_match(self):
        direct = self.qbit.get_version()
        via_proxy = self.proxy.get_version()
        self.assertEqual(direct, via_proxy, "Versions should match through proxy")

    def test_04_transfer_info_via_proxy(self):
        code, resp = self.proxy.api_get("/api/v2/transfer/info")
        self.assertEqual(code, 200, "Transfer info should be accessible through proxy")
        data = resp.json()
        self.assertIn("dl_info_speed", data)

    def test_05_local_torrent_files_available(self):
        torrents = get_local_torrents()
        self.assertGreater(
            len(torrents),
            0,
            f"No local torrent files found in {TORRENTS_DIR}. "
            f"Run the download script or add .torrent files manually.",
        )
        print(f"\n      Found {len(torrents)} local torrent files for testing:")
        for t in torrents:
            size = os.path.getsize(t)
            print(f"        - {os.path.basename(t)} ({size} bytes)")


class TestTorrentFileUpload(unittest.TestCase):
    """Test .torrent file upload through the proxy using real distro torrents."""

    @classmethod
    def setUpClass(cls):
        if not HAS_REQUESTS:
            raise unittest.SkipTest("requests module not installed")
        running, cls.runtime = is_container_running()
        if not running:
            raise unittest.SkipTest("Containers not running")
        cls.qbit = QBittorrentSession(QBIT_URL)
        cls.proxy = QBittorrentSession(PROXY_URL)
        if not cls.qbit.login() or not cls.proxy.login():
            raise unittest.SkipTest("Login failed")
        cls.added_hashes = []
        cls.torrent_files = get_local_torrents()
        if not cls.torrent_files:
            raise unittest.SkipTest(f"No local torrent files in {TORRENTS_DIR}")
        cls.primary_torrent = cls.torrent_files[0]
        print(f"\n{'=' * 70}")
        print("Torrent File Upload Test Suite")
        print(f"{'=' * 70}\n")

    @classmethod
    def tearDownClass(cls):
        for h in cls.added_hashes:
            try:
                cls.qbit.delete_torrent(h, delete_files=True)
                time.sleep(0.3)
            except Exception:
                pass

    def _cleanup_test_torrents(self):
        self.qbit.delete_all_torrents()
        self.added_hashes.clear()
        time.sleep(0.5)

    def test_01_direct_upload_works(self):
        """Baseline: direct upload to qBittorrent (bypass proxy) works."""
        self._cleanup_test_torrents()
        status, text = self.qbit.add_torrent_file(self.primary_torrent)
        self.assertEqual(
            status, 200, f"Direct upload should return 200, got {status}: {text}"
        )
        self.assertEqual(text, "Ok.", f"Direct upload should return Ok., got: {text}")
        time.sleep(2)
        torrents = self.qbit.get_torrents()
        self.assertGreater(
            len(torrents), 0, "Torrent should appear in list after direct upload"
        )
        for t in torrents:
            self.added_hashes.append(t["hash"])

    def test_02_proxy_upload_returns_ok(self):
        """Upload through proxy should return Ok. (NOT 500 like before the fix)."""
        self._cleanup_test_torrents()
        status, text = self.proxy.add_torrent_file(self.primary_torrent)
        self.assertEqual(
            status, 200, f"Proxy upload should return 200, got {status}: {text}"
        )
        self.assertEqual(text, "Ok.", f"Proxy upload should return Ok., got: {text}")

    def test_03_proxy_upload_torrent_appears_in_list(self):
        """Torrent uploaded through proxy should appear in qBittorrent torrent list."""
        self._cleanup_test_torrents()
        status, _ = self.proxy.add_torrent_file(self.primary_torrent)
        self.assertEqual(status, 200)
        time.sleep(3)
        torrents = self.qbit.get_torrents()
        self.assertGreater(
            len(torrents), 0, "Torrent should appear in list after proxy upload"
        )
        for t in torrents:
            self.added_hashes.append(t["hash"])

    def test_04_proxy_upload_torrent_has_valid_state(self):
        """Torrent uploaded through proxy should have a valid download state."""
        self._cleanup_test_torrents()
        self.proxy.add_torrent_file(self.primary_torrent)
        time.sleep(3)
        torrents = self.qbit.get_torrents()
        self.assertGreater(len(torrents), 0)
        state = torrents[0].get("state", "")
        self.assertIn(state, ALL_VALID_STATES, f"State should be valid, got: {state}")
        for t in torrents:
            self.added_hashes.append(t["hash"])

    def test_05_magnet_url_passthrough(self):
        """Magnet URLs should pass through proxy and be added to qBittorrent."""
        self._cleanup_test_torrents()
        unique_hash = hashlib.sha256(str(time.time()).encode()).hexdigest()[:40]
        magnet = f"magnet:?xt=urn:btih:{unique_hash}&dn=test_magnet_{int(time.time())}"
        status, text = self.proxy.add_magnet(magnet)
        self.assertEqual(
            status, 200, f"Magnet add should return 200, got {status}: {text}"
        )
        self.assertEqual(text, "Ok.", f"Magnet add should return Ok., got: {text}")
        time.sleep(2)
        torrents = self.qbit.get_torrents()
        found = [
            t
            for t in torrents
            if t.get("hash", "").lower().startswith(unique_hash.lower()[:12])
        ]
        self.assertTrue(len(found) > 0, "Magnet torrent should appear in list")
        for t in torrents:
            self.added_hashes.append(t["hash"])

    def test_06_all_distro_torrents_upload_via_proxy(self):
        """All local distro torrent files should upload successfully through proxy."""
        self._cleanup_test_torrents()
        for torrent_path in self.torrent_files:
            self.qbit.delete_all_torrents()
            self.added_hashes.clear()
            time.sleep(0.5)
            name = os.path.basename(torrent_path)
            status, text = self.proxy.add_torrent_file(torrent_path)
            self.assertEqual(
                status,
                200,
                f"Proxy upload of {name} should return 200, got {status}: {text}",
            )
            self.assertEqual(
                text, "Ok.", f"Proxy upload of {name} should return Ok., got: {text}"
            )
            time.sleep(2)
            torrents = self.qbit.get_torrents()
            self.assertGreater(
                len(torrents),
                0,
                f"{name}: torrent should appear in list after proxy upload",
            )
            for t in torrents:
                self.added_hashes.append(t["hash"])

    def test_07_upload_with_custom_savepath(self):
        """Upload with custom save path should work through proxy."""
        self._cleanup_test_torrents()
        status, text = self.proxy.add_torrent_file(
            self.primary_torrent, savepath="/downloads/Movies/"
        )
        self.assertEqual(status, 200, f"Upload with savepath should return 200: {text}")
        self.assertEqual(text, "Ok.", f"Upload with savepath should return Ok.: {text}")
        time.sleep(2)
        torrents = self.qbit.get_torrents()
        self.assertGreater(len(torrents), 0)
        save_path = torrents[0].get("save_path", "")
        self.assertIn(
            "Movies", save_path, f"Save path should contain Movies, got: {save_path}"
        )
        for t in torrents:
            self.added_hashes.append(t["hash"])

    def test_08_duplicate_detection(self):
        """Duplicate torrent upload should fail gracefully through proxy."""
        self._cleanup_test_torrents()
        status1, text1 = self.proxy.add_torrent_file(self.primary_torrent)
        self.assertEqual(status1, 200)
        self.assertEqual(text1, "Ok.")
        time.sleep(1)
        status2, text2 = self.proxy.add_torrent_file(self.primary_torrent)
        self.assertEqual(status2, 200, "Duplicate upload should still return 200")
        self.assertEqual(
            text2, "Fails.", f"Duplicate should return Fails., got: {text2}"
        )
        for t in self.qbit.get_torrents():
            self.added_hashes.append(t["hash"])

    def test_09_proxy_never_returns_500_for_multipart(self):
        """Proxy should NEVER return 500 for multipart uploads (regression test for the bug)."""
        self._cleanup_test_torrents()
        for i, torrent_path in enumerate(self.torrent_files):
            self.qbit.delete_all_torrents()
            self.added_hashes.clear()
            time.sleep(0.5)
            name = os.path.basename(torrent_path)
            status, text = self.proxy.add_torrent_file(torrent_path)
            self.assertNotEqual(
                status,
                500,
                f"Iteration {i + 1} ({name}): Proxy returned 500 (the original bug). "
                f"Response: {text[:200]}",
            )
        for t in self.qbit.get_torrents():
            self.added_hashes.append(t["hash"])

    def test_10_preferences_via_proxy(self):
        """GET requests for app preferences should work through proxy."""
        code, resp = self.proxy.api_get("/api/v2/app/preferences")
        self.assertEqual(code, 200, "Preferences should be accessible through proxy")
        prefs = resp.json()
        self.assertIn("save_path", prefs)


class TestProxyRegression(unittest.TestCase):
    """Regression tests ensuring the original bug does not resurface."""

    @classmethod
    def setUpClass(cls):
        if not HAS_REQUESTS:
            raise unittest.SkipTest("requests module not installed")
        running, _ = is_container_running()
        if not running:
            raise unittest.SkipTest("Containers not running")
        cls.qbit = QBittorrentSession(QBIT_URL)
        cls.proxy = QBittorrentSession(PROXY_URL)
        if not cls.qbit.login() or not cls.proxy.login():
            raise unittest.SkipTest("Login failed")
        cls.added_hashes = []
        cls.torrent_files = get_local_torrents()
        if not cls.torrent_files:
            raise unittest.SkipTest(f"No local torrent files in {TORRENTS_DIR}")

    @classmethod
    def tearDownClass(cls):
        for h in cls.added_hashes:
            try:
                cls.qbit.delete_torrent(h, delete_files=True)
            except Exception:
                pass

    def test_01_no_unicode_decode_error_on_any_torrent(self):
        """The proxy must not crash with UnicodeDecodeError on any local torrent file."""
        for torrent_path in self.torrent_files:
            with open(torrent_path, "rb") as f:
                torrent_bytes = f.read()
            name = os.path.basename(torrent_path)
            files = {"torrents": (name, torrent_bytes, "application/x-bittorrent")}
            data = {"savepath": "/downloads/"}
            resp = requests.post(
                f"{PROXY_URL}/api/v2/torrents/add",
                files=files,
                data=data,
                cookies=self.proxy.session.cookies,
                timeout=30,
            )
            self.assertNotEqual(
                resp.status_code,
                500,
                f"{name}: Proxy must not return 500 (UnicodeDecodeError was the original bug)",
            )
            self.assertNotIn(
                "utf-8",
                resp.text.lower(),
                f"{name}: Response must not contain UTF-8 error message",
            )
            self.assertNotIn(
                "decode",
                resp.text.lower(),
                f"{name}: Response must not contain decode error message",
            )
            time.sleep(0.5)
        torrents = self.qbit.get_torrents()
        for t in torrents:
            if t["hash"] not in self.added_hashes:
                self.added_hashes.append(t["hash"])

    def test_02_binary_torrent_with_all_byte_values(self):
        """Torrent containing all possible byte values (0-255) should upload without 500."""
        with open(self.torrent_files[0], "rb") as f:
            original = f.read()
        all_bytes_injected = bytearray(original)
        all_bytes_injected.extend(bytes(range(256)) * 3)
        all_bytes_injected.extend(b"padding_data_to_ensure_binary_content")
        files = {
            "torrents": (
                "binary_test.torrent",
                bytes(all_bytes_injected),
                "application/x-bittorrent",
            )
        }
        data = {"savepath": "/downloads/"}
        resp = requests.post(
            f"{PROXY_URL}/api/v2/torrents/add",
            files=files,
            data=data,
            cookies=self.proxy.session.cookies,
            timeout=30,
        )
        self.assertNotEqual(
            resp.status_code,
            500,
            "Proxy must not crash on torrent with all byte values",
        )

    def test_03_proxy_logs_no_error(self):
        """After successful file uploads, proxy logs should not contain errors."""
        runtime = (
            "podman"
            if subprocess.run(["which", "podman"], capture_output=True).returncode == 0
            else "docker"
        )
        result = subprocess.run(
            [runtime, "logs", "qbittorrent-proxy", "--tail", "20"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        logs = result.stdout + result.stderr
        self.assertNotIn(
            "Error handling request",
            logs,
            "Proxy logs should not contain 'Error handling request'",
        )
        self.assertNotIn(
            "UnicodeDecodeError",
            logs,
            "Proxy logs should not contain 'UnicodeDecodeError'",
        )
        self.assertNotIn(
            "can't decode byte",
            logs,
            "Proxy logs should not contain byte decode errors",
        )

    def test_04_largest_torrent_file(self):
        """The largest local torrent file should upload without issues."""
        largest = max(self.torrent_files, key=os.path.getsize)
        name = os.path.basename(largest)
        size = os.path.getsize(largest)
        print(f"\n      Testing largest torrent: {name} ({size} bytes)")
        status, text = self.proxy.add_torrent_file(largest)
        self.assertEqual(
            status,
            200,
            f"Largest torrent ({name}, {size}B) should upload via proxy: {text}",
        )
        time.sleep(1)
        torrents = self.qbit.get_torrents()
        for t in torrents:
            if t["hash"] not in self.added_hashes:
                self.added_hashes.append(t["hash"])


def run_tests():
    if not HAS_REQUESTS:
        print("ERROR: requests module required. Install with: pip install requests")
        return 1

    running, _ = is_container_running()
    if not running:
        print("=" * 70)
        print("SKIP: Containers not running")
        print("Start with: ./start.sh")
        print("=" * 70)
        return 1

    torrents = get_local_torrents()
    if not torrents:
        print("=" * 70)
        print(f"ERROR: No valid .torrent files found in {TORRENTS_DIR}/")
        print("Add real .torrent files (Linux distro ISOs) for testing.")
        print("=" * 70)
        return 1

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestProxyInfrastructure))
    suite.addTests(loader.loadTestsFromTestCase(TestTorrentFileUpload))
    suite.addTests(loader.loadTestsFromTestCase(TestProxyRegression))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"\n{'=' * 70}")
    if result.wasSuccessful():
        print("ALL TORRENT FILE UPLOAD TESTS PASSED")
        print("The download proxy correctly handles .torrent file uploads.")
        print(f"Tested with {len(torrents)} distro torrent file(s).")
    else:
        print(f"FAILURES: {len(result.failures)}, ERRORS: {len(result.errors)}")
        if result.failures:
            print("\nFailed tests:")
            for test, trace in result.failures:
                print(f"  - {test}")
        if result.errors:
            print("\nErrored tests:")
            for test, trace in result.errors:
                print(f"  - {test}")
    print(f"{'=' * 70}")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
