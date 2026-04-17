import sys
import os
import json
import asyncio
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))

from api.streaming import SSEHandler


class TestSSEHandler:
    def test_format_event_basic(self):
        result = SSEHandler.format_event(event="test_event", data={"key": "value"})
        assert "event: test_event" in result
        assert "data: " in result
        assert '"key"' in result
        assert '"value"' in result
        assert result.endswith("\n")

    def test_format_event_with_id(self):
        result = SSEHandler.format_event(event="test_event", data={"x": 1}, event_id="abc-123")
        assert "id: abc-123" in result
        assert "event: test_event" in result

    def test_format_event_multiline_data(self):
        result = SSEHandler.format_event(event="test", data={"msg": "line1\nline2"})
        assert "line1" in result
        assert "line2" in result

    def test_format_event_empty_event(self):
        result = SSEHandler.format_event(event="", data={"k": "v"})
        assert "event:" not in result
        assert "data:" in result

    def test_search_results_stream_not_found(self):
        class FakeOrchestrator:
            def get_search_status(self, sid):
                return None

        gen = SSEHandler.search_results_stream("bad-id", FakeOrchestrator())
        events = asyncio.run(self._collect(gen))
        assert len(events) == 2
        assert '"error"' in events[1]

    def test_search_results_stream_completed(self):
        class FakeMeta:
            status = "completed"
            total_results = 5
            merged_results = 3
            trackers_searched = ["rutracker"]

            def to_dict(self):
                return {"status": "completed", "total_results": 5}

        class FakeOrchestrator:
            def get_search_status(self, sid):
                return FakeMeta()

        gen = SSEHandler.search_results_stream("sid", FakeOrchestrator(), poll_interval=0)
        events = asyncio.run(self._collect(gen))
        assert any("search_start" in e for e in events)
        assert any("search_complete" in e for e in events)

    def test_download_progress_stream_not_found(self):
        gen = SSEHandler.download_progress_stream("dl-id", lambda x: None, poll_interval=0)
        events = asyncio.run(self._collect(gen))
        assert len(events) == 2
        assert any("download_start" in e for e in events)
        assert any("download_complete" in e for e in events)

    def test_download_progress_stream_complete(self):
        call_count = 0

        def get_progress(dl_id):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                return None
            return {"progress": 50, "complete": False}

        gen = SSEHandler.download_progress_stream("dl-id", get_progress, poll_interval=0)
        events = asyncio.run(self._collect(gen))
        assert len(events) >= 2

    def test_create_streaming_response(self):
        async def fake_gen():
            yield "data: test\n\n"

        response = SSEHandler.create_streaming_response(fake_gen())
        assert response.media_type == "text/event-stream"
        assert response.headers["Cache-Control"] == "no-cache"
        assert response.headers["Connection"] == "keep-alive"

    async def _collect(self, gen):
        results = []
        async for item in gen:
            results.append(item)
        return results


class TestRealTimeStreaming:
    """Tests for real-time streaming of individual search results."""

    async def _collect_limit(self, gen, max_iterations=20):
        results = []
        async for item in gen:
            results.append(item)
            if len(results) >= max_iterations:
                break
        return results

    def test_streaming_yields_individual_results(self):
        """Test that search_results_stream yields individual results as they arrive, not just counts."""

        class FakeResult:
            hash = "abc123"
            name = "Test Movie 2023 1080p"
            seeds = 100
            tracker = "rutracker"

        call_count = [0]

        class FakeMeta:
            status = "running"
            total_results = 1
            merged_results = 0
            trackers_searched = ["rutracker"]

            def to_dict(self):
                return {"status": "running", "total_results": 1}

        class FakeOrchestrator:
            def get_search_status(self, sid):
                call_count[0] += 1
                if call_count[0] > 3:
                    m = FakeMeta()
                    m.status = "completed"
                    return m
                return FakeMeta()

            def get_live_results(self, sid):
                return [FakeResult()]

        gen = SSEHandler.search_results_stream("sid", FakeOrchestrator(), poll_interval=0)
        events = asyncio.run(self._collect_limit(gen))
        has_result_found = any("result_found" in e for e in events)
        assert has_result_found, "Should emit result_found event with individual result data"

    def test_streaming_result_contains_result_details(self):
        """Test that result_found event contains actual result details (name, seeds, tracker)."""
        call_count = [0]

        class FakeResult:
            hash = "def456"
            name = "Awesome Film 2024 4K"
            seeds = 250
            leechers = 50
            tracker = "kinozal"

        class FakeMeta:
            status = "running"
            total_results = 1
            merged_results = 0
            trackers_searched = ["kinozal"]

            def to_dict(self):
                return {"status": "running", "total_results": 1}

        class FakeOrchestrator:
            def get_search_status(self, sid):
                call_count[0] += 1
                if call_count[0] > 3:
                    m = FakeMeta()
                    m.status = "completed"
                    return m
                return FakeMeta()

            def get_live_results(self, sid):
                return [FakeResult()]

        gen = SSEHandler.search_results_stream("sid", FakeOrchestrator(), poll_interval=0)
        events = asyncio.run(self._collect_limit(gen))
        result_events = [e for e in events if "result_found" in e]
        assert len(result_events) > 0, "Should have result_found event"
        assert "Awesome Film" in result_events[0], "Result should contain name"

    def test_streaming_shows_trackers_as_they_complete(self):
        """Test that results_update events show which trackers have completed."""
        call_count = [0]

        class FakeMeta:
            status = "running"
            total_results = 10
            merged_results = 5
            trackers_searched = ["rutracker", "kinozal"]

            def to_dict(self):
                return {"status": "running", "total_results": 10, "trackers_searched": ["rutracker", "kinozal"]}

        class FakeOrchestrator:
            def get_search_status(self, sid):
                call_count[0] += 1
                if call_count[0] > 3:
                    m = FakeMeta()
                    m.status = "completed"
                    return m
                return FakeMeta()

            def get_live_results(self, sid):
                return []

        gen = SSEHandler.search_results_stream("sid", FakeOrchestrator(), poll_interval=0)
        events = asyncio.run(self._collect_limit(gen))
        update_events = [e for e in events if "results_update" in e]
        assert len(update_events) > 0, "Should have results_update events"
        has_trackers = any("rutracker" in e or "kinozal" in e for e in update_events)
        assert has_trackers, "Should show which trackers have been searched"
