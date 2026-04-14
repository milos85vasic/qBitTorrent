#!/usr/bin/env python3
"""
qBittorrent Complete Test Runner
Comprehensive tests for UI, API, plugins, search, and download
"""

import sys
import time
import json
import requests
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:7186"
USERNAME = "admin"
PASSWORD = "admin"


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []
        self.session = None

    def log(self, test_name, status, message="", time_taken=0):
        symbol = "✓" if status == "PASS" else ("✗" if status == "FAIL" else "⊘")
        color = (
            "\033[92m"
            if status == "PASS"
            else ("\033[91m" if status == "FAIL" else "\033[93m")
        )
        reset = "\033[0m"

        self.results.append(
            {
                "test": test_name,
                "status": status,
                "message": message,
                "time": time_taken,
            }
        )

        print(f"{color}{symbol}{reset} {test_name}: {message} ({time_taken:.2f}s)")

        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        else:
            self.skipped += 1

    def print_header(self, text):
        print(f"\n{'=' * 60}")
        print(f"  {text}")
        print(f"{'=' * 60}")

    def login(self):
        """Login and store session"""
        if self.session:
            return self.session

        self.session = requests.Session()
        response = self.session.post(
            f"{BASE_URL}/api/v2/auth/login",
            data={"username": USERNAME, "password": PASSWORD},
            timeout=10,
        )
        if response.text != "Ok.":
            raise Exception(f"Login failed: {response.text}")
        return self.session


def run_all_tests():
    runner = TestRunner()
    runner.print_header("qBittorrent Complete Test Suite")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {BASE_URL}")

    # Test 1: Login Page Loads
    runner.print_header("Test 1: Login Page")
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}/", timeout=10)
        elapsed = time.time() - start

        assert response.status_code == 200
        assert "qBittorrent" in response.text
        assert 'id="username"' in response.text
        assert 'id="password"' in response.text

        runner.log("Login page loads", "PASS", f"HTTP 200, {elapsed:.2f}s", elapsed)
    except Exception as e:
        runner.log("Login page loads", "FAIL", str(e), 0)

    # Test 2: CSS Loads
    runner.print_header("Test 2: CSS Files")
    try:
        start = time.time()
        response = requests.get(f"{BASE_URL}/css/login.css", timeout=5)
        elapsed = time.time() - start

        assert response.status_code == 200
        assert len(response.text) > 0

        runner.log(
            "CSS loads", "PASS", f"{len(response.text)} bytes, {elapsed:.2f}s", elapsed
        )
    except Exception as e:
        runner.log("CSS loads", "FAIL", str(e), 0)

    # Test 3: API Login
    runner.print_header("Test 3: API Login")
    try:
        start = time.time()
        runner.login()
        elapsed = time.time() - start

        runner.log("API login", "PASS", f"{elapsed:.2f}s", elapsed)
    except Exception as e:
        runner.log("API login", "FAIL", str(e), 0)

    # Test 4: API Version
    runner.print_header("Test 4: API Version")
    try:
        start = time.time()
        session = runner.login()
        response = session.get(f"{BASE_URL}/api/v2/app/version", timeout=5)
        elapsed = time.time() - start

        version = response.text
        assert version.startswith("v")

        runner.log("API version", "PASS", f"{version}, {elapsed:.2f}s", elapsed)
    except Exception as e:
        runner.log("API version", "FAIL", str(e), 0)

    # Test 5: Plugins List
    runner.print_header("Test 5: Search Plugins")
    try:
        start = time.time()
        session = runner.login()
        response = session.get(f"{BASE_URL}/api/v2/search/plugins", timeout=10)
        plugins = response.json()
        elapsed = time.time() - start

        enabled = [p for p in plugins if p.get("enabled")]

        runner.log(
            "Plugins available",
            "PASS",
            f"{len(enabled)}/{len(plugins)} enabled",
            elapsed,
        )

        # List all plugins
        for p in plugins:
            status = "✓" if p.get("enabled") else "✗"
            print(f"    {status} {p.get('name')}: {p.get('url')}")

    except Exception as e:
        runner.log("Plugins available", "FAIL", str(e), 0)

    # Test 6: RuTracker Plugin
    runner.print_header("Test 6: RuTracker Plugin")
    try:
        start = time.time()
        session = runner.login()
        response = session.get(f"{BASE_URL}/api/v2/search/plugins", timeout=10)
        plugins = response.json()
        elapsed = time.time() - start

        rutracker = next((p for p in plugins if p.get("name") == "rutracker"), None)

        if not rutracker:
            runner.log("RuTracker plugin", "FAIL", "Not found", elapsed)
        elif not rutracker.get("enabled"):
            runner.log("RuTracker plugin", "FAIL", "Not enabled", elapsed)
        else:
            runner.log("RuTracker plugin", "PASS", "Enabled", elapsed)

    except Exception as e:
        runner.log("RuTracker plugin", "FAIL", str(e), 0)

    # Test 7: RuTracker Search
    runner.print_header("Test 7: RuTracker Search")
    try:
        start = time.time()
        session = runner.login()

        # Start search
        response = session.post(
            f"{BASE_URL}/api/v2/search/start",
            data={"pattern": "ubuntu", "plugins": "rutracker", "category": "all"},
            timeout=15,
        )
        search_id = response.json().get("id")

        if not search_id:
            raise Exception("No search ID returned")

        # Wait for results
        time.sleep(5)

        # Get results
        response = session.get(
            f"{BASE_URL}/api/v2/search/results",
            params={"id": search_id, "limit": 5},
            timeout=10,
        )
        results = response.json()

        if not results.get("results"):
            raise Exception("No results")

        elapsed = time.time() - start
        count = len(results["results"])

        runner.log("RuTracker search", "PASS", f"Found {count} results", elapsed)

        # Show first result
        first = results["results"][0]
        print(f"    First: {first['fileName'][:60]}...")

    except Exception as e:
        runner.log("RuTracker search", "FAIL", str(e), 0)

    # Test 8: Download from RuTracker
    runner.print_header("Test 8: RuTracker Download")
    try:
        start = time.time()
        session = runner.login()

        # Search first
        response = session.post(
            f"{BASE_URL}/api/v2/search/start",
            data={"pattern": "ubuntu", "plugins": "rutracker", "category": "all"},
            timeout=15,
        )
        search_id = response.json().get("id")
        time.sleep(5)

        # Get result
        response = session.get(
            f"{BASE_URL}/api/v2/search/results",
            params={"id": search_id, "limit": 1},
            timeout=10,
        )
        results = response.json()

        if not results.get("results"):
            raise Exception("No results to download")

        download_url = results["results"][0]["fileUrl"]

        # Download
        response = session.post(
            f"{BASE_URL}/api/v2/torrents/add", data={"urls": download_url}, timeout=15
        )

        if response.text != "Ok.":
            raise Exception(f"Add failed: {response.text}")

        time.sleep(2)

        # Verify in list
        response = session.get(f"{BASE_URL}/api/v2/torrents/info", timeout=10)
        torrents = response.json()

        found = False
        for t in torrents:
            if "ubuntu" in t["name"].lower():
                found = True
                torrent_name = t["name"]
                break

        if not found:
            raise Exception("Torrent not in list")

        elapsed = time.time() - start
        runner.log("RuTracker download", "PASS", f"Added: {torrent_name[:40]}", elapsed)

    except Exception as e:
        runner.log("RuTracker download", "FAIL", str(e), 0)

    # Test 9: Multiple Plugins
    runner.print_header("Test 9: Multiple Plugins Search")
    try:
        start = time.time()
        session = runner.login()

        # Get plugins
        response = session.get(f"{BASE_URL}/api/v2/search/plugins", timeout=10)
        plugins = [p["name"] for p in response.json() if p.get("enabled")][:3]

        if len(plugins) < 2:
            runner.log(
                "Multi-plugin search", "SKIP", f"Only {len(plugins)} plugins", elapsed
            )
        else:
            # Search
            response = session.post(
                f"{BASE_URL}/api/v2/search/start",
                data={
                    "pattern": "test",
                    "plugins": ",".join(plugins),
                    "category": "all",
                },
                timeout=15,
            )
            search_id = response.json().get("id")
            time.sleep(5)

            response = session.get(
                f"{BASE_URL}/api/v2/search/results",
                params={"id": search_id, "limit": 5},
                timeout=10,
            )
            results = response.json()

            elapsed = time.time() - start
            total = results.get("total", 0)

            runner.log(
                "Multi-plugin search",
                "PASS",
                f"{total} results from {len(plugins)} plugins",
                elapsed,
            )

    except Exception as e:
        runner.log("Multi-plugin search", "FAIL", str(e), 0)

    # Test 10: API Performance
    runner.print_header("Test 10: API Performance")
    try:
        session = runner.login()

        endpoints = [
            "/api/v2/app/version",
            "/api/v2/transfer/info",
            "/api/v2/torrents/info",
            "/api/v2/search/plugins",
        ]

        all_fast = True
        for endpoint in endpoints:
            start_ep = time.time()
            response = session.get(f"{BASE_URL}{endpoint}", timeout=5)
            elapsed_ep = time.time() - start_ep

            if elapsed_ep < 1.0:
                runner.log(
                    f"API {endpoint.split('/')[-1]}",
                    "PASS",
                    f"{elapsed_ep:.3f}s",
                    elapsed_ep,
                )
            else:
                runner.log(
                    f"API {endpoint.split('/')[-1]}",
                    "FAIL",
                    f"{elapsed_ep:.3f}s (too slow)",
                    elapsed_ep,
                )
                all_fast = False

    except Exception as e:
        runner.log("API Performance", "FAIL", str(e), 0)

    # Summary
    runner.print_header("Test Summary")
    print(f"  Passed:  {runner.passed}")
    print(f"  Failed:  {runner.failed}")
    print(f"  Skipped: {runner.skipped}")
    print(f"  Total:   {runner.passed + runner.failed + runner.skipped}")

    if runner.failed > 0:
        print(f"\n❌ Some tests failed!")
        return 1
    else:
        print(f"\n✅ All tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())
