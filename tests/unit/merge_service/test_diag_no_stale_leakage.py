"""Guards against stale diagnostics leaking from an aborted search
into the next search's ``tracker_stats``.

The orchestrator uses a per-instance ``_last_public_tracker_diag``
dict as a side-channel to carry subprocess error classifications out
of ``_search_public_tracker``. If a search is cancelled or the
orchestrator raises before the pop-on-read in ``_search_one`` can run,
the old entry sits there and could get attributed to a future
tracker run.

``_run_search`` explicitly clears entries for every fan-out tracker
before the search begins. These tests ensure that clean-up stays in
place — a future refactor that forgets it will silently surface
last-week's `upstream_http_403` as this-search's empty-tracker
explanation.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

REPO = Path(__file__).resolve().parents[3]
_MS_PATH = REPO / "download-proxy" / "src" / "merge_service"


sys.modules.setdefault("merge_service", type(sys)("merge_service"))
sys.modules["merge_service"].__path__ = [str(_MS_PATH)]  # type: ignore[attr-defined]
_spec = importlib.util.spec_from_file_location("merge_service.search", str(_MS_PATH / "search.py"))
_search = importlib.util.module_from_spec(_spec)
sys.modules["merge_service.search"] = _search
_spec.loader.exec_module(_search)  # type: ignore[union-attr]


def test_run_search_clears_stale_diag_before_fanning_out() -> None:
    """Pre-seed the diag with a stale entry and confirm _run_search wipes it."""
    orch = _search.SearchOrchestrator()
    # Pretend a previous search's subprocess crashed and its diag never
    # got popped because the search was cancelled.
    orch._last_public_tracker_diag["piratebay"] = {
        "error_type": "upstream_http_403",
        "error": "stale leftover from prior search",
        "stderr_tail": "old",
        "deadline_hit": False,
        "deadline_seconds": 25.0,
    }

    # Fake tracker fan-out: return no trackers so nothing actually runs,
    # but `_run_search` should still clear the diag before it would dispatch.
    # We run the clearing prologue by calling `start_search` + a minimal
    # `_run_search` with no real subprocess work.
    metadata = orch.start_search("q", "all", enable_metadata=False, validate_trackers=False)

    # Patch `_search_tracker` to be a no-op so the orchestrator doesn't try
    # to actually spawn plugins. The clearing happens BEFORE the fan-out.
    async def no_op(self, tracker, query, category):
        return []

    with patch.object(_search.SearchOrchestrator, "_search_tracker", no_op):
        asyncio.run(orch._run_search(metadata.search_id, "q", "all"))

    # After the fan-out, the stale entry must be gone because piratebay
    # is enabled by default and `_run_search` cleared its slot.
    assert "piratebay" not in orch._last_public_tracker_diag, (
        "_run_search failed to clear the stale diag entry — the next "
        "search's piratebay chip would pick up last-search's error."
    )


def test_diag_is_popped_not_lingering_after_search_one() -> None:
    """Verify the normal pop-on-read path in `_search_one`.

    After a successful _search_tracker call the entry must be gone
    from the side-channel (pop, not peek) so that two searches don't
    share the same diagnostic cell.
    """
    orch = _search.SearchOrchestrator()

    async def fake_search_tracker(tracker, query, category):
        # Simulate `_search_public_tracker` writing to the diag.
        orch._last_public_tracker_diag[tracker.name] = {
            "error_type": "upstream_http_403",
            "error": "403 Forbidden",
            "stderr_tail": "HTTP Error 403",
            "deadline_hit": False,
            "deadline_seconds": 25.0,
        }
        return []

    metadata = orch.start_search("q", "all", enable_metadata=False, validate_trackers=False)
    with patch.object(orch, "_search_tracker", new=AsyncMock(side_effect=fake_search_tracker)):
        asyncio.run(orch._run_search(metadata.search_id, "q", "all"))

    # After the fan-out every public-tracker entry must be popped.
    # (The orchestrator pops the diag in `_search_one` after each tracker
    # completes.)
    assert orch._last_public_tracker_diag == {}, (
        f"Diag left behind: {orch._last_public_tracker_diag}. The fan-out must drain the side-channel."
    )

    # The diagnostic info should have landed on the stat instead.
    stats = metadata.tracker_stats
    piratebay_stat = stats.get("piratebay")
    assert piratebay_stat is not None
    assert piratebay_stat.error_type == "upstream_http_403"
    assert piratebay_stat.error == "403 Forbidden"
    assert piratebay_stat.status == "error"  # classified empty → error
