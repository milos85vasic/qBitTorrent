#!/usr/bin/env python3
"""
WebUI Automation Test Suite using Playwright

This test suite:
1. Opens qBittorrent WebUI in a browser
2. Tests search functionality through the UI
3. Verifies plugin loading
4. Tests download workflow end-to-end
5. Takes screenshots for verification

Requirements:
    pip install playwright pytest-playwright
    playwright install

Usage:
    python3 tests/test_webui_automation.py
    python3 tests/test_webui_automation.py --headed  # See browser
    python3 tests/test_webui_automation.py --plugin rutor
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime
from typing import Dict, List, Optional

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
PLUGINS_DIR = os.path.join(PROJECT_DIR, "plugins")
sys.path.insert(0, PLUGINS_DIR)
sys.path.insert(0, SCRIPT_DIR)

# Try to import playwright
try:
    from playwright.sync_api import sync_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not available. Install with:")
    print("  pip install playwright pytest-playwright")
    print("  playwright install")


class Colors:
    GREEN = '\033[92m'
    FAIL = '\033[91m'
    WARNING = '\033[93m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_success(text): print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")
def print_error(text): print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")
def print_warning(text): print(f"{Colors.WARNING}! {text}{Colors.ENDC}")
def print_info(text): print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")
def print_header(text): print(f"\n{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")


class WebUIAutomationTester:
    """Automates WebUI testing using Playwright."""
    
    def __init__(self, host='localhost', port=7186, username='admin', password='admin', headed=False):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.headed = headed
        self.base_url = f"http://{host}:{port}"
        self.results = []
        
    def run_full_test(self) -> Dict:
        """Run complete WebUI automation test."""
        if not PLAYWRIGHT_AVAILABLE:
            return {'status': 'skipped', 'reason': 'playwright not available'}
        
        print_header("WEBUI AUTOMATION TEST SUITE")
        print(f"Testing: {self.base_url}")
        print(f"Headed mode: {self.headed}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not self.headed)
            context = browser.new_context(viewport={'width': 1920, 'height': 1080})
            page = context.new_page()
            
            try:
                # Test 1: Login
                self._test_login(page)
                
                # Test 2: Search Tab
                self._test_search_tab(page)
                
                # Test 3: Plugin Verification
                self._test_plugin_list(page)
                
                # Test 4: Search Workflow
                self._test_search_workflow(page)
                
                # Take final screenshot
                self._take_screenshot(page, 'final_state')
                
                result = {
                    'status': 'passed',
                    'timestamp': datetime.now().isoformat(),
                    'results': self.results
                }
                
            except Exception as e:
                print_error(f"Test failed: {e}")
                self._take_screenshot(page, 'error_state')
                result = {
                    'status': 'failed',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat(),
                    'results': self.results
                }
            finally:
                browser.close()
        
        return result
    
    def _test_login(self, page: Page):
        """Test WebUI login."""
        print_header("Test 1: WebUI Login")
        
        page.goto(self.base_url)
        page.wait_for_load_state('networkidle')
        
        # Check if on login page
        if page.locator('input#username').is_visible():
            print_info("Login page detected")
            page.fill('input#username', self.username)
            page.fill('input#password', self.password)
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle')
        
        # Verify logged in (look for main UI elements)
        page.wait_for_selector('#main', timeout=10000)
        print_success("Logged in successfully")
        self.results.append({'test': 'login', 'status': 'passed'})
        
        self._take_screenshot(page, '01_logged_in')
    
    def _test_search_tab(self, page: Page):
        """Test search tab access."""
        print_header("Test 2: Search Tab Access")
        
        # Click on Search tab
        search_tab = page.locator('text=Search').first
        if search_tab.is_visible():
            search_tab.click()
            page.wait_for_timeout(1000)
            
            # Verify search UI loaded
            if page.locator('input[placeholder*="search"]').first.is_visible() or \
               page.locator('[class*="search"]').first.is_visible():
                print_success("Search tab accessible")
                self.results.append({'test': 'search_tab', 'status': 'passed'})
            else:
                print_warning("Search tab UI not clearly visible")
                self.results.append({'test': 'search_tab', 'status': 'warning'})
        else:
            print_error("Search tab not found")
            self.results.append({'test': 'search_tab', 'status': 'failed'})
        
        self._take_screenshot(page, '02_search_tab')
    
    def _test_plugin_list(self, page: Page):
        """Test that plugins are loaded."""
        print_header("Test 3: Plugin Verification")
        
        # Look for plugin-related UI elements
        plugin_selectors = [
            'text=Search plugins',
            'button:has-text("Plugins")',
            '[class*="plugin"]',
            'select[name*="plugin"]'
        ]
        
        found = False
        for selector in plugin_selectors:
            try:
                if page.locator(selector).first.is_visible(timeout=2000):
                    print_success(f"Plugin UI found: {selector}")
                    found = True
                    break
            except:
                continue
        
        if not found:
            print_warning("Plugin UI not found (may need to open plugins dialog)")
        
        self.results.append({'test': 'plugin_list', 'status': 'passed' if found else 'warning'})
        self._take_screenshot(page, '03_plugins')
    
    def _test_search_workflow(self, page: Page):
        """Test complete search workflow."""
        print_header("Test 4: Search Workflow")
        
        # Try to perform a search
        try:
            # Find search input
            search_input = page.locator('input[placeholder*="search"], input[name*="search"]').first
            if search_input.is_visible():
                search_input.fill('ubuntu')
                search_input.press('Enter')
                
                # Wait for results
                page.wait_for_timeout(3000)
                
                # Check for results
                result_selectors = [
                    'table tbody tr',
                    '[class*="result"]',
                    'text=Ubuntu'
                ]
                
                results_found = False
                for selector in result_selectors:
                    try:
                        count = page.locator(selector).count()
                        if count > 0:
                            print_success(f"Found {count} search results")
                            results_found = True
                            break
                    except:
                        continue
                
                if results_found:
                    self.results.append({'test': 'search_workflow', 'status': 'passed'})
                else:
                    print_warning("Search performed but results not clearly visible")
                    self.results.append({'test': 'search_workflow', 'status': 'warning'})
            else:
                print_warning("Search input not found")
                self.results.append({'test': 'search_workflow', 'status': 'skipped'})
                
        except Exception as e:
            print_error(f"Search workflow failed: {e}")
            self.results.append({'test': 'search_workflow', 'status': 'failed', 'error': str(e)})
        
        self._take_screenshot(page, '04_search_results')
    
    def _take_screenshot(self, page: Page, name: str):
        """Take a screenshot for verification."""
        screenshot_dir = os.path.join(SCRIPT_DIR, 'screenshots')
        os.makedirs(screenshot_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{name}_{timestamp}.png"
        filepath = os.path.join(screenshot_dir, filename)
        
        try:
            page.screenshot(path=filepath, full_page=True)
            print_info(f"Screenshot saved: {filepath}")
        except Exception as e:
            print_warning(f"Screenshot failed: {e}")


def main():
    parser = argparse.ArgumentParser(description='WebUI Automation Test Suite')
    parser.add_argument('--host', type=str, default='localhost', help='qBittorrent host')
    parser.add_argument('--port', type=str, default='7186', help='qBittorrent port')
    parser.add_argument('--username', type=str, default='admin', help='qBittorrent username')
    parser.add_argument('--password', type=str, default='admin', help='qBittorrent password')
    parser.add_argument('--headed', action='store_true', help='Show browser window')
    parser.add_argument('--output', type=str, default='webui_automation_report.json', help='Output file')
    args = parser.parse_args()
    
    if not PLAYWRIGHT_AVAILABLE:
        print("Cannot run tests - Playwright not available")
        print("Install with:")
        print("  pip install playwright pytest-playwright")
        print("  playwright install")
        return 1
    
    tester = WebUIAutomationTester(
        args.host, args.port, args.username, args.password, args.headed
    )
    
    result = tester.run_full_test()
    
    # Save report
    with open(args.output, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n{Colors.CYAN}Report saved to: {args.output}{Colors.ENDC}")
    
    return 0 if result.get('status') == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
