"""Verify Phase-3 TTL caches stay bounded under sustained load.

tracemalloc delta between N=0 and N=10_000 inserts must not grow
unboundedly for _active_searches, _last_merged_results, or
_pending_captchas.

Hitting the live service isn't needed — we import the orchestrator
in-process and push rows directly.
"""

from __future__ import annotations

import os
import sys
import tracemalloc
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "download-proxy" / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost")
os.environ.setdefault("MAX_ACTIVE_SEARCHES", "32")

pytestmark = pytest.mark.memory


def _fresh_orchestrator():
    # Re-import so MAX_ACTIVE_SEARCHES env override sticks per-test.
    for mod_name in [k for k in list(sys.modules) if k.startswith("merge_service")]:
        del sys.modules[mod_name]
    from merge_service.search import SearchOrchestrator

    return SearchOrchestrator()


def test_active_searches_cache_bounded_by_maxsize(monkeypatch):
    monkeypatch.setenv("MAX_ACTIVE_SEARCHES", "32")
    orch = _fresh_orchestrator()

    class _Dummy:
        search_id = "x"

    for i in range(500):
        orch._active_searches[f"id-{i}"] = _Dummy()

    # TTLCache caps to maxsize; assert we never exceed the cap.
    assert len(orch._active_searches) <= 32


def test_last_merged_results_cache_bounded(monkeypatch):
    monkeypatch.setenv("MAX_ACTIVE_SEARCHES", "16")
    orch = _fresh_orchestrator()

    for i in range(200):
        orch._last_merged_results[f"id-{i}"] = ([], [])

    assert len(orch._last_merged_results) <= 16


def test_pending_captchas_cache_bounded(monkeypatch):
    monkeypatch.setenv("PENDING_CAPTCHAS_MAX", "8")
    # Reload the module to pick up the new env var.
    import importlib

    from api import auth as auth_mod

    importlib.reload(auth_mod)

    for i in range(64):
        auth_mod._pending_captchas[f"sess-{i}"] = {"answer": None}

    assert len(auth_mod._pending_captchas) <= 8


def test_tracker_sessions_cache_bounded_by_maxsize(monkeypatch):
    monkeypatch.setenv("MAX_ACTIVE_SEARCHES", "16")
    orch = _fresh_orchestrator()

    for i in range(500):
        orch._tracker_sessions[f"session-{i}"] = {"cookies": {}, "base_url": "https://example.com"}

    assert len(orch._tracker_sessions) <= 16


def test_tracker_results_cache_bounded_by_maxsize(monkeypatch):
    monkeypatch.setenv("MAX_ACTIVE_SEARCHES", "16")
    orch = _fresh_orchestrator()

    for i in range(500):
        orch._tracker_results[f"search-{i}"] = {"tracker": []}

    assert len(orch._tracker_results) <= 16


def test_tracemalloc_orchestrator_insert_does_not_grow_unbounded(monkeypatch):
    """Insert 10k items into _active_searches; allocated bytes must not
    grow linearly with N once the cache cap is reached.
    """
    monkeypatch.setenv("MAX_ACTIVE_SEARCHES", "64")
    orch = _fresh_orchestrator()

    tracemalloc.start()
    baseline = tracemalloc.take_snapshot()

    class _Dummy:
        search_id = "x"

    for i in range(10_000):
        orch._active_searches[f"id-{i}"] = _Dummy()

    peak = tracemalloc.take_snapshot()
    tracemalloc.stop()

    diff = peak.compare_to(baseline, "lineno")
    # Sum size_diff across all frames — the cache cap (64 entries)
    # should keep this well below a linear 10k-entries growth. 1 MiB
    # is a generous ceiling.
    total_delta = sum(s.size_diff for s in diff)
    assert total_delta < 1_000_000, f"tracemalloc delta grew {total_delta} bytes — cache not bounded?"
