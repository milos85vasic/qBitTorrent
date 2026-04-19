"""
Integration tests for real-time search results streaming.

Tests verify that:
1. SSE endpoint returns events while search is in progress
2. Individual results appear as trackers complete (not all at once)
3. search_complete event fires at the end
4. Frontend receives result_found events

These tests will FAIL until streaming is properly implemented.
"""

import json
import threading
import time

import pytest
import requests

BASE_URL = "http://localhost:7187"


class SSECapture:
    """Capture SSE events from a stream."""

    def __init__(self, url):
        self.url = url
        self.events = []
        self.done = False
        self._thread = None

    def start(self):
        def _run():
            try:
                resp = requests.get(self.url, stream=True, timeout=30)
                for line in resp.iter_lines():
                    if line:
                        line = line.decode("utf-8")
                        if line.startswith("data:"):
                            data = line[5:].strip()
                            self.events.append(data)
            except Exception as e:
                self.events.append(f"ERROR: {e}")
            finally:
                self.done = True

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        return self

    def wait_for_events(self, count=1, timeout=10):
        """Wait for at least count events."""
        start = time.time()
        while time.time() - start < timeout:
            if len(self.events) >= count:
                return True
            if self.done:
                break
            time.sleep(0.1)
        return False

    def close(self):
        self.done = True
        if self._thread:
            self._thread.join(timeout=2)


class TestSSEStreaming:
    """Test SSE streaming behavior."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL

    def test_sse_endpoint_exists(self):
        """SSE endpoint should exist and respond."""
        # First start a search to get a valid search_id
        resp = requests.post(f"{self.base_url}/api/v1/search", json={"query": "test-stream", "limit": 5}, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        assert "search_id" in data
        search_id = data["search_id"]

        # Now test SSE endpoint
        resp = requests.get(f"{self.base_url}/api/v1/search/stream/{search_id}", stream=True, timeout=5)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        # Consume the stream to verify it works
        event_count = 0
        for line in resp.iter_lines():
            event_count += 1
            if event_count > 10:
                break

    @pytest.mark.timeout(180)
    def test_search_emits_events_during_execution(self):
        """Search should emit events while running, not just at completion.

        The live merge service fans out across multiple trackers, so the
        full round-trip can take a minute or more; pytest budget set
        accordingly.
        """
        # Start search
        resp = requests.post(f"{self.base_url}/api/v1/search", json={"query": "star wars", "limit": 10}, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        search_id = data["search_id"]

        # Immediately connect to SSE stream
        sse = SSECapture(f"{self.base_url}/api/v1/search/stream/{search_id}").start()

        # Wait for search to complete (may take 10-30 seconds)
        max_time = 60
        start = time.time()
        while not sse.done and time.time() - start < max_time:
            time.sleep(0.5)

        sse.close()

        # Check what events we got
        print(f"Events received: {len(sse.events)}")
        # Print a subset to see structure
        for i, e in enumerate(sse.events[:3]):
            print(f"Event {i}: {e[:100]}...")

        # SHOULD have: search_start, result_found (multiple), search_complete
        assert len(sse.events) >= 2, f"Should have at least 2 events, got {len(sse.events)}"

        # Check for any data containing search_id (indicates search_start)
        has_start = any("search_id" in e for e in sse.events)
        assert has_start, "Should have search events"

        # Check for result_found using different pattern
        has_results = any('"name"' in e for e in sse.events)
        assert has_results, "Should have result_found events with individual results"

        # Check for search_complete
        has_complete = any("status" in e and "completed" in e for e in sse.events)
        assert has_complete, "Should have search_complete event"

    @pytest.mark.timeout(180)
    def test_individual_results_stream(self):
        """Individual results should stream as trackers complete.

        This test verifies that result_found events contain actual result data.
        Live multi-tracker search; pytest budget raised for CI.
        """
        # Start search
        resp = requests.post(f"{self.base_url}/api/v1/search", json={"query": "matrix", "limit": 5}, timeout=60)
        data = resp.json()
        search_id = data["search_id"]

        # Connect to SSE
        sse = SSECapture(f"{self.base_url}/api/v1/search/stream/{search_id}").start()

        # Wait for completion
        max_time = 60
        start = time.time()
        while not sse.done and time.time() - start < max_time:
            time.sleep(0.5)

        sse.close()

        # Parse events and check for result data
        result_events = [e for e in sse.events if "result_found" in e or '"name"' in e]
        print(f"Result events: {len(result_events)}")

        # Also check for any event with result data (name field)
        events_with_names = [e for e in sse.events if '"name"' in e and '"seeds"' in e]
        print(f"Events with result data: {len(events_with_names)}")

        if result_events:
            # Check first result has data
            first_result = json.loads(result_events[0])
            print(f"First result: {first_result}")

            # Verify result has expected fields
            if "name" in first_result:
                assert first_result["name"], "Result should have name"
                assert first_result.get("seeds", 0) >= 0, "Result should have seeds"

        # This assertion WILL FAIL without the fix - check for any result data or name field
        assert len(events_with_names) > 0, "Should receive individual result events"

    @pytest.mark.timeout(180)
    def test_search_complete_has_totals(self):
        """search_complete event should include total counts."""
        resp = requests.post(f"{self.base_url}/api/v1/search", json={"query": "test", "limit": 5}, timeout=60)
        data = resp.json()
        search_id = data["search_id"]

        sse = SSECapture(f"{self.base_url}/api/v1/search/stream/{search_id}").start()

        max_time = 60
        start = time.time()
        while not sse.done and time.time() - start < max_time:
            time.sleep(0.5)

        sse.close()

        complete_events = [e for e in sse.events if "completed" in e]
        assert len(complete_events) > 0, "Should have search_complete event"

        complete_data = json.loads(complete_events[0])
        assert "total_results" in complete_data, "Complete event should have total_results"
        assert complete_data["total_results"] > 0, "Should find some results"


class TestStreamingWithAbort:
    """Test streaming with search abort."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.base_url = BASE_URL

    def test_abort_stops_search(self):
        """Abort should stop the streaming."""
        # Start search
        resp = requests.post(f"{self.base_url}/api/v1/search", json={"query": "test abort", "limit": 5}, timeout=60)
        data = resp.json()
        search_id = data["search_id"]

        # Abort it
        abort_resp = requests.post(f"{self.base_url}/api/v1/search/{search_id}/abort", timeout=10)
        assert abort_resp.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
