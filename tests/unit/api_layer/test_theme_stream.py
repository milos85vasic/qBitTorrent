"""
SSE emission tests for ``GET /api/v1/theme/stream``.

The streaming endpoint must:
1. Emit the current state immediately when a client subscribes (so late
   subscribers catch up without waiting for the next PUT).
2. Emit a fresh ``event: theme`` with the new payload within one poll
   cycle of a PUT.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_PATH = _REPO_ROOT / "download-proxy" / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))


def _purge_api_module() -> None:
    for key in [k for k in list(sys.modules) if k == "api" or k.startswith("api.")]:
        del sys.modules[key]


@pytest.mark.asyncio
async def test_sse_emits_initial_state_then_updates(tmp_path, monkeypatch):
    theme_path = tmp_path / "theme.json"
    monkeypatch.setenv("THEME_STATE_PATH", str(theme_path))
    _purge_api_module()
    import api
    from api import theme_state as ts

    ts._store = None  # type: ignore[attr-defined]
    store = ts.get_store()

    # Subscribe a queue directly and drive put() to verify fan-out.
    queue = store.subscribe()
    try:
        # PUT: change happens, subscriber should receive the update.
        store.put("nord", "light")
        item = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert item.paletteId == "nord"
        assert item.mode == "light"
        assert item.updatedAt
    finally:
        store.unsubscribe(queue)


@pytest.mark.asyncio
async def test_sse_multiple_subscribers_receive_same_updates(tmp_path, monkeypatch):
    theme_path = tmp_path / "theme.json"
    monkeypatch.setenv("THEME_STATE_PATH", str(theme_path))
    _purge_api_module()
    import api
    from api import theme_state as ts

    ts._store = None  # type: ignore[attr-defined]
    store = ts.get_store()

    q1 = store.subscribe()
    q2 = store.subscribe()
    try:
        store.put("gruvbox", "dark")
        got_a = await asyncio.wait_for(q1.get(), timeout=1.0)
        got_b = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert got_a.paletteId == got_b.paletteId == "gruvbox"
        assert got_a.mode == got_b.mode == "dark"
    finally:
        store.unsubscribe(q1)
        store.unsubscribe(q2)


@pytest.mark.asyncio
async def test_sse_endpoint_serves_initial_event(tmp_path, monkeypatch):
    """HTTP-level smoke test using the streaming endpoint.

    Drives the ASGI app directly (no httpx) so we can stop reading the
    moment the first ``event: theme`` frame has been flushed — an
    ``async for`` over :func:`httpx.Client.stream` is infinite for a
    keepalive SSE feed.
    """
    theme_path = tmp_path / "theme.json"
    monkeypatch.setenv("THEME_STATE_PATH", str(theme_path))
    _purge_api_module()
    import api
    from api import theme_state as ts

    ts._store = None  # type: ignore[attr-defined]

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/theme/stream",
        "raw_path": b"/api/v1/theme/stream",
        "query_string": b"",
        "headers": [(b"host", b"test")],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
        "root_path": "",
    }
    disconnect_event = asyncio.Event()

    async def receive():
        # First return the request body (empty), then on the next call
        # signal disconnect so the route exits cleanly after the test.
        if not disconnect_event.is_set():
            await asyncio.sleep(0.01)
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    sent: list[dict] = []
    started = asyncio.Event()
    first_event = asyncio.Event()

    async def send(message):
        sent.append(message)
        if message["type"] == "http.response.start":
            started.set()
        elif message["type"] == "http.response.body":
            body = message.get("body", b"")
            if b"event: theme" in body and b"\n\n" in body:
                first_event.set()

    task = asyncio.create_task(api.app(scope, receive, send))
    try:
        await asyncio.wait_for(first_event.wait(), timeout=2.0)
    finally:
        disconnect_event.set()
        # Give the generator a chance to notice disconnect and exit.
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except TimeoutError:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    # Assertions.
    headers = dict(next(m for m in sent if m["type"] == "http.response.start")["headers"])
    assert headers.get(b"content-type", b"").startswith(b"text/event-stream")

    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    text = body.decode("utf-8", errors="ignore")
    assert "event: theme" in text
    for line in text.splitlines():
        if line.startswith("data: "):
            payload = json.loads(line[len("data: ") :])
            assert payload["paletteId"] == "darcula"
            assert payload["mode"] == "dark"
            break
    else:
        pytest.fail("No data line emitted by SSE stream")
