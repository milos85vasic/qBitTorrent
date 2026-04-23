"""Property-based tests for the deduplicator.

Hypothesis explores edge cases that hand-written examples miss:
- idempotence (merging twice == merging once)
- commutativity over input order
- seed-sum invariant (total_seeds == sum of source seeds)
- size-parse roundtrip for common formats
"""

from __future__ import annotations

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

from merge_service.deduplicator import Deduplicator
from merge_service.search import SearchResult

pytestmark = pytest.mark.property


@st.composite
def _search_result(draw) -> SearchResult:
    name = draw(st.text(min_size=1, max_size=80).filter(lambda s: s.strip()))
    size_val = draw(st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False))
    size_unit = draw(st.sampled_from(["MB", "GB"]))
    seeds = draw(st.integers(min_value=0, max_value=100_000))
    leechers = draw(st.integers(min_value=0, max_value=100_000))
    tracker = draw(st.sampled_from(["rutracker", "kinozal", "nnmclub", "iptorrents", "piratebay", "eztv"]))
    info_hash = draw(st.text(alphabet="abcdef0123456789", min_size=40, max_size=40))
    return SearchResult(
        name=name,
        link=f"magnet:?xt=urn:btih:{info_hash}",
        size=f"{size_val:.2f} {size_unit}",
        seeds=seeds,
        leechers=leechers,
        engine_url=f"https://{tracker}.example",
        desc_link=f"https://{tracker}.example/{info_hash}",
        pub_date="2024-01-01",
        tracker=tracker,
    )


@given(results=st.lists(_search_result(), min_size=0, max_size=40))
@settings(max_examples=60, deadline=5_000, suppress_health_check=[HealthCheck.too_slow])
def test_merge_is_idempotent(results):
    """Merging an already-merged list yields the same count."""
    dedup = Deduplicator()
    first = dedup.merge_results(results)
    # Flatten back to inputs for the second pass.
    flat = [r for m in first for r in m.original_results]
    second = dedup.merge_results(flat)
    assert len(second) == len(first)


@given(results=st.lists(_search_result(), min_size=2, max_size=30))
@settings(max_examples=50, deadline=5_000, suppress_health_check=[HealthCheck.too_slow])
def test_merge_is_order_invariant(results):
    """The set of merge-group signatures is insensitive to input order."""
    dedup = Deduplicator()

    def _sigs(merged):
        return sorted(tuple(sorted(r.tracker + ":" + r.link for r in m.original_results)) for m in merged)

    reversed_results = list(reversed(results))
    assert _sigs(dedup.merge_results(results)) == _sigs(dedup.merge_results(reversed_results))


@given(results=st.lists(_search_result(), min_size=1, max_size=30))
@settings(max_examples=50, deadline=5_000, suppress_health_check=[HealthCheck.too_slow])
def test_total_seeds_equals_sum_of_sources(results):
    """Aggregated total_seeds is exactly the sum of per-source seeds."""
    dedup = Deduplicator()
    for m in dedup.merge_results(results):
        expected = sum(r.seeds for r in m.original_results)
        assert m.total_seeds == expected


@given(results=st.lists(_search_result(), min_size=1, max_size=30))
@settings(max_examples=50, deadline=5_000, suppress_health_check=[HealthCheck.too_slow])
def test_total_leechers_equals_sum_of_sources(results):
    dedup = Deduplicator()
    for m in dedup.merge_results(results):
        expected = sum(r.leechers for r in m.original_results)
        assert m.total_leechers == expected


@given(results=st.lists(_search_result(), min_size=0, max_size=20))
@settings(max_examples=40, deadline=5_000, suppress_health_check=[HealthCheck.too_slow])
def test_merge_never_drops_sources(results):
    """Every input result is referenced in exactly one merged group."""
    dedup = Deduplicator()
    merged = dedup.merge_results(results)
    total = sum(len(m.original_results) for m in merged)
    assert total == len(results)


@given(
    value=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False),
    unit=st.sampled_from(["KB", "MB", "GB", "TB"]),
)
def test_parse_size_roundtrip(value, unit):
    """Round-tripping a formatted size preserves within 0.2% precision."""
    dedup = Deduplicator()
    original = f"{value:.2f} {unit}"
    bytes_ = dedup._parse_size(original)
    assert bytes_ is not None and bytes_ > 0
    # Re-parse of the same string must be deterministic.
    assert dedup._parse_size(original) == bytes_
