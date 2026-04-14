import sys
import os
import json
import asyncio
import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src")
)

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
        result = SSEHandler.format_event(
            event="test_event", data={"x": 1}, event_id="abc-123"
        )
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
        events = asyncio.get_event_loop().run_until_complete(self._collect(gen))
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

        gen = SSEHandler.search_results_stream(
            "sid", FakeOrchestrator(), poll_interval=0
        )
        events = asyncio.get_event_loop().run_until_complete(self._collect(gen))
        assert any("search_start" in e for e in events)
        assert any("search_complete" in e for e in events)

    def test_download_progress_stream_not_found(self):
        gen = SSEHandler.download_progress_stream(
            "dl-id", lambda x: None, poll_interval=0
        )
        events = asyncio.get_event_loop().run_until_complete(self._collect(gen))
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

        gen = SSEHandler.download_progress_stream(
            "dl-id", get_progress, poll_interval=0
        )
        events = asyncio.get_event_loop().run_until_complete(self._collect(gen))
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
