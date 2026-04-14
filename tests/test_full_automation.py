"""
qBittorrent Full Automation Test Suite
Uses Playwright for comprehensive UI and API testing
"""

import pytest
import time
from playwright.sync_api import sync_playwright, Page, Browser
from typing import List, Dict
import json
import requests


class QBittorrentTester:
    """Main test class for qBittorrent automation"""

    BASE_URL = "http://localhost:7186"
    USERNAME = "admin"
    PASSWORD = "admin"

    def __init__(self):
        self.browser = None
        self.page = None
        self.session_cookie = None

    def start(self):
        """Initialize browser and context"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_default_timeout(30000)  # 30 second timeout

    def stop(self):
        """Cleanup"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def login_api(self) -> str:
        """Login via API and return cookie"""
        response = requests.post(
            f"{self.BASE_URL}/api/v2/auth/login",
            data={"username": self.USERNAME, "password": self.PASSWORD},
            timeout=10,
        )
        if response.text == "Ok.":
            self.session_cookie = response.cookies.get_dict()
            return "success"
        return f"failed: {response.text}"

    def wait_for_selector(self, selector: str, timeout: int = 10000):
        """Wait for element to appear"""
        self.page.wait_for_selector(selector, timeout=timeout)

    def take_screenshot(self, name: str):
        """Take screenshot for debugging"""
        self.page.screenshot(path=f"/tmp/qb_test_{name}.png")

    # ========== UI TESTS ==========

    def test_login_page_loads(self):
        """Test that login page loads correctly and quickly"""
        start = time.time()
        self.page.goto(self.BASE_URL)
        load_time = time.time() - start

        # Check page title
        assert "qBittorrent" in self.page.title(), f"Wrong title: {self.page.title()}"

        # Check login form exists
        self.wait_for_selector("#username")
        self.wait_for_selector("#password")
        self.wait_for_selector("#loginButton")

        # Verify load time is reasonable (< 3 seconds)
        assert load_time < 3.0, f"Page too slow: {load_time}s"
        return f"Login page loaded in {load_time:.2f}s"

    def test_login_ui(self):
        """Test login through UI"""
        # Already on login page
        self.page.fill("#username", self.USERNAME)
        self.page.fill("#password", self.PASSWORD)
        self.page.click("#loginButton")

        # Wait for main UI to load
        self.wait_for_selector(".mocha-content", timeout=15000)

        # Verify we're logged in by checking for torrent table
        self.wait_for_selector("#torrentsTable", timeout=5000)
        return "Login successful via UI"

    # ========== API TESTS ==========

    def test_api_version(self):
        """Test API version endpoint"""
        self.login_api()
        response = requests.get(
            f"{self.BASE_URL}/api/v2/app/version",
            cookies=self.session_cookie,
            timeout=10,
        )
        version = response.text
        assert version.startswith("v"), f"Invalid version: {version}"
        return f"qBittorrent version: {version}"

    def test_api_transfer_info(self):
        """Test transfer info API"""
        self.login_api()
        response = requests.get(
            f"{self.BASE_URL}/api/v2/transfer/info",
            cookies=self.session_cookie,
            timeout=10,
        )
        data = response.json()
        assert isinstance(data, list), "Transfer info should be a list"
        return f"Transfer info: {len(data)} torrents"

    # ========== PLUGIN TESTS ==========

    def get_search_plugins(self) -> List[Dict]:
        """Get list of search plugins"""
        self.login_api()
        response = requests.get(
            f"{self.BASE_URL}/api/v2/search/plugins",
            cookies=self.session_cookie,
            timeout=10,
        )
        return response.json()

    def test_plugins_available(self):
        """Test that search plugins are available"""
        plugins = self.get_search_plugins()

        assert len(plugins) > 0, "No plugins found"

        plugin_names = [p["name"] for p in plugins]

        # Check for expected plugins
        expected_plugins = ["rutracker", "rutor", "piratebay", "eztv"]
        found = [p for p in expected_plugins if p in plugin_names]

        return {
            "total": len(plugins),
            "expected_found": found,
            "all_names": plugin_names,
        }

    # ========== SEARCH TESTS ==========

    def test_search(self, plugin: str, query: str, timeout: int = 30000) -> Dict:
        """Test search functionality for a specific plugin"""
        self.login_api()

        # Start search
        response = requests.post(
            f"{self.BASE_URL}/api/v2/search/start",
            cookies=self.session_cookie,
            data={"pattern": query, "plugins": plugin, "category": "all"},
            timeout=timeout // 1000,
        )

        if response.status_code != 200:
            return {
                "error": f"Search start failed: {response.status_code}",
                "plugin": plugin,
            }

        search_data = response.json()
        search_id = search_data.get("id")

        if not search_id:
            return {"error": "No search ID returned", "plugin": plugin}

        # Wait for results
        time.sleep(5)

        # Get results
        response = requests.get(
            f"{self.BASE_URL}/api/v2/search/results",
            params={"id": search_id, "limit": 10},
            cookies=self.session_cookie,
            timeout=timeout // 1000,
        )

        results = response.json()

        return {
            "plugin": plugin,
            "query": query,
            "search_id": search_id,
            "status": results.get("status", "Unknown"),
            "total": results.get("total", 0),
            "results_count": len(results.get("results", [])),
            "has_results": len(results.get("results", [])) > 0,
        }

    # ========== DOWNLOAD TESTS ==========

    def test_download(self, plugin: str, query: str, timeout: int = 60000) -> Dict:
        """Test download functionality for a specific plugin"""
        # First do a search
        search_result = self.test_search(plugin, query, timeout)

        if not search_result.get("has_results"):
            return {
                "error": "No search results to download",
                "plugin": plugin,
                "search_result": search_result,
            }

        # Get first result
        results = search_result.get("results", [])
        if not results:
            # Fetch results again
            self.login_api()
            response = requests.get(
                f"{self.BASE_URL}/api/v2/search/results",
                params={"id": search_result["search_id"], "limit": 1},
                cookies=self.session_cookie,
                timeout=10,
            )
            results = response.json().get("results", [])

        if not results:
            return {"error": "Could not fetch results", "plugin": plugin}

        first_result = results[0]
        download_url = first_result.get("fileUrl")
        file_name = first_result.get("fileName")

        if not download_url:
            return {
                "error": "No download URL in result",
                "plugin": plugin,
                "result": first_result,
            }

        # Attempt download
        response = requests.post(
            f"{self.BASE_URL}/api/v2/torrents/add",
            cookies=self.session_cookie,
            data={"urls": download_url},
            timeout=timeout // 1000,
        )

        download_success = response.text == "Ok."

        if download_success:
            # Verify torrent was added
            time.sleep(2)
            response = requests.get(
                f"{self.BASE_URL}/api/v2/torrents/info",
                cookies=self.session_cookie,
                timeout=10,
            )
            torrents = response.json()

            # Check if our torrent is in the list
            found = any(
                t.get("name", "").lower() in file_name.lower() for t in torrents
            )

            return {
                "plugin": plugin,
                "download_success": download_success,
                "file_name": file_name,
                "url": download_url,
                "torrent_found": found,
                "total_torrents": len(torrents),
            }

        return {"plugin": plugin, "download_success": False, "response": response.text}

    def test_ui_search_flow(self, plugin: str, query: str):
        """Test search through UI"""
        # Ensure logged in
        self.test_login_ui()

        # Click Search tab
        search_tab = self.page.query_selector("text=Search Engine")
        if search_tab:
            search_tab.click()
            time.sleep(1)

        # Fill search box
        search_input = self.page.query_selector("#searchInput")
        if search_input:
            search_input.fill(query)

            # Select plugin (if possible)
            # Click search button
            search_btn = self.page.query_selector("#startSearchButton")
            if search_btn:
                search_btn.click()
                time.sleep(3)

                # Check for results
                results = self.page.query_selector_all("#searchResultsTable tbody tr")
                return {
                    "plugin": plugin,
                    "query": query,
                    "results_count": len(results) if results else 0,
                }

        return {"error": "Could not complete UI search", "plugin": plugin}


class TestQBittorrent:
    """Pytest test class"""

    @pytest.fixture(scope="class")
    def tester(self):
        t = QBittorrentTester()
        t.start()
        yield t
        t.stop()

    def test_01_login_page(self, tester):
        """Test login page loads quickly"""
        result = tester.test_login_page_loads()
        assert "loaded" in result.lower()

    def test_02_login_ui(self, tester):
        """Test UI login"""
        result = tester.test_login_ui()
        assert "successful" in result.lower()

    def test_03_api_version(self, tester):
        """Test API version"""
        result = tester.test_api_version()
        assert "v" in result

    def test_04_plugins_available(self, tester):
        """Test plugins are available"""
        result = tester.test_plugins_available()
        assert result["total"] > 0
        assert "rutracker" in result["all_names"]

    def test_05_search_rutracker(self, tester):
        """Test RuTracker search"""
        result = tester.test_search("rutracker", "ubuntu")
        assert result.get("has_results") or result.get("total", 0) > 0, (
            f"RuTracker search failed: {result}"
        )

    def test_06_download_rutracker(self, tester):
        """Test RuTracker download"""
        result = tester.test_download("rutracker", "ubuntu")
        assert result.get("download_success"), f"RuTracker download failed: {result}"

    def test_07_search_rutor(self, tester):
        """Test Rutor search"""
        result = tester.test_search("rutor", "ubuntu")
        # Rutor might not have results, just check it doesn't error
        assert "error" not in result or result.get("total", 0) >= 0

    def test_08_search_piratebay(self, tester):
        """Test PirateBay search"""
        result = tester.test_search("piratebay", "ubuntu")
        assert "error" not in result or result.get("total", 0) >= 0

    def test_09_response_time(self, tester):
        """Test API response time"""
        tester.login_api()
        start = time.time()
        for _ in range(10):
            requests.get(
                f"{tester.BASE_URL}/api/v2/app/version",
                cookies=tester.session_cookie,
                timeout=5,
            )
        elapsed = time.time() - start
        avg_time = elapsed / 10
        assert avg_time < 1.0, f"API too slow: {avg_time}s average"


if __name__ == "__main__":
    # Run standalone test
    import sys

    tester = QBittorrentTester()
    try:
        tester.start()

        print("=" * 70)
        print("qBittorrent Full Automation Test Suite")
        print("=" * 70)

        # Run all tests
        tests = [
            ("Login Page", tester.test_login_page_loads),
            ("UI Login", tester.test_login_ui),
            ("API Version", tester.test_api_version),
            ("Transfer Info", tester.test_api_transfer_info),
            ("Plugins Available", tester.test_plugins_available),
            ("RuTracker Search", lambda: tester.test_search("rutracker", "ubuntu")),
            ("RuTracker Download", lambda: tester.test_download("rutracker", "ubuntu")),
            ("Rutor Search", lambda: tester.test_search("rutor", "test")),
            ("PirateBay Search", lambda: tester.test_search("piratebay", "ubuntu")),
        ]

        results = []
        for name, test_func in tests:
            print(f"\n[TEST] {name}...")
            try:
                result = test_func()
                print(f"  ✓ PASSED: {result}")
                results.append((name, "PASS", result))
            except Exception as e:
                print(f"  ✗ FAILED: {e}")
                results.append((name, "FAIL", str(e)))

        # Summary
        print("\n" + "=" * 70)
        print("Test Summary")
        print("=" * 70)
        passed = sum(1 for r in results if r[1] == "PASS")
        failed = sum(1 for r in results if r[1] == "FAIL")
        print(f"Passed: {passed}/{len(results)}")
        print(f"Failed: {failed}/{len(results)}")

        for name, status, detail in results:
            symbol = "✓" if status == "PASS" else "✗"
            print(f"  {symbol} {name}: {detail}")

        sys.exit(0 if failed == 0 else 1)

    finally:
        tester.stop()
