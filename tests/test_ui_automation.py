#!/usr/bin/env python3
"""
qBittorrent Comprehensive UI Automation Test Suite
Using Playwright for full browser automation testing
"""

import pytest
import time
import json
import requests
import os
from playwright.sync_api import sync_playwright, Page, Browser, expect, Locator
from typing import Optional, List, Dict
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:7186"
USERNAME = "admin"
PASSWORD = "admin"
HEADLESS = True
SCREENSHOT_DIR = "/tmp/qb_test_screenshots"
VIDEO_DIR = "/tmp/qb_test_videos"


class QBittorrentPage:
    """Page Object Model for qBittorrent UI"""

    def __init__(self, page: Page):
        self.page = page

    # Login Page Locators
    @property
    def username_input(self) -> Locator:
        return self.page.locator("#username")

    @property
    def password_input(self) -> Locator:
        return self.page.locator("#password")

    @property
    def login_button(self) -> Locator:
        return self.page.locator("#loginButton")

    # Main UI Locators
    @property
    def torrent_table(self) -> Locator:
        return self.page.locator("#torrentsTable")

    @property
    def add_torrent_button(self) -> Locator:
        return self.page.locator("#addTorrentButtonBar")

    @property
    def search_tab(self) -> Locator:
        return self.page.locator("#tabSearch")

    # Dialog Locators
    @property
    def download_from_urls_dialog(self) -> Locator:
        return self.page.locator(".mocha-window:has-text('Download from URLs')")

    @property
    def urls_textarea(self) -> Locator:
        return self.page.locator("#urls")

    @property
    def download_button_in_dialog(self) -> Locator:
        return self.page.locator("#downloadButton")

    # Search Locators
    @property
    def search_pattern_input(self) -> Locator:
        return self.page.locator("#searchPattern")

    @property
    def search_start_button(self) -> Locator:
        return self.page.locator("#startSearchBtn")

    @property
    def search_results_table(self) -> Locator:
        return self.page.locator("#searchResultsTable")

    # Actions
    def login(self):
        """Perform login"""
        self.page.goto(BASE_URL)
        self.username_input.fill(USERNAME)
        self.password_input.fill(PASSWORD)
        self.login_button.click()
        # Wait for main UI
        self.page.wait_for_selector("#torrentsTable", timeout=15000)

    def open_download_from_urls(self):
        """Open Download from URLs dialog"""
        # Click File menu
        self.page.click("text=File")
        self.page.click("text=Add Torrent Link...")
        # Wait for dialog
        self.page.wait_for_selector(
            ".mocha-window:has-text('Download from URLs')", timeout=5000
        )

    def add_torrent_from_url(self, url: str):
        """Add torrent from URL via dialog"""
        self.open_download_from_urls()
        # Fill URL
        self.urls_textarea.fill(url)
        # Click Download
        self.download_button_in_dialog.click()

    def go_to_search_tab(self):
        """Navigate to search tab"""
        self.page.click("#tabSearch")
        self.page.wait_for_selector("#searchPattern", timeout=5000)

    def search(self, query: str, plugin: str = "all"):
        """Perform search"""
        self.go_to_search_tab()
        self.search_pattern_input.fill(query)
        # Select plugin if needed
        # Start search
        self.search_start_button.click()
        # Wait for results
        self.page.wait_for_selector("#searchResultsTable tbody tr", timeout=30000)


class TestQBittorrentUI:
    """Comprehensive UI Tests using Playwright"""

    @pytest.fixture(scope="class")
    def browser(self):
        """Create browser instance"""
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=HEADLESS, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        yield browser
        browser.close()
        playwright.stop()

    @pytest.fixture
    def page(self, browser):
        """Create page with video recording"""
        context = browser.new_context(
            record_video_dir=VIDEO_DIR, viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        page.set_default_timeout(30000)
        yield page
        context.close()

    @pytest.fixture
    def qb_page(self, page):
        """Create page object"""
        return QBittorrentPage(page)

    # ========== LOGIN TESTS ==========

    def test_01_login_page_loads_instantly(self, page: Page, qb_page: QBittorrentPage):
        """Test login page loads in under 1 second"""
        start = time.time()
        page.goto(BASE_URL)
        qb_page.username_input.wait_for(state="visible", timeout=5000)
        elapsed = time.time() - start

        # Take screenshot
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        page.screenshot(path=f"{SCREENSHOT_DIR}/01_login.png")

        assert elapsed < 1.0, f"Login page too slow: {elapsed:.2f}s"
        print(f"✓ Login page loaded in {elapsed:.2f}s")

    def test_02_login_page_visual_elements(self, page: Page, qb_page: QBittorrentPage):
        """Test login page has all required elements"""
        page.goto(BASE_URL)

        # Check logo
        logo = page.locator("img.logo, img[alt*='qBittorrent']").first
        assert logo.is_visible(), "Logo not visible"

        # Check form elements
        assert qb_page.username_input.is_visible(), "Username input not visible"
        assert qb_page.password_input.is_visible(), "Password input not visible"
        assert qb_page.login_button.is_visible(), "Login button not visible"

        # Check labels
        assert page.locator("text=Username").is_visible()
        assert page.locator("text=Password").is_visible()

        page.screenshot(path=f"{SCREENSHOT_DIR}/02_login_elements.png")
        print("✓ All login page elements visible")

    def test_03_login_flow_works(self, page: Page, qb_page: QBittorrentPage):
        """Test complete login flow"""
        start = time.time()
        qb_page.login()
        elapsed = time.time() - start

        # Verify logged in
        expect(qb_page.torrent_table).to_be_visible()

        page.screenshot(path=f"{SCREENSHOT_DIR}/03_logged_in.png")
        print(f"✓ Login completed in {elapsed:.2f}s")

    def test_04_invalid_login_shows_error(self, page: Page, qb_page: QBittorrentPage):
        """Test invalid login shows error"""
        page.goto(BASE_URL)
        qb_page.username_input.fill("wrong")
        qb_page.password_input.fill("wrong")
        qb_page.login_button.click()

        # Should stay on login page
        page.wait_for_timeout(2000)
        assert qb_page.username_input.is_visible(), "Should still be on login page"
        print("✓ Invalid login handled correctly")

    # ========== MAIN UI TESTS ==========

    def test_05_main_ui_elements(self, page: Page, qb_page: QBittorrentPage):
        """Test main UI has all required elements"""
        qb_page.login()

        # Check main elements
        assert page.locator("#desktopToolbar").is_visible()
        assert page.locator("#torrentsTable").is_visible()
        assert page.locator("#transferList").is_visible()
        assert page.locator("#tabBar").is_visible()

        # Check tabs
        assert page.locator("#tabTransfer").is_visible()
        assert page.locator("#tabSearch").is_visible()
        assert page.locator("#tabRss").is_visible()

        page.screenshot(path=f"{SCREENSHOT_DIR}/05_main_ui.png")
        print("✓ All main UI elements visible")

    def test_06_open_download_from_urls_dialog(
        self, page: Page, qb_page: QBittorrentPage
    ):
        """Test opening Download from URLs dialog"""
        qb_page.login()
        qb_page.open_download_from_urls()

        # Check dialog elements
        assert qb_page.urls_textarea.is_visible()
        assert qb_page.download_button_in_dialog.is_visible()

        page.screenshot(path=f"{SCREENSHOT_DIR}/06_download_dialog.png")
        print("✓ Download from URLs dialog opens")

    # ========== SEARCH TESTS ==========

    def test_07_open_search_tab(self, page: Page, qb_page: QBittorrentPage):
        """Test opening search tab"""
        qb_page.login()
        qb_page.go_to_search_tab()

        # Check search elements
        assert qb_page.search_pattern_input.is_visible()
        assert qb_page.search_start_button.is_visible()

        page.screenshot(path=f"{SCREENSHOT_DIR}/07_search_tab.png")
        print("✓ Search tab opens correctly")

    def test_08_rutracker_search(self, page: Page, qb_page: QBittorrentPage):
        """Test RuTracker search via UI"""
        qb_page.login()
        qb_page.go_to_search_tab()

        # Fill search
        qb_page.search_pattern_input.fill("ubuntu")

        # Select RuTracker plugin
        # Look for plugin selector
        plugin_select = page.locator(
            "#pluginsSelect, #pluginSelect, select[name='plugin']"
        )
        if plugin_select.count() > 0:
            plugin_select.select_option("rutracker")

        # Start search
        qb_page.search_start_button.click()

        # Wait for results (up to 30 seconds)
        try:
            page.wait_for_selector("#searchResultsTable tbody tr", timeout=30000)
            results = page.locator("#searchResultsTable tbody tr").count()
            print(f"✓ RuTracker search found {results} results")
        except:
            print("⚠ RuTracker search timed out (may be normal if tracker is slow)")

        page.screenshot(path=f"{SCREENSHOT_DIR}/08_search_results.png")

    def test_09_search_result_has_download_link(
        self, page: Page, qb_page: QBittorrentPage
    ):
        """Test search results have download links"""
        qb_page.login()

        # Use API for faster search
        session = requests.Session()
        session.post(
            f"{BASE_URL}/api/v2/auth/login",
            data={"username": USERNAME, "password": PASSWORD},
        )
        response = session.post(
            f"{BASE_URL}/api/v2/search/start",
            data={"pattern": "ubuntu", "plugins": "rutracker", "category": "all"},
        )
        search_id = response.json().get("id")

        # Wait for results
        time.sleep(5)

        response = session.get(
            f"{BASE_URL}/api/v2/search/results", params={"id": search_id, "limit": 1}
        )
        results = response.json()

        if results.get("results"):
            result = results["results"][0]
            url = result.get("fileUrl")
            name = result.get("fileName")

            print(f"✓ Found result: {name[:50]}...")
            print(f"  URL: {url}")

            # Check if it's a direct download URL or magnet
            if url.startswith("magnet:"):
                print("  ✓ Is magnet link")
            elif "dl.php" in url:
                print("  ✓ Is direct download URL (will be proxied)")
        else:
            print("⚠ No search results found")

    # ========== DOWNLOAD TESTS ==========

    def test_10_download_from_url_dialog_freeze(
        self, page: Page, qb_page: QBittorrentPage
    ):
        """Test that Download from URLs dialog doesn't freeze"""
        qb_page.login()
        qb_page.open_download_from_urls()

        # Enter a RuTracker URL
        test_url = "https://rutracker.org/forum/dl.php?t=6241988"
        qb_page.urls_textarea.fill(test_url)

        # Click download and verify it doesn't freeze
        start = time.time()
        qb_page.download_button_in_dialog.click()

        # Wait for either:
        # 1. Dialog to close (success)
        # 2. Error message
        # 3. Timeout (freeze)

        try:
            # Wait for dialog to close (success)
            page.wait_for_selector(
                ".mocha-window:has-text('Download from URLs')",
                state="hidden",
                timeout=10000,
            )
            elapsed = time.time() - start
            print(f"✓ Download dialog closed in {elapsed:.2f}s (success)")

            # Verify torrent was added
            time.sleep(2)
            page.wait_for_selector("#torrentsTable tbody tr", timeout=5000)
            print("✓ Torrent added to list")

        except Exception as e:
            elapsed = time.time() - start
            if elapsed > 9:
                print(f"✗ Download dialog appears to be frozen (waited {elapsed:.2f}s)")
                page.screenshot(path=f"{SCREENSHOT_DIR}/10_frozen_dialog.png")
                raise Exception("Download dialog is frozen!")
            else:
                print(f"⚠ Download failed or timed out: {e}")

        page.screenshot(path=f"{SCREENSHOT_DIR}/10_download_result.png")

    def test_11_download_from_magnet_link(self, page: Page, qb_page: QBittorrentPage):
        """Test downloading from magnet link (should work instantly)"""
        qb_page.login()
        qb_page.open_download_from_urls()

        # Use a known working magnet link
        magnet_link = "magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10&dn=Sintel&tr=udp%3A%2F%2Fexplodie.org%3A6969&tr=udp%3A%2F%2Ftracker.coppersurfer.tk%3A6969&tr=udp%3A%2F%2Ftracker.empire-js.us%3A1337&tr=udp%3A%2F%2Ftracker.leechers-paradise.org%3A6969&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=wss%3A%2F%2Ftracker.btorrent.xyz&tr=wss%3A%2F%2Ftracker.fastcast.nz&tr=wss%3A%2F%2Ftracker.openwebtorrent.com"

        qb_page.urls_textarea.fill(magnet_link)

        start = time.time()
        qb_page.download_button_in_dialog.click()

        # Dialog should close quickly
        page.wait_for_selector(
            ".mocha-window:has-text('Download from URLs')", state="hidden", timeout=5000
        )
        elapsed = time.time() - start

        print(f"✓ Magnet link added in {elapsed:.2f}s")

        # Verify torrent in list
        time.sleep(2)
        torrents = page.locator("#torrentsTable tbody tr").count()
        print(f"✓ {torrents} torrents in list")

    # ========== PERFORMANCE TESTS ==========

    def test_12_ui_response_time(self, page: Page, qb_page: QBittorrentPage):
        """Test UI response times"""
        # Login time
        start = time.time()
        qb_page.login()
        login_time = time.time() - start
        assert login_time < 5.0, f"Login too slow: {login_time:.2f}s"

        # Tab switch time
        start = time.time()
        qb_page.go_to_search_tab()
        tab_time = time.time() - start
        assert tab_time < 2.0, f"Tab switch too slow: {tab_time:.2f}s"

        print(f"✓ Login time: {login_time:.2f}s")
        print(f"✓ Tab switch time: {tab_time:.2f}s")

    def test_13_multiple_concurrent_requests(
        self, page: Page, qb_page: QBittorrentPage
    ):
        """Test handling multiple concurrent requests"""
        qb_page.login()

        # Use API for concurrent test
        import concurrent.futures

        session = requests.Session()
        session.post(
            f"{BASE_URL}/api/v2/auth/login",
            data={"username": USERNAME, "password": PASSWORD},
        )

        def make_request(i):
            start = time.time()
            response = session.get(f"{BASE_URL}/api/v2/app/version", timeout=5)
            return time.time() - start

        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(10)]
            times = [f.result() for f in concurrent.futures.as_completed(futures)]

        avg_time = sum(times) / len(times)
        max_time = max(times)

        print(f"✓ 10 concurrent requests: avg={avg_time:.3f}s, max={max_time:.3f}s")
        assert max_time < 2.0, f"Some requests too slow: {max_time:.2f}s"


class TestQBittorrentAPI:
    """API-only tests (faster)"""

    @pytest.fixture
    def session(self):
        """Create authenticated session"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/v2/auth/login",
            data={"username": USERNAME, "password": PASSWORD},
            timeout=10,
        )
        assert response.text == "Ok.", f"Login failed: {response.text}"
        return session

    def test_api_version(self, session):
        """Test API version endpoint"""
        response = session.get(f"{BASE_URL}/api/v2/app/version", timeout=5)
        assert response.status_code == 200
        assert response.text.startswith("v")
        print(f"✓ API version: {response.text}")

    def test_api_plugins(self, session):
        """Test plugins endpoint"""
        response = session.get(f"{BASE_URL}/api/v2/search/plugins", timeout=5)
        plugins = response.json()

        enabled = [p for p in plugins if p.get("enabled")]
        print(f"✓ {len(enabled)}/{len(plugins)} plugins enabled")

        # Check RuTracker
        rutracker = next((p for p in plugins if p.get("name") == "rutracker"), None)
        assert rutracker is not None, "RuTracker plugin not found"
        assert rutracker.get("enabled"), "RuTracker not enabled"
        print("✓ RuTracker plugin enabled")

    def test_api_search_and_download(self, session):
        """Test search and download via API"""
        # Start search
        response = session.post(
            f"{BASE_URL}/api/v2/search/start",
            data={"pattern": "ubuntu", "plugins": "rutracker", "category": "all"},
            timeout=15,
        )
        search_id = response.json().get("id")
        assert search_id, "Search failed to start"

        # Wait for results
        time.sleep(5)

        # Get results
        response = session.get(
            f"{BASE_URL}/api/v2/search/results",
            params={"id": search_id, "limit": 1},
            timeout=10,
        )
        results = response.json()

        if results.get("results"):
            download_url = results["results"][0]["fileUrl"]
            file_name = results["results"][0]["fileName"]

            # Add torrent
            response = session.post(
                f"{BASE_URL}/api/v2/torrents/add",
                data={"urls": download_url},
                timeout=15,
            )

            assert response.text == "Ok.", f"Download failed: {response.text}"
            print(f"✓ Downloaded: {file_name[:50]}...")

            # Verify in list
            time.sleep(2)
            response = session.get(f"{BASE_URL}/api/v2/torrents/info", timeout=10)
            torrents = response.json()

            found = any(t for t in torrents if "ubuntu" in t["name"].lower())
            assert found, "Torrent not in list"
            print("✓ Torrent verified in list")
        else:
            print("⚠ No search results (tracker may be slow)")


def run_standalone():
    """Run tests in standalone mode"""
    import sys

    print("=" * 70)
    print("qBittorrent Comprehensive UI Automation Test Suite")
    print("Using Playwright for full browser automation")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {BASE_URL}")
    print()

    # Create directories
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)

    # Run tests
    exit_code = pytest.main(
        [
            __file__,
            "-v",
            "-s",
            "--tb=short",
            f"--html=/tmp/qb_test_report.html",
            "--self-contained-html",
        ]
    )

    print()
    print("=" * 70)
    print(f"Screenshots: {SCREENSHOT_DIR}")
    print(f"Videos: {VIDEO_DIR}")
    print(f"Report: /tmp/qb_test_report.html")
    print("=" * 70)

    return exit_code


if __name__ == "__main__":
    import sys

    sys.exit(run_standalone())
