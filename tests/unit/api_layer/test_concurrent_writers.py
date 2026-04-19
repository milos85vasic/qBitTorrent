"""
Lock around concurrent appenders.

Two hazards:

1. ``hooks._execution_logs`` is mutated from async handlers that can race.
   It must be a bounded `deque` with a `maxlen` (env ``HOOK_LOG_MAXLEN``,
   default 500) and all mutations must be serialised by an asyncio.Lock.

2. ``streaming.SSEHandler.search_results_stream`` keeps a per-generator
   ``seen_hashes`` set — since two concurrent SSE clients must not share
   state, the set must NOT be elevated to module scope.
"""

from __future__ import annotations

import asyncio
import collections
import importlib.util
import inspect
import os
import sys
from types import SimpleNamespace

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")

if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


@pytest.fixture(autouse=True)
def _restore_api_modules():
    """Restore the `api.*` module graph after every test.

    Each ``_reimport_*`` helper below stubs the ``api`` package so that
    importing ``api.hooks`` / ``api.streaming`` does NOT trigger the real
    ``api/__init__.py`` (which spins up FastAPI). Without this fixture
    that stub would leak into later tests, replacing the real ``api``
    package with a bare module and breaking every ``from api.X import Y``
    that comes after — hence the cross-suite pollution we used to see.
    """
    saved = {k: v for k, v in sys.modules.items() if k == "api" or k.startswith("api.")}
    try:
        yield
    finally:
        for k in [k for k in list(sys.modules) if k == "api" or k.startswith("api.")]:
            del sys.modules[k]
        sys.modules.update(saved)


def _install_fake_api_package() -> None:
    """Install a namespace-package-shaped ``api`` module.

    Giving the stub a ``__path__`` means Python's import machinery still
    treats ``api`` as a *package* (so ``from api.routes import X`` works
    if something later needs it), while ``api/__init__.py`` is never
    executed — avoiding FastAPI startup during unit tests.
    """
    for k in [k for k in list(sys.modules) if k == "api" or k.startswith("api.")]:
        del sys.modules[k]
    fake_api = type(sys)("api")
    fake_api.__path__ = [os.path.join(_SRC_PATH, "api")]  # type: ignore[attr-defined]
    sys.modules["api"] = fake_api


def _reimport_hooks(env=None):
    _install_fake_api_package()
    spec = importlib.util.spec_from_file_location(
        "api.hooks", os.path.join(_SRC_PATH, "api", "hooks.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["api.hooks"] = mod
    spec.loader.exec_module(mod)
    return mod


def _reimport_streaming():
    _install_fake_api_package()
    spec = importlib.util.spec_from_file_location(
        "api.streaming", os.path.join(_SRC_PATH, "api", "streaming.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["api.streaming"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_execution_logs_is_bounded_deque(monkeypatch):
    monkeypatch.setenv("HOOK_LOG_MAXLEN", "50")
    hooks_mod = _reimport_hooks()

    assert isinstance(hooks_mod._execution_logs, collections.deque)
    assert hooks_mod._execution_logs.maxlen == 50


def test_execution_logs_lock_exists(monkeypatch):
    monkeypatch.setenv("HOOK_LOG_MAXLEN", "500")
    hooks_mod = _reimport_hooks()

    assert hasattr(hooks_mod, "_execution_logs_lock"), (
        "hooks module must expose an asyncio.Lock named _execution_logs_lock"
    )
    assert isinstance(hooks_mod._execution_logs_lock, asyncio.Lock)


def test_append_hook_log_helper_exists_and_is_coroutine(monkeypatch):
    monkeypatch.setenv("HOOK_LOG_MAXLEN", "500")
    hooks_mod = _reimport_hooks()

    fn = getattr(hooks_mod, "append_hook_log", None)
    assert fn is not None, "append_hook_log() helper must exist"
    assert inspect.iscoroutinefunction(fn)


@pytest.mark.asyncio
async def test_200_concurrent_appends_self_bound(monkeypatch):
    monkeypatch.setenv("HOOK_LOG_MAXLEN", "80")
    hooks_mod = _reimport_hooks()

    async def writer(i: int):
        await hooks_mod.append_hook_log({"i": i})

    await asyncio.gather(*[writer(i) for i in range(200)])

    assert len(hooks_mod._execution_logs) <= 80
    # No entry should be partially constructed / None / missing the key.
    for entry in hooks_mod._execution_logs:
        assert isinstance(entry, dict) and "i" in entry


@pytest.mark.asyncio
async def test_two_concurrent_sse_streams_do_not_share_seen_hashes(monkeypatch):
    streaming_mod = _reimport_streaming()

    def _make_results(hashes):
        return [SimpleNamespace(hash=h, name=h, seeds=0, leechers=0, tracker="t", size="1 B", link="") for h in hashes]

    class FakeOrch:
        def __init__(self, results_per_call):
            self._rpc = list(results_per_call)

        def get_search_status(self, sid):
            # Return two statuses: first "running" (to yield results), then "completed"
            if self._rpc:
                return SimpleNamespace(
                    status="running",
                    total_results=0,
                    merged_results=0,
                    trackers_searched=[],
                    to_dict=lambda: {"status": "running"},
                )
            return SimpleNamespace(
                status="completed",
                total_results=0,
                merged_results=0,
                trackers_searched=[],
                to_dict=lambda: {"status": "completed"},
            )

        def get_live_results(self, sid):
            if self._rpc:
                return self._rpc.pop(0)
            return []

    async def drain(gen, limit: int = 20):
        out = []
        async for evt in gen:
            out.append(evt)
            if len(out) >= limit:
                break
        return out

    # Two separate generators started from two "clients" — they must each see
    # the same hash exactly once (i.e. seen_hashes is NOT module-shared).
    orch_a = FakeOrch([_make_results(["abc"])])
    orch_b = FakeOrch([_make_results(["abc"])])

    gen_a = streaming_mod.SSEHandler.search_results_stream(
        "sid-a", orch_a, poll_interval=0.001
    )
    gen_b = streaming_mod.SSEHandler.search_results_stream(
        "sid-b", orch_b, poll_interval=0.001
    )

    events_a, events_b = await asyncio.gather(drain(gen_a), drain(gen_b))

    # Each should contain at least one result_found event for "abc".
    def count_result_found(events):
        return sum(1 for e in events if "event: result_found" in e)

    assert count_result_found(events_a) >= 1
    assert count_result_found(events_b) >= 1
