"""Guards the tunable per-tracker deadline and the deadline_hit
diagnostic note.

Before 2026-04-19 the deadline was hardcoded at 25 s and when it
fired the captured rows were preserved but there was no signal in
the response that the result set was truncated — a tracker with
1738 rows for "linux" and one that finished cleanly with 25 rows
looked identical to the operator. These tests pin:

1. ``PUBLIC_TRACKER_DEADLINE_SECONDS`` env var is honoured.
2. The value is clamped to the [5, 120] range so a malicious or
   typo'd env can't turn the deadline into something absurd.
3. When the deadline fires, ``_last_public_tracker_diag[name]``
   carries ``deadline_hit=True`` and the configured seconds.
4. A clean-exit tracker has ``deadline_hit=False``.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

REPO = Path(__file__).resolve().parents[3]
_MS_PATH = REPO / "download-proxy" / "src" / "merge_service"


sys.modules.setdefault("merge_service", type(sys)("merge_service"))
sys.modules["merge_service"].__path__ = [str(_MS_PATH)]  # type: ignore[attr-defined]
_spec = importlib.util.spec_from_file_location(
    "merge_service.search", str(_MS_PATH / "search.py")
)
_search = importlib.util.module_from_spec(_spec)
sys.modules["merge_service.search"] = _search
_spec.loader.exec_module(_search)  # type: ignore[union-attr]


def _proc_mock(rows_then_eof: list[bytes], *, returncode: int = 0) -> AsyncMock:
    mock = AsyncMock()
    mock.returncode = returncode
    mock.stdout = MagicMock()
    mock.stdout.readline = AsyncMock(side_effect=rows_then_eof + [b""])
    mock.stderr = MagicMock()
    mock.stderr.read = AsyncMock(return_value=b"")
    mock.wait = AsyncMock(return_value=returncode)
    mock.kill = MagicMock()
    return mock


@pytest.mark.parametrize(
    "env_val,expected",
    [
        (None, 60.0),
        ("10", 10.0),
        ("60", 60.0),
        ("3", 5.0),      # clamped up
        ("999", 120.0),  # clamped down
        ("not-a-number", 60.0),  # invalid falls back to default
    ],
)
def test_deadline_env_clamping(env_val, expected) -> None:
    """The deadline value must respect the env, clamped to [5, 120]."""
    orch = _search.SearchOrchestrator()
    env = {k: v for k, v in os.environ.items() if k != "PUBLIC_TRACKER_DEADLINE_SECONDS"}
    if env_val is not None:
        env["PUBLIC_TRACKER_DEADLINE_SECONDS"] = env_val

    captured: dict = {}

    async def fake_subprocess(*args, **kwargs):
        # We never let the real subprocess run; just record the deadline.
        return _proc_mock([b'{"name":"x","size":"1 B","seeds":1,"leech":0,"link":"m","desc_link":"d"}\n'])

    with patch.dict(os.environ, env, clear=True), patch(
        "asyncio.create_subprocess_exec", side_effect=fake_subprocess
    ):
        asyncio.run(orch._search_public_tracker("piratebay", "q", "all"))

    diag = orch._last_public_tracker_diag.get("piratebay")
    assert diag is not None
    assert diag["deadline_seconds"] == pytest.approx(expected), (
        f"env={env_val!r} → expected clamped deadline {expected}, got {diag['deadline_seconds']}"
    )


def test_deadline_hit_flag_false_on_clean_exit() -> None:
    orch = _search.SearchOrchestrator()

    async def fake_subprocess(*args, **kwargs):
        return _proc_mock([b'{"name":"ok","size":"1 B","seeds":1,"leech":0,"link":"m","desc_link":"d"}\n'])

    with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
        results = asyncio.run(orch._search_public_tracker("piratebay", "q", "all"))

    assert results, "fake plugin emitted one row — it must land"
    diag = orch._last_public_tracker_diag["piratebay"]
    assert diag["deadline_hit"] is False


def test_deadline_hit_flag_true_when_readline_times_out() -> None:
    """Simulate a plugin that never flushes before the deadline.

    `proc.stdout.readline` hangs; our parent's `asyncio.wait_for` fires
    and breaks out of the loop with `killed_by_deadline=True`.
    """
    orch = _search.SearchOrchestrator()

    async def _hang():
        await asyncio.sleep(999)

    async def fake_subprocess(*args, **kwargs):
        mock = AsyncMock()
        mock.returncode = None
        mock.stdout = MagicMock()
        mock.stdout.readline = AsyncMock(side_effect=_hang)
        mock.stderr = MagicMock()
        mock.stderr.read = AsyncMock(return_value=b"")
        mock.wait = AsyncMock(return_value=-9)
        mock.kill = MagicMock()
        return mock

    # Tighten deadline so the test runs quickly.
    with patch.dict(
        os.environ, {"PUBLIC_TRACKER_DEADLINE_SECONDS": "5"}, clear=False
    ), patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
        results = asyncio.run(orch._search_public_tracker("slowplug", "q", "all"))

    assert results == [], "no rows should have flushed"
    diag = orch._last_public_tracker_diag["slowplug"]
    assert diag["deadline_hit"] is True
    assert diag["error_type"] == "deadline_timeout"
    assert diag["deadline_seconds"] == 5.0
