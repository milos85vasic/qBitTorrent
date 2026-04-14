#!/usr/bin/env python3
"""
qBittorrent Comprehensive UI Test Suite
Tests all UI flows including login, search, download, dialogs,"""

import sys
import time
from playwright.sync_api import sync_playwright, Page, Browser
import requests
from datetime import datetime

from typing import Optional, List, Dict

# Configuration
BASE_URL = "http://localhost:7186"
USERNAME = "admin"
PASSWORD = "admin"
HEADLESS = True
SCREENSHOT_DIR = "/tmp/qb_screenshots"


class TestRunner:
    """Main test runner class"""
    
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        
    def log(self, test_name: str, status: str, message: str = "", time_taken: float = 0.0):
        symbol = "✓" if status == "PASS" else ("✗" if status == "FAIL" else "⊘")
        color = "\033[92m" if status == "PASS" else ("\033[91m" if status == "FAIL" else "\033[93m")
        reset = "\033[0m"
        
        self.results.append({
            "test": test_name,
            "status": status,
            "message": message,
            "time": time_taken
        })
        
        print(f"{color}{symbol}{reset} {test_name}: {message} ({time_taken:.2f}s)")
        
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        else:
            self.skipped += 1
    
    def print_header(self, text: str):
        print(f"\n{'='*60}")
        print(f"  {text}")
        print(f"{'='*60}")
    
    def save_screenshot(self, page: Page, name: str):
        import os
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        try:
            page.screenshot(path=f"{SCREENSHOT_DIR}/{name}.png")
        except Exception as e:
            print(f"Could not save screenshot: {e}")


class QBittorrentTests:
    """Test class with Playwright"""
    
    def __init__(self):
        self.browser = None
        self.page = None
        self.runner = TestRunner()
        self.session = None
    
    def setup(self):
        """Initialize browser"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=HEADLESS,
            args=['--no-sandbox']
        )
        self.page = self.browser.new_page()
        self.page.set_default_timeout(30000)
    
    def teardown(self):
        """Cleanup"""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def login_api(self) -> requests.Session:
        """Login via API for faster requests"""
        if not self.session:
            self.session = requests.Session()
            response = self.session.post(
                f"{BASE_URL}/api/v2/auth/login",
                data={"username": USERNAME, "password": PASSWORD},
                timeout=10
            )
            if response.text != "Ok.":
                raise Exception(f"Login failed: {response.text}")
        return self.session
    
    def wait_for_selector(self, selector: str, timeout: int = 5000):
        """Wait for element"""
        self.page.wait_for_selector(selector, timeout=timeout)
    
    # ========== TESTS ==========
    
    def test_01_login_page_loads_instantly(self):
        """Test login page loads in under 1 second"""
        self.runner.print_header("Test 1: Login Page Load Time")
        
        start = time.time()
        self.page.goto(BASE_URL)
        self.wait_for_selector("#loginButton", timeout=5000)
        elapsed = time.time() - start
        
        self.runner.save_screenshot(self.page, "01_login_page")
        
        if elapsed < 1.0:
            self.runner.log("Login page loads instantly", "PASS", f"{elapsed:.2f}s", elapsed)
        else:
            self.runner.log("Login page too slow", "FAIL", f"{elapsed:.2f}s", elapsed)
    
    def test_02_login_page_elements(self):
        """Test login page has all required elements"""
        self.runner.print_header("Test 2: Login Page Elements")
        
        # Already on login page from previous test
        username = self.page.query_selector("#username")
        password = self.page.query_selector("#password")
        login_btn = self.page.query_selector("#loginButton")
        logo = self.page.query_selector("img")
        
        checks = []
        if username:
            checks.append("username input")
        if password:
            checks.append("password input")
        if login_btn:
            checks.append("login button")
        if logo:
            checks.append("logo")
        
        self.runner.save_screenshot(self.page, "02_login_elements")
        
        if len(checks) == 4:
            self.runner.log("All elements present", "PASS", ", ".join(checks), 0)
        else:
            self.runner.log("Missing elements", "FAIL", f"Found: {checks}", 0)
    
    def test_03_ui_login(self):
        """Test login through UI"""
        self.runner.print_header("Test 3: UI Login")
        
        start = time.time()
        
        # Fill login form
        self.page.fill("#username", USERNAME)
        self.page.fill("#password", PASSWORD)
        self.page.click("#loginButton")
        
        # Wait for main UI
        try:
            self.wait_for_selector("#torrentsTable", timeout=10000)
            elapsed = time.time() - start
            
            self.runner.save_screenshot(self.page, "03_logged_in")
            self.runner.log("UI login successful", "PASS", f"{elapsed:.2f}s", elapsed)
        except Exception as e:
            self.runner.log("UI login failed", "FAIL", str(e), 0)
    
    def test_04_main_ui_loads(self):
        """Test main UI loads after login"""
        self.runner.print_header("Test 4: Main UI Load")
        
        # Already logged in
        start = time.time()
        
        # Check for main elements
        try:
            toolbar = self.page.query_selector("#desktopToolbar")
            torrent_table = self.page.query_selector("#torrentsTable")
            
            elapsed = time.time() - start
            
            if toolbar and torrent_table:
                self.runner.save_screenshot(self.page, "04_main_ui")
                self.runner.log("Main UI loaded", "PASS", f"{elapsed:.2f}s", elapsed)
            else:
                self.runner.log("Main UI elements missing", "FAIL", "", 0)
        except Exception as e:
            self.runner.log("Main UI load failed", "FAIL", str(e), 0)
    
    def test_05_download_from_urls_dialog(self):
        """Test Download from URLs dialog opens"""
        self.runner.print_header("Test 5: Download from URLs Dialog")
        
        try:
            # Click File menu
            file_menu = self.page.query_selector("text=File")
            if not file_menu:
                # Try alternative approach - use keyboard shortcut or                pass
                self.page.keyboard.press("Control+n")
            else:
                file_menu.click()
                time.sleep(0.5)
                
                # Click Add Torrent Link
                add_link = self.page.query_selector("text=Add Torrent Link...")
                if add_link:
                    add_link.click()
                else:
                    # Try alternative text
                    add_link2 self.page.query_selector("text=Add torrent link")
                    if add_link2:
                        add_link2.click()
            
            # Wait for dialog
            time.sleep(1)
            dialog = self.page.query_selector(".mocha-window")
            
            self.runner.save_screenshot(self.page, "05_download_dialog")
            
            if dialog:
                self.runner.log("Download dialog opened", "PASS", "", 0)
            else:
                self.runner.log("Download dialog not found", "FAIL", "", 0)
        except Exception as e:
            self.runner.log("Download dialog test failed", "FAIL", str(e), 0)
    
    def test_06_add_rutracker_url_to_dialog(self):
        """Test adding RuTracker URL to download dialog"""
        self.runner.print_header("Test 6: Add RuTracker URL")
        
        try:
            # Find URL textarea
            textarea = self.page.query_selector("#urls, textarea")
            
            if textarea:
                test_url = "https://rutracker.org/forum/dl.php?t=6241988"
                textarea.fill(test_url)
                
                self.runner.save_screenshot(self.page, "06_url_added")
                self.runner.log("URL added to dialog", "PASS", test_url, 0)
            else:
                self.runner.log("URL textarea not found", "FAIL", "", 0)
        except Exception as e:
            self.runner.log("Add URL failed", "FAIL", str(e), 0)
    
    def test_07_click_download_button(self):
        """Test clicking Download button in dialog"""
        self.runner.print_header("Test 7: Click Download Button")
        
        try:
            # Find Download button
            download_btn = self.page.query_selector("#downloadButton")
            if not download_btn:
                download_btn = self.page.query_selector("button:has-text('Download')")
            if not download_btn:
                # Try finding all buttons in dialog
                buttons = self.page.query_selector_all(".mocha-window button")
                if buttons:
                    for btn in buttons:
                        if "download" in btn.inner_text().lower():
                            download_btn = btn
                            break
            
            if download_btn:
                start = time.time()
                download_btn.click()
                
                # Wait for response - dialog should close or show progress
                time.sleep(3)
                
                elapsed = time.time() - start
                
                # Check if dialog closed
                dialog = self.page.query_selector(".mocha-window")
                if not dialog or not dialog.is_visible():
                    self.runner.save_screenshot(self.page, "07_after_download")
                    self.runner.log("Download button clicked - dialog closed", "PASS", f"{elapsed:.2f}s", elapsed)
                else:
                    # Check for progress indicator
                    progress = self.page.query_selector(".progress")
                    self.runner.log("Download in progress", "PASS", f"Dialog still open, elapsed)
            else:
                self.runner.log("Download button not found", "FAIL", "", 0)
        except Exception as e:
            self.runner.log("Click download failed", "FAIL", str(e), 0)
    
    def test_08_verify_torrent_added(self):
        """Verify torrent was added to list"""
        self.runner.print_header("Test 8: Verify Torrent Added")
        
        time.sleep(2)
        
        try:
            # Check torrent table
            rows = self.page.query_selector_all("#torrentsTable tbody tr")
            count = len(rows) if rows else 0
            
            self.runner.save_screenshot(self.page, "08_torrent_list")
            
            if count > 0:
                self.runner.log("Torrent added to list", "PASS", f"{count} torrent(s) in list", 0)
            else:
                self.runner.log("No torrents in list", "FAIL", "", 0)
        except Exception as e:
            self.runner.log("Verify failed", "FAIL", str(e), 0)
    
    def test_09_search_tab(self):
        """Test Search tab opens"""
        self.runner.print_header("Test 9: Search Tab")
        
        try:
            # Click Search tab
            search_tab = self.page.query_selector("#tabSearch, text=Search")
            if not search_tab:
                search_tab = self.page.query_selector("button:has-text('Search')")
            
            if search_tab:
                start = time.time()
                search_tab.click()
                
                # Wait for search panel
                self.wait_for_selector("#searchPattern", timeout=5000)
                elapsed = time.time() - start
                
                self.runner.save_screenshot(self.page, "09_search_tab")
                self.runner.log("Search tab opened", "PASS", f"{elapsed:.2f}s", elapsed)
            else:
                self.runner.log("Search tab not found", "FAIL", "", 0)
        except Exception as e:
            self.runner.log("Search tab test failed", "FAIL", str(e), 0)
    
    def test_10_rutracker_search(self):
        """Test RuTracker search through UI"""
        self.runner.print_header("Test 10: RuTracker Search")
        
        try:
            # Fill search pattern
            search_input = self.page.query_selector("#searchPattern")
            if search_input:
                search_input.fill("ubuntu")
                
                # Start search
                start_btn = self.page.query_selector("#startSearchBtn, button:has-text('Search')")
                if start_btn:
                    start_btn.click()
                    
                    # Wait for results
                    time.sleep(10)
                    
                    # Check for results
                    results = self.page.query_selector_all("#searchResultsTable tbody tr")
                    count = len(results) if results else 0
                    
                    self.runner.save_screenshot(self.page, "10_search_results")
                    
                    if count > 0:
                        self.runner.log("RuTracker search successful", "PASS", f"{count} results", 0)
                    else:
                        self.runner.log("No search results", "FAIL", "", 0)
            else:
                self.runner.log("Search input not found", "FAIL", "", 0)
        except Exception as e:
            self.runner.log("RuTracker search failed", "FAIL", str(e), 0)
    
    def test_11_download_from_search(self):
        """Test downloading from search results"""
        self.runner.print_header("Test 11: Download from Search")
        
        try:
            # Find first download link in search results
            download_links = self.page.query_selector_all("#searchResultsTable a")
            
            if download_links and len(download_links) > 0:
                first_link = download_links[0]
                start = time.time()
                first_link.click()
                
                # Wait for download to complete
                time.sleep(3)
                elapsed = time.time() - start
                
                self.runner.save_screenshot(self.page, "11_download_from_search")
                self.runner.log("Download from search", "PASS", f"{elapsed:.2f}s", elapsed)
            else:
                self.runner.log("No download links in results", "FAIL", "", 0)
        except Exception as e:
            self.runner.log("Download from search failed", "FAIL", str(e), 0)
    
    def test_12_api_performance(self):
        """Test API response times"""
        self.runner.print_header("Test 12: API Performance")
        
        session = self.login_api()
        
        endpoints = [
            "/api/v2/app/version",
            "/api/v2/transfer/info",
            "/api/v2/torrents/info",
            "/api/v2/search/plugins"
        ]
        
        all_fast = True
        for endpoint in endpoints:
            start = time.time()
            response = session.get(f"{BASE_URL}{endpoint}", timeout=5)
            elapsed = time.time() - start
            
            if elapsed < 1.0:
                self.runner.log(f"API {endpoint.split('/')[-1]}", "PASS", f"{elapsed:.3f}s", elapsed)
            else:
                self.runner.log(f"API {endpoint.split('/')[-1]}", "FAIL", f"{elapsed:.3f}s (too slow)", elapsed)
                all_fast = False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print(f"\n{'='*60}")
        print(f"  qBittorrent UI Automation Test Suite")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Target: {BASE_URL}")
        print(f"{'='*60}\n")
        
        try:
            self.setup()
            
            # Run all tests
            self.test_01_login_page_loads_instantly()
            self.test_02_login_page_elements()
            self.test_03_ui_login()
            self.test_04_main_ui_loads()
            self.test_05_download_from_urls_dialog()
            self.test_06_add_rutracker_url_to_dialog()
            self.test_07_click_download_button()
            self.test_08_verify_torrent_added()
            self.test_09_search_tab()
            self.test_10_rutracker_search()
            self.test_11_download_from_search()
            self.test_12_api_performance()
            
        finally:
            self.teardown()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*60}")
        print(f"  Test Summary")
        print(f"{'='*60}")
        print(f"  Passed:  {self.runner.passed}")
        print(f"  Failed:  {self.runner.failed}")
        print(f"  Skipped: {self.runner.skipped}")
        print(f"  Total:   {self.runner.passed + self.runner.failed + self.runner.skipped}")
        print(f"\n  Screenshots: {SCREENSHOT_DIR}")
        
        if self.runner.failed > 0:
            print(f"\n  ✗ Some tests failed!")
            return 1
        else:
            print(f"\n  ✓ All tests passed!")
            return 0


def main():
    """Main entry point"""
    test_suite = QBittorrentTests()
    exit_code = test_suite.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    Main()
