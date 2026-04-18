"""
SSE exits cleanly when the client disconnects.

Previous behaviour: `while True: await asyncio.sleep(0.5)` kept polling the
orchestrator until the search metadata expired, wasting CPU on dropped
connections.

New contract: each iteration must check ``await request.is_disconnected()``
and break cleanly.  A trailing ``event: close`` sentinel is emitted on the
way out so downstream instrumentation can observe the shutdown.

``request`` is an optional kwarg to preserve backwards compatibility for
existing callers that do not pass one.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


def _reimport_streaming():
    for k in [k for k in list(sys.modules) if k == "api" or k.startswith("api.")]:
        del sys.modules[k]
    sys.modules.setdefault("api", type(sys)("api"))
    spec = importlib.util.spec_from_file_location(
        "api.streaming", os.path.join(_SRC_PATH, "api", "streaming.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["api.streaming"] = mod
    spec.loader.exec_module(mod)
    return mod


class _RunningOrch:
    """Orchestrator stub that stays 'running' forever — only a disconnect
    should end the stream."""

    def get_search_status(self, sid):
        return SimpleNamespace(
            status="running",
            total_results=0,
            merged_results=0,
            trackers_searched=[],
            to_dict=lambda: {"status": "running"},
        )

    def get_live_results(self, sid):
        return []


@pytest.mark.asyncio
async def test_search_stream_exits_after_disconnect():
    streaming_mod = _reimport_streaming()
    SSEHandler = streaming_mod.SSEHandler

    # Sequence: False, False, True -> exit on the third check.
    request = SimpleNamespace(is_disconnected=AsyncMock(side_effect=[False, False, True]))

    gen = SSEHandler.search_results_stream(
        "sid-x", _RunningOrch(), poll_interval=0.001, request=request
    )

    events = []
    async for evt in gen:
        events.append(evt)

    # Generator must have terminated (no infinite loop).
    assert any("event: close" in e for e in events), (
        f"expected a trailing 'event: close' sentinel, got: {events!r}"
    )

    # is_disconnected was consulted until it returned True.
    assert request.is_disconnected.await_count >= 3


@pytest.mark.asyncio
async def test_search_stream_still_works_without_request():
    """Backwards compat: existing callers omit the request kwarg."""
    streaming_mod = _reimport_streaming()
    SSEHandler = streaming_mod.SSEHandler

    class _CompleteOrch:
        def get_search_status(self, sid):
            return SimpleNamespace(
                status="completed",
                total_results=0,
                merged_results=0,
                trackers_searched=[],
                to_dict=lambda: {"status": "completed"},
            )

        def get_live_results(self, sid):
            return []

    gen = SSEHandler.search_results_stream("sid-y", _CompleteOrch(), poll_interval=0.001)
    events = [e async for e in gen]
    # Should terminate on completed status without needing a request.
    assert any("event: search_complete" in e for e in events)


@pytest.mark.asyncio
async def test_download_progress_stream_exits_on_disconnect():
    streaming_mod = _reimport_streaming()
    SSEHandler = streaming_mod.SSEHandler

    request = SimpleNamespace(is_disconnected=AsyncMock(side_effect=[False, True]))

    def get_progress(download_id: str):
        # Never complete — only the disconnect should end the loop.
        return {"complete": False, "percent": 10}

    gen = SSEHandler.download_progress_stream(
        "dl-1", get_progress, poll_interval=0.001, request=request
    )
    events = [e async for e in gen]
    assert any("event: close" in e for e in events)
    assert request.is_disconnected.await_count >= 2
