"""Guards the dead-tracker exclusion so the dashboard doesn't drown
in permanently-red chips.

Every entry in ``DEAD_PUBLIC_TRACKERS`` has been observed returning
consistent failures in the diagnostic pass run on 2026-04-23 (403/404,
DNS failures, TLS handshake breaks, or plugin-level crashes on stale
regex). They remain in ``PUBLIC_TRACKERS`` so the classifier still
reports the real reason — but ``_get_enabled_trackers`` filters them
out of the fan-out unless ``ENABLE_DEAD_TRACKERS=1``.

These tests:

1. Assert every name in ``DEAD_PUBLIC_TRACKERS`` is also a key in
   ``PUBLIC_TRACKERS`` (no typos or orphaned entries).
2. Assert ``_get_enabled_trackers()`` omits the dead set by default.
3. Assert ``ENABLE_DEAD_TRACKERS=1`` forces them back in.
4. Assert healthy public trackers (piratebay, linuxtracker, rutor,
   torrentscsv) always make it into the fan-out so a future careless
   `DEAD_PUBLIC_TRACKERS` edit can't silently black-hole them.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[3]
_MS_PATH = REPO / "download-proxy" / "src" / "merge_service"


sys.modules.setdefault("merge_service", type(sys)("merge_service"))
sys.modules["merge_service"].__path__ = [str(_MS_PATH)]  # type: ignore[attr-defined]
_spec = importlib.util.spec_from_file_location("merge_service.search", str(_MS_PATH / "search.py"))
_search = importlib.util.module_from_spec(_spec)
sys.modules["merge_service.search"] = _search
_spec.loader.exec_module(_search)  # type: ignore[union-attr]


def test_dead_set_is_subset_of_public_registry() -> None:
    stray = set(_search.DEAD_PUBLIC_TRACKERS) - set(_search.PUBLIC_TRACKERS)
    assert not stray, (
        f"DEAD_PUBLIC_TRACKERS contains names not in PUBLIC_TRACKERS: {sorted(stray)}. "
        "Typos or orphaned entries defeat the filter — every dead name must "
        "round-trip through the public registry."
    )


def test_default_fan_out_excludes_dead_trackers() -> None:
    orch = _search.SearchOrchestrator()
    with patch.dict(os.environ, {"ENABLE_DEAD_TRACKERS": "0"}, clear=True):
        enabled = {t.name for t in orch._get_enabled_trackers()}
    leaked = enabled & set(_search.DEAD_PUBLIC_TRACKERS)
    assert not leaked, (
        f"Dead trackers leaked into the default fan-out: {sorted(leaked)}. "
        "Dashboard will show permanently-red chips for these."
    )


def test_env_flag_forces_dead_trackers_back_in() -> None:
    orch = _search.SearchOrchestrator()
    with patch.dict(os.environ, {"ENABLE_DEAD_TRACKERS": "1"}, clear=False):
        enabled = {t.name for t in orch._get_enabled_trackers()}
    missing = set(_search.DEAD_PUBLIC_TRACKERS) - enabled
    assert not missing, (
        f"ENABLE_DEAD_TRACKERS=1 should include dead trackers but these were still missing: {sorted(missing)}"
    )


@pytest.mark.parametrize(
    "canary",
    [
        "piratebay",
        "linuxtracker",
        "rutor",
        "torrentscsv",
        "academictorrents",
        "yts",
        "glotorrents",
        "yourbittorrent",
    ],
)
def test_canary_trackers_stay_in_default_fan_out(canary: str) -> None:
    """Canaries are trackers known to return results for common queries
    like ``linux``. They must never accidentally end up in the dead set."""
    assert canary in _search.PUBLIC_TRACKERS, (
        f"{canary!r} disappeared from PUBLIC_TRACKERS — that's a much "
        "bigger problem than this test but we want to catch it here too."
    )
    assert canary not in _search.DEAD_PUBLIC_TRACKERS, (
        f"{canary!r} was added to DEAD_PUBLIC_TRACKERS. It is a known-good "
        "tracker; adding it there will silently black-hole its results."
    )


def test_dead_list_reflects_documented_categories() -> None:
    """Keep docs/MERGE_SEARCH_DIAGNOSTICS.md in sync with code.

    The diagnostics doc publishes the known-dead list; when we drop
    entries in or out, the doc should reflect it. This test reads the
    doc and asserts every DEAD_PUBLIC_TRACKERS name is mentioned.
    """
    doc = (REPO / "docs" / "MERGE_SEARCH_DIAGNOSTICS.md").read_text(encoding="utf-8")
    missing = [name for name in _search.DEAD_PUBLIC_TRACKERS if name not in doc]
    assert not missing, (
        f"DEAD_PUBLIC_TRACKERS entries not documented in "
        f"docs/MERGE_SEARCH_DIAGNOSTICS.md: {sorted(missing)}. "
        "Add them to the 'The known-dead list' section."
    )
