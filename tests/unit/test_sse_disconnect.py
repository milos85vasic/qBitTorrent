"""
SSE generator must stop promptly when the consumer task is cancelled.

Previous behaviour: `while True: await asyncio.sleep(0.5)` loops kept
polling the orchestrator even after the client disconnected, because the
loop had no cancellation-awareness.

New contract: when the consuming task is cancelled (CancelledError), the
generator must exit within a bounded time so the server doesn't leak
coroutines on dropped connections.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


@pytest.fixture(autouse=True)
def _restore_api_modules():
    saved = {k: v for k, v in sys.modules.items() if k == "api" or k.startswith("api.")}
    try:
        yield
    finally:
        for k in [k for k in list(sys.modules) if k == "api" or k.startswith("api.")]:
            del sys.modules[k]
        sys.modules.update(saved)


def _reimport_streaming():
    for k in [k for k in list(sys.modules) if k == "api" or k.startswith("api.")]:
        del sys.modules[k]
    fake_api = type(sys)("api")
    fake_api.__path__ = [os.path.join(_SRC_PATH, "api")]
    sys.modules["api"] = fake_api
    spec = importlib.util.spec_from_file_location(
        "api.streaming", os.path.join(_SRC_PATH, "api", "streaming.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["api.streaming"] = mod
    spec.loader.exec_module(mod)
    return mod


class _RunningOrch:
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
async def test_search_stream_exits_on_task_cancel():
    """Cancelling the consumer task must terminate the SSE generator within 1 second."""
    streaming_mod = _reimport_streaming()
    SSEHandler = streaming_mod.SSEHandler

    gen = SSEHandler.search_results_stream(
        "sid-cancel", _RunningOrch(), poll_interval=0.1
    )

    collected: list[str] = []

    async def consume():
        async for evt in gen:
            collected.append(evt)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.3)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1.0)

    assert not task.cancelled() or task.done()
