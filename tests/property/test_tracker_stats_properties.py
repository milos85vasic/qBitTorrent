"""Property-based invariants for per-tracker search stats.

- sum of stat.results_count == metadata.total_results
- every completed stat has duration_ms >= 0
- set of stat names == set of trackers_searched
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

_SRC = Path(__file__).resolve().parents[2] / "download-proxy" / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost")

from merge_service.search import (
    SearchOrchestrator,
    SearchResult,
    TrackerSource,
)

pytestmark = pytest.mark.property

_TERMINAL = {"success", "empty", "error", "timeout", "cancelled"}


@st.composite
def _tracker_payloads(draw):
    n_trackers = draw(st.integers(min_value=1, max_value=6))
    payloads: list[tuple[str, int, bool]] = []
    for i in range(n_trackers):
        name = f"t{i}"
        count = draw(st.integers(min_value=0, max_value=8))
        fail = draw(st.booleans())
        payloads.append((name, count, fail))
    return payloads


def _result(name="r") -> SearchResult:
    return SearchResult(
        name=name,
        link=f"magnet:?xt=urn:btih:{'a' * 40}",
        size="1 MB",
        seeds=1,
        leechers=0,
        engine_url="http://x",
    )


async def _run_search_with_payloads(payloads):
    orch = SearchOrchestrator()
    fake_trackers = [
        TrackerSource(name=name, url=f"https://{name}.example", enabled=True) for (name, _count, _fail) in payloads
    ]
    orch._get_enabled_trackers = lambda: fake_trackers

    async def fake_search_tracker(tracker, query, category):
        for pname, count, fail in payloads:
            if pname == tracker.name:
                if fail:
                    raise RuntimeError("boom")
                return [_result(f"{pname}-{i}") for i in range(count)]
        return []

    orch._search_tracker = fake_search_tracker
    metadata = await orch.search(query="q", enable_metadata=False, validate_trackers=False)
    return metadata


@given(payloads=_tracker_payloads())
@settings(max_examples=40, deadline=5_000, suppress_health_check=[HealthCheck.too_slow])
def test_results_count_sums_to_total_results(payloads):
    """sum of stat.results_count across all trackers == metadata.total_results."""
    metadata = asyncio.run(_run_search_with_payloads(payloads))
    assert sum(s.results_count for s in metadata.tracker_stats.values()) == metadata.total_results


@given(payloads=_tracker_payloads())
@settings(max_examples=40, deadline=5_000, suppress_health_check=[HealthCheck.too_slow])
def test_every_completed_stat_has_nonnegative_duration(payloads):
    metadata = asyncio.run(_run_search_with_payloads(payloads))
    for stat in metadata.tracker_stats.values():
        # Every stat that finished a run should have a non-None duration.
        if stat.status in _TERMINAL:
            assert stat.duration_ms is not None
            assert stat.duration_ms >= 0


@given(payloads=_tracker_payloads())
@settings(max_examples=40, deadline=5_000, suppress_health_check=[HealthCheck.too_slow])
def test_stat_names_match_trackers_searched(payloads):
    metadata = asyncio.run(_run_search_with_payloads(payloads))
    assert set(metadata.tracker_stats.keys()) == set(metadata.trackers_searched)


@given(payloads=_tracker_payloads())
@settings(max_examples=30, deadline=5_000, suppress_health_check=[HealthCheck.too_slow])
def test_failed_trackers_record_error_info(payloads):
    metadata = asyncio.run(_run_search_with_payloads(payloads))
    for name, _count, fail in payloads:
        stat = metadata.tracker_stats[name]
        if fail:
            assert stat.status == "error"
            assert stat.error_type == "RuntimeError"
            assert stat.error == "boom"
        else:
            # Non-failing trackers are either success or empty.
            assert stat.status in {"success", "empty"}
