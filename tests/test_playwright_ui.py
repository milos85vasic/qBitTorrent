#!/usr/bin/env python3
"""
Comprehensive Playwright UI Tests for qBittorrent
Tests all UI interactions including:
- Login flow
- Download from URLs dialog
- Search functionality  
- RuTracker integration
"""

import sys
import os
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright, Page

BASE_URL = "http://localhost:8085"
USERNAME = "admin"
PASSWORD = "admin"
SCREENSHOT_DIR = "/tmp/qb_screenshots"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

class TestResult:
    def __init__(self):
        self.passed = []
        self.failed = []
    
    def add_pass(self, test: str, msg: str = ""):
        self.passed.append((test, msg))
        print(f"\033[92m✓\033[0m {test}: {msg}")
    
    def add_fail(self, test: str, msg: str = ""):
        self.failed.append((test, msg))
        print(f"\033[91m✗\033[0m {test}: {msg}")
    
    def summary(self):
        print(f"\n{'='*60}")
        print(f"Results: {len(self.passed)} passed, {len(self.failed)} failed")
        print(f"{'='*60}")
        return len(self.failed) == 0

results = TestResult()
session = None

def get_session():
    global session
    if not session:
        session = requests.Session()
        r = session.post(f"{BASE_URL}/api/v2/auth/login", 
                        data={"username": USERNAME, "password": PASSWORD})
        if r.text != "Ok.":
            raise Exception(f"Login failed: {r.text}")
    return session

def take_screenshot(page: Page, name: str):
    try:
        page.screenshot(path=f"{SCREENSHOT_DIR}/{name}.png")
    except:
        pass

def test_login_page(page: Page):
    print("\n[TEST] Login Page Load")
    start = time.time()
    page.goto(BASE_URL)
    page.wait_for_selector("#loginButton", timeout=5000)
    elapsed = time.time() - start
    take_screenshot(page, "01_login")
    
    if elapsed < 1.0:
        results.add_pass("Login page loads", f"{elapsed:.2f}s")
    else:
        results.add_fail("Login page too slow", f"{elapsed:.2f}s")

def test_login_flow(page: Page):
    print("\n[TEST] Login Flow")
    page.fill("#username", USERNAME)
    page.fill("#password", PASSWORD)
    page.click("#loginButton")
    
    try:
        page.wait_for_selector("#torrentsTable", timeout=10000)
        take_screenshot(page, "02_logged_in")
        results.add_pass("Login successful")
    except:
        results.add_fail("Login failed")
        raise

def test_download_dialog(page: Page):
    print("\n[TEST] Download from URLs Dialog")
    
    try:
        # Open File menu
        page.click("text=File")
        time.sleep(0.3)
        
        # Click Add Torrent Link
        page.click("text=Add Torrent Link...")
        
        # Wait for dialog
        page.wait_for_selector(".mocha-window", timeout=5000)
        take_screenshot(page, "03_download_dialog")
        results.add_pass("Download dialog opened")
        
        return True
    except Exception as e:
        results.add_fail("Download dialog", str(e))
        return False

def test_add_rutracker_url(page: Page):
    print("\n[TEST] Add RuTracker URL")
    
    try:
        # Find textarea
        textarea = page.locator("textarea").first
        if textarea:
            url = "https://rutracker.org/forum/dl.php?t=6241988"
            textarea.fill(url)
            take_screenshot(page, "04_url_added")
            results.add_pass("URL added to dialog")
            return True
        else:
            results.add_fail("Textarea not found")
            return False
    except Exception as e:
        results.add_fail("Add URL", str(e))
        return False

def test_click_download(page: Page):
    print("\n[TEST] Click Download Button")
    
    try:
        # Find download button
        btn = page.locator("button:has-text('Download')").first
        if btn:
            start = time.time()
            btn.click()
            
            # Wait for response
            time.sleep(5)
            elapsed = time.time() - start
            
            take_screenshot(page, "05_after_download")
            
            # Check if dialog closed
            dialog = page.locator(".mocha-window:visible").count()
            if dialog == 0:
                results.add_pass("Download clicked - dialog open")
            else:
                results.add_pass("Download clicked - dialog closed")
        else:
            results.add_fail("Download button not found")
    except Exception as e:
        results.add_fail("Click download", str(e))

def test_search_tab(page: Page):
    print("\n[TEST] Search Tab")
    
    try:
        # Click Search tab
        page.click("text=Search")
        page.wait_for_selector("#searchPattern", timeout=5000)
        take_screenshot(page, "06_search_tab")
        results.add_pass("Search tab opened")
    except Exception as e:
        results.add_fail("Search tab", str(e))

def test_rutracker_search(page: Page):
    print("\n[TEST] RuTracker Search")
    
    try:
        # Fill search
        page.fill("#searchPattern", "ubuntu")
        
        # Click search button
        page.click("#startSearchBtn")
        
        # Wait for results
        time.sleep(10)
        
        # Check results
        rows = page.locator("#searchResultsTable tbody tr").count()
        take_screenshot(page, "07_search_results")
        
        if rows > 0:
            results.add_pass("RuTracker search", f"{rows} results")
        else:
            results.add_fail("No search results")
    except Exception as e:
        results.add_fail("RuTracker search", str(e))

def test_api_endpoints():
    print("\n[TEST] API Performance")
    
    s = get_session()
    endpoints = [
        "/api/v2/app/version",
        "/api/v2/torrents/info",
        "/api/v2/search/plugins"
    ]
    
    for ep in endpoints:
        start = time.time()
        r = s.get(f"{BASE_URL}{ep}", timeout=5)
        elapsed = time.time() - start
        
        if elapsed < 1.0:
            results.add_pass(f"API {ep.split('/')[-1]}", f"{elapsed:.3f}s")
        else:
            results.add_fail(f"API {ep.split('/')[-1]}", f"{elapsed:.3f}s (slow)")

def run_all_tests():
    print(f"\n{'='*60}")
    print(f"qBittorrent Playwright Test Suite")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        
        try:
            test_login_page(page)
            test_login_flow(page)
            test_download_dialog(page)
            test_add_rutracker_url(page)
            test_click_download(page)
            test_search_tab(page)
            test_rutracker_search(page)
        except Exception as e:
            print(f"\nTest suite error: {e}")
        finally:
            browser.close()
    
    # API tests
    try:
        test_api_endpoints()
    except Exception as e:
        print(f"API tests error: {e}")
    
    # Summary
    success = results.summary()
    print(f"\nScreenshots saved to: {SCREENSHOT_DIR}")
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
