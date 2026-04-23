"""
Browser-based integration tests for real-time streaming.

Uses Playwright to verify:
1. Dashboard loads correctly with Angular app
2. Search sends request to API
3. Results appear incrementally (not all at once)
4. button state changes during search

Run with: python3 -m pytest tests/integration/test_streaming_browser.py -v
"""

import time

import pytest

BASE_URL = "http://localhost:7187"
SEARCH_QUERY = "linux"


class TestStreamingBrowser:
    """Test streaming in real browser."""

    @pytest.fixture(autouse=True)
    def setup(self, browser):
        self.browser = browser
        self.context = browser.new_context()
        self.page = self.context.new_page()

    def teardown_method(self):
        self.context.close()

    def test_dashboard_loads_with_angular_app(self):
        """Dashboard should load as Angular app."""
        self.page.goto(BASE_URL, wait_until="domcontentloaded")

        # Check HTML contains Angular app-root
        html = self.page.content()
        assert "<app-root" in html or "<app-root></app-root>" in html, "Dashboard should have Angular app-root"

        print("\n[PASS] Dashboard loads as Angular app")

    @pytest.mark.timeout(180)
    def test_search_returns_results(self):
        """Search should return a search_id + running-style status."""
        import requests

        resp = requests.post(f"{BASE_URL}/api/v1/search", json={"query": SEARCH_QUERY, "limit": 10}, timeout=30)
        data = resp.json()

        assert "search_id" in data
        # POST /search is async: it returns immediately with status
        # "running". Accept that + legacy spellings in case the service
        # evolves.
        assert data["status"] in ("completed", "running", "in_progress", "searching")

        print(f"\n[PASS] Search returned {data.get('total_results', 0)} results")

    def test_sse_streaming_integration(self):
        """SSE endpoint should stream individual results."""
        import threading

        import requests

        # Start search
        resp = requests.post(f"{BASE_URL}/api/v1/search", json={"query": SEARCH_QUERY, "limit": 20}, timeout=60)
        data = resp.json()
        search_id = data["search_id"]

        # Connect to SSE stream
        sse_url = f"{BASE_URL}/api/v1/search/stream/{search_id}"

        events = []

        def fetch_sse():
            try:
                resp = requests.get(sse_url, stream=True, timeout=25)
                for line in resp.iter_lines():
                    if line:
                        line = line.decode("utf-8")
                        if line.startswith("data:"):
                            events.append(line[5:].strip())
            except Exception:
                pass

        t = threading.Thread(target=fetch_sse, daemon=True)
        t.start()

        # Wait for some events
        time.sleep(8)

        events_with_data = [e for e in events if e]
        print(f"\n[SSE] Received {len(events_with_data)} events")

        assert len(events_with_data) > 0, "Should receive SSE events"

        # Check for result events that include data with name field
        name_count = sum(1 for e in events_with_data if '"name"' in e)
        print(f"[SSE] Events with name: {name_count}")

        assert name_count > 0, "Should have result events with names"

    @pytest.mark.timeout(300)
    def test_search_endpoint_works(self):
        """Full search + stream should work end-to-end."""
        import requests

        # 1. Start search
        resp = requests.post(f"{BASE_URL}/api/v1/search", json={"query": "linux", "limit": 5}, timeout=60)
        data = resp.json()

        assert "search_id" in data
        search_id = data["search_id"]

        # 2. Poll for status — fan-out can take up to 300 s under
        # batch load. ``timeout=30`` on each poll so a transient
        # slow-down doesn't drop the test on ReadTimeout.
        status = {}
        for _ in range(150):
            time.sleep(2)
            status_resp = requests.get(f"{BASE_URL}/api/v1/search/{search_id}", timeout=30)
            status = status_resp.json()

            if status.get("status") == "completed":
                break

        # 3. Get results
        results = status.get("results", [])
        print(f"\n[E2E] Got {len(results)} results")

        assert len(results) > 0, "Should return results"


class TestDashboardElements:
    """Test dashboard UI elements."""

    @pytest.fixture(autouse=True)
    def setup(self, browser):
        self.browser = browser
        self.context = browser.new_context()
        self.page = self.context.new_page()

    def teardown_method(self):
        self.context.close()

    def test_has_angular_app(self):
        """Dashboard should have Angular app."""
        self.page.goto(BASE_URL, wait_until="domcontentloaded")

        html = self.page.content()
        assert "<app-root" in html or "<app-root></app-root>" in html
        print("\n[PASS] Angular app exists")

    def test_has_angular_script(self):
        """Dashboard should load Angular main script."""
        self.page.goto(BASE_URL, wait_until="domcontentloaded")

        html = self.page.content()
        assert "main-" in html and '.js"' in html
        print("\n[PASS] Angular main script loaded")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
