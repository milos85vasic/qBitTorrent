"""The SSE poll loop emits tracker_started / tracker_completed events.

We feed the streamer a hand-rolled orchestrator whose
``get_search_status()`` returns a metadata object whose tracker_stats
flip between iterations.  A minimum viable sequence:

    iter 1: alpha=pending, beta=running          -> emit tracker_started(beta)
    iter 2: alpha=running, beta=success          -> emit tracker_started(alpha),
                                                     tracker_completed(beta)
    iter 3: alpha=success, beta=success, status=completed  -> emit
                                                     tracker_completed(alpha)
                                                     then search_complete
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
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
    fake_api.__path__ = [os.path.join(_SRC_PATH, "api")]  # type: ignore[attr-defined]
    sys.modules["api"] = fake_api
    spec = importlib.util.spec_from_file_location(
        "api.streaming", os.path.join(_SRC_PATH, "api", "streaming.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["api.streaming"] = mod
    spec.loader.exec_module(mod)
    return mod


class _Stat:
    def __init__(self, name, status, results_count=0, error=None, error_type=None):
        self.name = name
        self.status = status
        self.results_count = results_count
        self.error = error
        self.error_type = error_type

    def to_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "results_count": self.results_count,
            "error": self.error,
            "error_type": self.error_type,
        }


class _MetadataStub:
    def __init__(self, status, total_results, tracker_stats):
        self.status = status
        self.total_results = total_results
        self.merged_results = 0
        self.trackers_searched = list(tracker_stats.keys())
        self.tracker_stats = tracker_stats

    def to_dict(self):
        return {
            "status": self.status,
            "total_results": self.total_results,
            "merged_results": self.merged_results,
            "trackers_searched": self.trackers_searched,
            "tracker_stats": [s.to_dict() for s in self.tracker_stats.values()],
        }


class _ScriptedOrch:
    """Returns a scripted sequence of metadata snapshots each time
    ``get_search_status()`` is called.  Any extra calls past the end
    of the script return the final snapshot."""

    def __init__(self, snapshots):
        self._snapshots = snapshots
        self._i = 0

    def get_search_status(self, _sid):
        snap = self._snapshots[min(self._i, len(self._snapshots) - 1)]
        self._i += 1
        return snap

    def get_live_results(self, _sid):
        return []


@pytest.mark.asyncio
async def test_streamer_emits_tracker_started_and_completed():
    streaming_mod = _reimport_streaming()
    SSEHandler = streaming_mod.SSEHandler

    snapshots = [
        _MetadataStub(
            status="running",
            total_results=0,
            tracker_stats={
                "alpha": _Stat("alpha", "pending"),
                "beta": _Stat("beta", "running"),
            },
        ),
        _MetadataStub(
            status="running",
            total_results=3,
            tracker_stats={
                "alpha": _Stat("alpha", "running"),
                "beta": _Stat("beta", "success", results_count=3),
            },
        ),
        _MetadataStub(
            status="completed",
            total_results=5,
            tracker_stats={
                "alpha": _Stat("alpha", "success", results_count=2),
                "beta": _Stat("beta", "success", results_count=3),
            },
        ),
    ]
    orch = _ScriptedOrch(snapshots)

    gen = SSEHandler.search_results_stream("sid-x", orch, poll_interval=0.001)
    events = [e async for e in gen]

    # Must see at least one tracker_started and one tracker_completed.
    assert any("event: tracker_started" in e for e in events), events
    assert any("event: tracker_completed" in e for e in events), events

    # Order: the initial running scan emits tracker_started for beta
    # before the success flip fires tracker_completed for beta.
    started_idx = next(i for i, e in enumerate(events) if "event: tracker_started" in e)
    completed_idx = next(i for i, e in enumerate(events) if "event: tracker_completed" in e)
    assert started_idx < completed_idx

    # Final event must be search_complete.
    assert "event: search_complete" in events[-1]


@pytest.mark.asyncio
async def test_streamer_emits_each_transition_exactly_once():
    """pending→running flips once, terminal status flips once — even if
    the same status is observed in multiple poll iterations."""
    streaming_mod = _reimport_streaming()
    SSEHandler = streaming_mod.SSEHandler

    stat = _Stat("alpha", "pending")
    meta_running_1 = _MetadataStub("running", 0, {"alpha": stat})
    stat_running = _Stat("alpha", "running")
    meta_running_2 = _MetadataStub("running", 0, {"alpha": stat_running})
    meta_running_3 = _MetadataStub("running", 0, {"alpha": stat_running})
    stat_success = _Stat("alpha", "success", results_count=4)
    meta_running_4 = _MetadataStub("running", 4, {"alpha": stat_success})
    meta_done = _MetadataStub("completed", 4, {"alpha": stat_success})

    snapshots = [meta_running_1, meta_running_2, meta_running_3, meta_running_4, meta_done]
    orch = _ScriptedOrch(snapshots)
    gen = SSEHandler.search_results_stream("sid-y", orch, poll_interval=0.001)
    events = [e async for e in gen]

    started = [e for e in events if "event: tracker_started" in e]
    completed = [e for e in events if "event: tracker_completed" in e]
    assert len(started) == 1, started
    assert len(completed) == 1, completed


@pytest.mark.asyncio
async def test_streamer_tolerates_missing_tracker_stats():
    """Orchestrators that predate tracker_stats keep working."""
    streaming_mod = _reimport_streaming()
    SSEHandler = streaming_mod.SSEHandler

    class _OldMeta:
        status = "completed"
        total_results = 0
        merged_results = 0
        trackers_searched = []

        def to_dict(self):
            return {"status": "completed"}

    class _OldOrch:
        def get_search_status(self, _sid):
            return _OldMeta()

        def get_live_results(self, _sid):
            return []

    gen = SSEHandler.search_results_stream("sid-z", _OldOrch(), poll_interval=0.001)
    events = [e async for e in gen]
    # No tracker_started/completed events, but should still complete.
    assert not any("event: tracker_started" in e for e in events)
    assert any("event: search_complete" in e for e in events)
