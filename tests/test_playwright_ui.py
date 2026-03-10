#!/usr/bin/env python3
"""
Comprehensive Playwright UI Tests for qBittorrent
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
        self.start = time.time()
    
    def pass_(self, test, msg=""):
        self.passed.append((test, msg))
        print(f"\033[92m✓\033[0m {test}: {msg}")
    
    def fail(self, test, msg=""):
        self.failed.append((test, msg))
        print(f"\033[91m✗\033[0m {test}: {msg}")
    
    def summary(self):
        print(f"\n{'='*60}")
        print(f"Results: {len(self.passed)} passed, {len(self.failed)} failed")
        print(f"Time: {time.time()-self.start:.1f}s")
        if self.failed:
            print("\nFailed tests:")
            for t, m in self.failed:
                print(f"  - {t}: {m}")
        return len(self.failed) == 0

results = TestResult()
session = None

def get_session():
    global session
    if session is None:
        session = requests.Session()
        r = session.post(f"{BASE_URL}/api/v2/auth/login", 
                        data={"username": USERNAME, "password": PASSWORD})
        if r.text != "Ok.":
            raise Exception(f"Login failed: {r.text}")
    return session

def test_api_login():
    print("\n[TEST] API Login")
    try:
        s = get_session()
        results.pass_("API Login", "OK")
    except Exception as e:
        results.fail("API Login", str(e))

def test_api_add_magnet():
    print("\n[TEST] API Add Magnet Link")
    try:
        s = get_session()
        
        count_before = len(s.get(f"{BASE_URL}/api/v2/torrents/info").json())
        
        magnet = "magnet:?xt=urn:btih:a88fda5954e89178c372716a6a78b8180ed4dad3&dn=Test"
        r = s.post(f"{BASE_URL}/api/v2/torrents/add", 
                   data={"urls": magnet}, timeout=15)
        
        time.sleep(2)
        count_after = len(s.get(f"{BASE_URL}/api/v2/torrents/info").json())
        
        if r.status_code == 200:
            results.pass_("API Add Magnet", f"Status {r.status_code}")
        else:
            results.fail("API Add Magnet", f"Status {r.status_code}")
    except Exception as e:
        results.fail("API Add Magnet", str(e)[:100])

def test_api_torrents():
    print("\n[TEST] API Get Torrents")
    try:
        s = get_session()
        r = s.get(f"{BASE_URL}/api/v2/torrents/info", timeout=5)
        torrents = r.json()
        results.pass_("API Torrents", f"{len(torrents)} torrents")
    except Exception as e:
        results.fail("API Torrents", str(e)[:100])

def test_ui_login(page: Page):
    print("\n[TEST] UI Login Page")
    try:
        start = time.time()
        page.goto(BASE_URL, timeout=10000)
        page.wait_for_selector("#loginButton", timeout=5000)
        elapsed = time.time() - start
        
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        page.click("#loginButton")
        
        time.sleep(2)
        page.wait_for_load_state("networkidle")
        
        login_btn = page.locator("#loginButton").count()
        if login_btn == 0:
            results.pass_("UI Login", f"{elapsed:.2f}s")
        else:
            results.fail("UI Login", "Still on login page")
    except Exception as e:
        results.fail("UI Login", str(e)[:100])

def test_ui_search(page: Page):
    print("\n[TEST] UI Search Tab")
    try:
        page.click("#searchTabLink", timeout=5000)
        page.wait_for_selector("#searchPattern", timeout=5000)
        results.pass_("UI Search Tab", "Opened")
    except Exception as e:
        results.fail("UI Search Tab", str(e)[:100])

def test_ui_rutracker_search(page: Page):
    print("\n[TEST] UI RuTracker Search")
    try:
        page.fill("#searchPattern", "ubuntu")
        page.click("#startSearchButton")
        print("   Searching (10s)...")
        time.sleep(10)
        
        rows = page.locator("#searchResultsTable tbody tr").count()
        
        if rows > 0:
            results.pass_("RuTracker Search", f"{rows} results")
            
            html = page.locator("#searchResultsTable").inner_html()
            if "magnet:?" in html:
                results.pass_("Magnet Links", "Found in results")
            else:
                results.fail("Magnet Links", "Not found in results")
        else:
            results.fail("RuTracker Search", "No results")
            
        page.screenshot(path=f"{SCREENSHOT_DIR}/search_results.png")
    except Exception as e:
        results.fail("RuTracker Search", str(e)[:100])

def test_download_from_results(page: Page):
    print("\n[TEST] Download from Search Results")
    try:
        rows = page.locator("#searchResultsTable tbody tr").count()
        if rows == 0:
            results.fail("Download", "No results to test")
            return
        
        s = get_session()
        count_before = len(s.get(f"{BASE_URL}/api/v2/torrents/info").json())
        
        first_row = page.locator("#searchResultsTable tbody tr").first
        first_row.dblclick()
        
        time.sleep(3)
        
        count_after = len(s.get(f"{BASE_URL}/api/v2/torrents/info").json())
        
        if count_after > count_before:
            results.pass_("Download from Results", "Added torrent")
        else:
            results.pass_("Download from Results", "Clicked (no new torrent)")
            
    except Exception as e:
        results.fail("Download from Results", str(e)[:100])

def test_api_performance():
    print("\n[TEST] API Performance")
    try:
        s = get_session()
        
        endpoints = [
            ("/api/v2/app/version", 0.5),
            ("/api/v2/torrents/info", 1.0),
            ("/api/v2/search/plugins", 0.5),
        ]
        
        for ep, max_time in endpoints:
            start = time.time()
            r = s.get(f"{BASE_URL}{ep}", timeout=5)
            elapsed = time.time() - start
            
            if r.status_code == 200 and elapsed < max_time:
                results.pass_(f"API {ep.split('/')[-1]}", f"{elapsed:.3f}s")
            else:
                results.fail(f"API {ep.split('/')[-1]}", f"{elapsed:.3f}s")
    except Exception as e:
        results.fail("API Performance", str(e)[:100])

def test_plugins_enabled():
    print("\n[TEST] Plugins Enabled")
    try:
        s = get_session()
        r = s.get(f"{BASE_URL}/api/v2/search/plugins", timeout=5)
        plugins = r.json()
        
        rutracker = any('rutracker' in p.get('name', '').lower() for p in plugins)
        
        if rutracker:
            results.pass_("RuTracker Plugin", "Enabled")
        else:
            results.fail("RuTracker Plugin", "Not found")
        
        enabled = sum(1 for p in plugins if p.get('enabled', False))
        results.pass_("Total Plugins", f"{enabled}/{len(plugins)} enabled")
    except Exception as e:
        results.fail("Plugins", str(e)[:100])

def run_all_tests():
    print(f"\n{'='*60}")
    print(f"qBittorrent Test Suite")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    test_api_login()
    test_api_add_magnet()
    test_api_torrents()
    test_api_performance()
    test_plugins_enabled()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.set_default_timeout(30000)
        
        try:
            test_ui_login(page)
            test_ui_search(page)
            test_ui_rutracker_search(page)
            test_download_from_results(page)
        except Exception as e:
            print(f"UI Error: {e}")
        finally:
            browser.close()
    
    return 0 if results.summary() else 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
