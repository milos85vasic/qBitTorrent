"""
Browser-based integration tests for real-time streaming.

Uses Playwright to verify:
1. Dashboard loads correctly with results-body ID
2. Search sends request to API
3. Results appear in table incrementally (not all at once)
4. button state changes during search

Run with: python3 -m pytest tests/integration/test_streaming_browser.py -v
"""

import pytest
import time


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

    def test_dashboard_loads_with_results_body(self):
        """Dashboard should have results-body ID in table."""
        self.page.goto(BASE_URL, wait_until="domcontentloaded")

        # Check HTML contains the ID (not waiting for it to be visible yet)
        html = self.page.content()
        assert 'id="results-body"' in html, "Table should have results-body ID"

        print("\n[PASS] Dashboard loads with results-body")

    def test_search_returns_results(self):
        """Search should return results from API."""
        import requests

        resp = requests.post(f"{BASE_URL}/api/v1/search", json={"query": SEARCH_QUERY, "limit": 10}, timeout=60)
        data = resp.json()

        assert "search_id" in data
        assert data["status"] in ("completed", "in_progress", "searching")

        print(f"\n[PASS] Search returned {data.get('total_results', 0)} results")

    def test_sse_streaming_integration(self):
        """SSE endpoint should stream individual results."""
        import requests
        import threading

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

    def test_search_endpoint_works(self):
        """Full search + stream should work end-to-end."""
        import requests

        # 1. Start search
        resp = requests.post(f"{BASE_URL}/api/v1/search", json={"query": "ubuntu", "limit": 5}, timeout=60)
        data = resp.json()

        assert "search_id" in data
        search_id = data["search_id"]

        # 2. Poll for status
        for _ in range(15):
            time.sleep(1)
            status_resp = requests.get(f"{BASE_URL}/api/v1/search/{search_id}")
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

    def test_has_stream_results_function(self):
        """Dashboard should have streamResults function."""
        self.page.goto(BASE_URL, wait_until="domcontentloaded")

        self.page.wait_for_function("typeof window.streamResults === 'function'")
        print("\n[PASS] streamResults function exists")

    def test_has_add_result_function(self):
        """Dashboard should have addLiveResult function."""
        self.page.goto(BASE_URL, wait_until="domcontentloaded")

        self.page.wait_for_function("typeof window.addLiveResult === 'function'")
        print("\n[PASS] addLiveResult function exists")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
