"""
qBittorrent Comprehensive Test Suite
Tests ALL plugins, login, search, and download flows
Uses Playwright for browser automation
"""

import pytest
import time
from playwright.sync_api import sync_playwright, Page, Browser, expect
import json
from typing import List, Dict, Optional
import os
import requests


# Test configuration
BASE_URL = "http://localhost:8085"
USERNAME = "admin"
PASSWORD = "admin"
HEADLESS = True
SCREENSHOT_DIR = "/tmp/qb_test_screenshots"


class QBittorrentTestSuite:
    """Comprehensive test suite for qBittorrent"""

    @pytest.fixture(scope="class")
    def browser_context(page: Page):
        """Provides browser context for tests"""
        page.set_default_timeout(30000)  # 30 seconds
        page.set_viewport_size({"width": 1920, "height": 1080})
        yield page

    def login_api(self) -> str:
        """Login via API and return session cookie"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/v2/auth/login",
            data={"username": USERNAME, "password": PASSWORD},
            timeout=10,
        )
        assert response.text == "Ok.", f"Login failed: {response.text}"
        return session.cookies.get_dict()

    # ========== LOGIN PAGE TESTS ==========

    def test_01_login_page_loads(self, page: Page):
        """Test login page loads correctly and quickly"""
        start_time = time.time()
        page.goto(BASE_URL, wait_until="networkidle")
        load_time = time.time() - start_time

        # Verify page loaded
        expect(page.title()).to_cont("qBittorrent")

        # Check login form elements exist
        username_input = page.query("#username")
        password_input = page.query("#password")
        login_button = page.query("#loginButton")

        assert username_input.is_visible()
        assert password_input.is_visible()
        assert login_button.is_visible()

        # Verify reasonable load time
        assert load_time < 5.0, f"Page too slow: {load_time:.2f}s"

        # Take screenshot
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        page.screenshot(path=f"{SCREENSHOT_DIR}/01_login_page.png")

    def test_02_login_page_visual_elements(self, page: Page):
        """Test login page visual elements are correct"""
        page.goto(BASE_URL)

        # Check logo exists and is visible
        logo = page.query("img.logo")
        assert logo.is_visible()

        # Check form layout
        form = page.query("form")
        assert form.is_visible()

        # Check labels
        labels = page.query_all("label")
        assert len(labels) >= 2  # At least username and password labels

        page.screenshot(path=f"{SCREENSHOT_DIR}/02_login_visual.png")

    def test_03_login_flow(self, page: Page):
        """Test successful login flow"""
        page.goto(BASE_URL)

        # Fill login form
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)

        # Click login
        page.click("#loginButton")

        # Wait for main UI to load
        page.wait_for_selector(".mocha-content", timeout=15000)

        # Verify logged in by checking for main elements
        page.wait_for_selector("#torrentsTable", timeout=5000)

        # Check toolbar exists
        toolbar = page.query("#desktopToolbar")
        assert toolbar.is_visible()

        page.screenshot(path=f"{SCREENSHOT_DIR}/03_logged_in.png")

    # ========== PLUGIN TESTS ==========

    def test_04_plugins_available(self, page: Page):
        """Test that search plugins are available"""
        # Login first
        self.login_api()

        # Go to search tab
        page.click("button:has-text('Search')")
        page.wait_for_selector("#searchTab", timeout=5000)

        # Click on plugins tab
        page.click("#searchPluginsButton")
        page.wait_for_selector("#searchPluginsTable", timeout=5000)

        # Check for plugin rows
        plugins = page.query_all("#searchPluginsTable tbody tr")
        plugin_count = len(plugins)

        assert plugin_count > 0, "No plugins found"
        print(f"Found {plugin_count} plugins")

        page.screenshot(path=f"{SCREENSHOT_DIR}/04_plugins.png")

    def test_05_rutracker_plugin_enabled(self, page: Page):
        """Test RuTracker plugin is enabled"""
        session = self.login_api()

        # Get plugins via API
        response = session.get(f"{BASE_URL}/api/v2/search/plugins")
        plugins = response.json()

        # Find RuTracker
        rutracker = next((p for p in plugins if p.get("name") == "rutracker"), None)
        assert rutracker is not None, "RuTracker plugin not found"
        assert rutracker.get("enabled") == True, "RuTracker not enabled"

    def test_06_all_plugins_status(self, page: Page):
        """Test status of all plugins"""
        session = self.login_api()

        response = session.get(f"{BASE_URL}/api/v2/search/plugins")
        plugins = response.json()

        enabled_count = sum(1 for p in plugins if p.get("enabled"))
        total_count = len(plugins)

        print(f"Plugins: {enabled_count}/{total_count} enabled")

        # List all plugins
        for plugin in plugins:
            status = "✓" if plugin.get("enabled") else "✗"
            print(f"  {status} {plugin.get('name')}: {plugin.get('url')}")

        assert total_count > 0, "No plugins found"
        assert enabled_count > 0, "No enabled plugins"

    # ========== SEARCH TESTS ==========

    def test_07_search_ui_opens(self, page: Page):
        """Test search UI opens correctly"""
        # Login
        page.goto(BASE_URL)
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        page.click("#loginButton")
        page.wait_for_selector(".mocha-content", timeout=15000)

        # Click search tab
        search_button = page.get_by_text("Search", exact=False).first()
        search_button.click()

        # Wait for search panel
        page.wait_for_selector("#searchPattern", timeout=5000)

        # Check search pattern input exists
        pattern_input = page.query("#searchPattern")
        assert pattern_input.is_visible()

        page.screenshot(path=f"{SCREENSHOT_DIR}/07_search_ui.png")

    def test_08_search_rutracker(self, page: Page):
        """Test search with RuTracker plugin"""
        session = self.login_api()

        # Start search via API
        response = session.post(
            f"{BASE_URL}/api/v2/search/start",
            data={"pattern": "ubuntu", "plugins": "rutracker", "category": "all"},
            timeout=15,
        )
        result = response.json()
        search_id = result.get("id")

        assert search_id is not None, "Search failed to start"

        # Wait for results
        time.sleep(5)

        # Get results
        response = session.get(
            f"{BASE_URL}/api/v2/search/results",
            params={"id": search_id, "limit": 5},
            timeout=10,
        )
        results = response.json()

        assert results.get("results"), "No results returned"
        assert len(results["results"]) > 0, "No search results"

        print(f"Found {len(results['results'])} results")

        # Verify result structure
        first_result = results["results"][0]
        assert "fileName" in first_result
        assert "fileUrl" in first_result
        assert "fileSize" in first_result

        print(f"First result: {first_result['fileName']}")

    def test_09_search_multiple_plugins(self, page: Page):
        """Test search with multiple plugins"""
        session = self.login_api()

        # Get first 3 enabled plugins
        response = session.get(f"{BASE_URL}/api/v2/search/plugins")
        plugins = [p["name"] for p in response.json() if p.get("enabled")][:3]

        if len(plugins) < 2:
            pytest.skip("Need at least 2 enabled plugins")

        # Start search
        response = session.post(
            f"{BASE_URL}/api/v2/search/start",
            data={"pattern": "test", "plugins": ",".join(plugins), "category": "all"},
            timeout=15,
        )
        search_id = response.json().get("id")

        assert search_id is not None

        # Wait for results
        time.sleep(5)

        # Get results
        response = session.get(
            f"{BASE_URL}/api/v2/search/results",
            params={"id": search_id, "limit": 10},
            timeout=10,
        )
        results = response.json()

        total_results = results.get("total", 0)
        print(f"Total results from {len(plugins)} plugins: {total_results}")

        assert total_results > 0, "No results found"

    # ========== DOWNLOAD TESTS ==========

    def test_10_download_from_rutracker(self, page: Page):
        """Test downloading torrent from RuTracker"""
        session = self.login_api()

        # Start search
        response = session.post(
            f"{BASE_URL}/api/v2/search/start",
            data={"pattern": "ubuntu", "plugins": "rutracker", "category": "all"},
            timeout=15,
        )
        search_id = response.json().get("id")

        # Wait for results
        time.sleep(5)

        # Get first result
        response = session.get(
            f"{BASE_URL}/api/v2/search/results",
            params={"id": search_id, "limit": 1},
            timeout=10,
        )
        results = response.json()

        if not results.get("results"):
            pytest.skip("No search results to test download")

        download_url = results["results"][0]["fileUrl"]
        file_name = results["results"][0]["fileName"]

        print(f"Downloading: {file_name}")

        # Add torrent via API
        response = session.post(
            f"{BASE_URL}/api/v2/torrents/add", data={"urls": download_url}, timeout=15
        )

        assert response.text == "Ok.", f"Add failed: {response.text}"
        print("Torrent added successfully")

        # Wait a moment
        time.sleep(2)

        # Verify torrent is in list
        response = session.get(f"{BASE_URL}/api/v2/torrents/info", timeout=10)
        torrents = response.json()

        # Find our torrent
        found = any(t for t in torrents if "ubuntu" in t["name"].lower())
        assert found, "Torrent not found in list"
        print(f"Verified torrent in list: {found['name']}")

    def test_11_download_ui(self, page: Page):
        """Test download through UI"""
        # Login via UI
        page.goto(BASE_URL)
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        page.click("#loginButton")
        page.wait_for_selector(".mocha-content", timeout=15000)

        # Go to search tab
        search_tab = page.get_by_text("Search").first()
        search_tab.click()
        page.wait_for_selector("#searchPattern", timeout=5000)

        # Enter search term
        page.fill("#searchPattern", "ubuntu")

        # Select RuTracker in plugin dropdown if needed
        # Click search button
        search_btn = page.query("#searchStartButton")
        search_btn.click()

        # Wait for results
        page.wait_for_selector(".searchTableRow", timeout=15000)

        # Get first result and click download
        first_result = page.query(".searchTableRow")
        download_link = first_result.query("a")

        if download_link:
            download_link.click()

            # Wait for add to happen
            time.sleep(2)

        page.screenshot(path=f"{SCREENSHOT_DIR}/11_download_ui.png")

    # ========== PERFORMANCE TESTS ==========

    def test_12_response_time_login(self, page: Page):
        """Test login page response time"""
        times = []
        for i in range(3):
            start = time.time()
            page.goto(BASE_URL)
            page.wait_for_selector("#loginButton")
            times.append(time.time() - start)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        print(f"Login page load times: {times}")
        print(f"Average: {avg_time:.2f}s, Max: {max_time:.2f}s")

        assert max_time < 5.0, f"Too slow: {max_time:.2f}s"

    def test_13_response_time_api(self, page: Page):
        """Test API response times"""
        session = self.login_api()

        endpoints = [
            "/api/v2/app/version",
            "/api/v2/transfer/info",
            "/api/v2/torrents/info",
        ]

        for endpoint in endpoints:
            start = time.time()
            response = session.get(f"{BASE_URL}{endpoint}", timeout=10)
            elapsed = time.time() - start
            print(f"{endpoint}: {elapsed:.3f}s")
            assert response.status_code == 200
            assert elapsed < 2.0, f"API too slow: {endpoint}"

    # ========== CLEANUP ==========

    def test_99_cleanup(self, page: Page):
        """Cleanup - stop any running searches"""
        session = self.login_api()

        # Stop all searches
        session.post(f"{BASE_URL}/api/v2/search/stop", timeout=10)

        # Clean up test screenshots
        if os.path.exists(SCREENSHOT_DIR):
            print(f"Screenshots saved to: {SCREENSHOT_DIR}")
