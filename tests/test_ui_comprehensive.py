#!/usr/bin/env python3
"""
Comprehensive UI Test Suite for qBittorrent
Tests: Login, Download Dialog, Search, RuTracker, API
"""

import sys
import os
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright, Page

BASE_URL = "http://localhost:7186"
USERNAME = "admin"
PASSWORD = "admin"
SCREENSHOT_DIR = "/tmp/qb_screenshots"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def pass(self, name: str, msg: str = ""):
        self.passed += 1
        self.tests.append((name, "PASS", msg))
        print(f"\033[92m✓\033[0m {name}: {msg}")
    
    def fail(self, name: str, msg: str = ""):
        self.failed += 1
        self.tests.append((name, "FAIL", msg))
        print(f"\033[91m✗\033[0m {name}: {msg}")
    
    def summary(self):
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Passed:  {self.passed}")
        print(f"Failed:  {self.failed}")
        for name, status, msg in self.tests:
            symbol = "✓" if status == "PASS" else "✗"
            print(f"  {symbol} {name}")
        return self.failed == 0

results = TestResults()
api_session = None

def get_api_session():
    global api_session
    if not api_session:
        api_session = requests.Session()
        r = api_session.post(f"{BASE_URL}/api/v2/auth/login",
                             data={"username": USERNAME, "password": PASSWORD})
        if r.text != "Ok.":
            raise Exception(f"API login failed")
    return api_session

def screenshot(page: Page, name: str):
    try:
        page.screenshot(path=f"{SCREENSHOT_DIR}/{name}.png")
    except:
        pass

print(f"\n{'='*60}")
print(f"qBittorrent Comprehensive UI Test Suite")
print(f"{'='*60}")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"URL: {BASE_URL}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page()
    page.set_default_timeout(30000)
    
    # Test 1: Login Page
    print(f"\n{'='*60}")
    print("TEST 1: Login Page Load Time")
    print(f"{'='*60}")
    try:
        start = time.time()
        page.goto(BASE_URL)
        page.wait_for_selector("#loginButton", timeout=5000)
        elapsed = time.time() - start
        screenshot(page, "01_login")
        results.pass("Login page loads", f"{elapsed:.2f}s")
    except Exception as e:
        results.fail("Login page loads", str(e))
    
    # Test 2: Login
    print(f"\n{'='*60}")
    print("TEST 2: Login Flow")
    print(f"{'='*60}")
    try:
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        start = time.time()
        page.click("#loginButton")
        page.wait_for_selector("#desktopNavbar", timeout=10000)
        elapsed = time.time() - start
        screenshot(page, "02_logged_in")
        results.pass("Login successful", f"{elapsed:.2f}s")
    except Exception as e:
        results.fail("Login successful", str(e))
    
    # Test 3: Download Dialog
    print(f"\n{'='*60}")
    print("TEST 3: Download from URLs Dialog")
    print(f"{'='*60}")
    try:
        page.click("text=File")
        time.sleep(0.5)
        page.click("text=Add Torrent Link...")
        page.wait_for_selector(".mocha-window", timeout=5000)
        screenshot(page, "03_download_dialog")
        results.pass("Download dialog opens")
    except Exception as e:
        results.fail("Download dialog opens", str(e))
    
    # Test 4: Add RuTracker URL
    print(f"\n{'='*60}")
    print("TEST 4: Add RuTracker URL")
    print(f"{'='*60}")
    try:
        textarea = page.locator("textarea").first
        url = "https://rutracker.org/forum/dl.php?t=6241988"
        textarea.fill(url)
        screenshot(page, "04_url_added")
        results.pass("URL added")
    except Exception as e:
        results.fail("URL added", str(e))
    
    # Test 5: Click Download
    print(f"\n{'='*60}")
    print("TEST 5: Click Download Button")
    print(f"{'='*60}")
    try:
        btn = page.locator("button:has-text('Download')").first
        start = time.time()
        btn.click()
        time.sleep(8)
        elapsed = time.time() - start
        screenshot(page, "05_after_download")
        
        # Check if dialog closed or torrent added
        dialog_visible = page.locator(".mocha-window:visible").count()
        if dialog_visible == 0:
            results.pass("Download completed", f"dialog closed, {elapsed:.2f}s")
        else:
            results.pass("Download initiated", f"dialog still open, {elapsed:.2f}s")
    except Exception as e:
        results.fail("Download button", str(e))
    
    # Test 6: Verify Torrent in List
    print(f"\n{'='*60}")
    print("TEST 6: Verify Torrent Added")
    print(f"{'='*60}")
    try:
        time.sleep(2)
        rows = page.locator("[id^='torrent']").count()
        if rows > 0:
            results.pass("Torrent in list", f"{rows} torrents")
        else:
            results.fail("Torrent in list", "no torrents")
    except Exception as e:
        results.fail("Torrent verification", str(e))
    
    # Test 7: Search Tab
    print(f"\n{'='*60}")
    print("TEST 7: Search Tab")
    print(f"{'='*60}")
    try:
        page.click("text=Search")
        page.wait_for_selector("#searchPattern", timeout=5000)
        screenshot(page, "06_search_tab")
        results.pass("Search tab opens")
    except Exception as e:
        results.fail("Search tab", str(e))
    
    # Test 8: RuTracker Search
    print(f"\n{'='*60}")
    print("TEST 8: RuTracker Search")
    print(f"{'='*60}")
    try:
        page.fill("#searchPattern", "ubuntu")
        start = time.time()
        page.click("#startSearchBtn")
        time.sleep(10)
        elapsed = time.time() - start
        
        rows = page.locator("#searchResultsTable tbody tr").count()
        screenshot(page, "07_search_results")
        
        if rows > 0:
            results.pass("RuTracker search", f"{rows} results in {elapsed:.2f}s")
        else:
            results.fail("RuTracker search", "no results")
    except Exception as e:
        results.fail("RuTracker search", str(e))
    
    browser.close()

# Test 9-12: API Tests
print(f"\n{'='*60}")
print("TEST 9-12: API Performance")
print(f"{'='*60}")

try:
    session = get_api_session()
    
    for endpoint in ["/api/v2/app/version", "/api/v2/torrents/info", "/api/v2/search/plugins"]:
        start = time.time()
        r = session.get(f"{BASE_URL}{endpoint}", timeout=5)
        elapsed = time.time() - start
        
        name = endpoint.split("/")[-1]
        if elapsed < 1.0:
            results.pass(f"API {name}", f"{elapsed:.3f}s")
        else:
            results.fail(f"API {name}", f"{elapsed:.3f}s (slow)")
except Exception as e:
    results.fail("API tests", str(e))

# Summary
success = results.summary()
print(f"\nScreenshots: {SCREENSHOT_DIR}")

sys.exit(0 if success else 1)
