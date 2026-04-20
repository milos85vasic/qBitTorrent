"""Integration-test conftest.

Adds one autouse fixture: ``_serialize_live_searches``. Every
integration test acquires the shared file lock from
``tests/fixtures/live_search.py`` before running, which means:

1.  At most one test in the batch can hold the lock at a time.
2.  Tests that fire ``/api/v1/search/sync`` don't pile up on the
    orchestrator's MAX_CONCURRENT_SEARCHES cap.
3.  Tests that don't hit the live service still take the lock, but
    hold it for milliseconds — no measurable slowdown.

The lock is re-exported via ``conftest._file_lock`` so tests that
want to drop it (e.g. intentionally burst the search endpoint) can
import and bypass it explicitly.
"""

from __future__ import annotations

import pytest

from tests.fixtures.live_search import _file_lock as _live_search_lock


@pytest.fixture(autouse=True)
def _serialize_live_searches():
    """Hold the shared live-search lock for the duration of each test.

    Pairs with ``fixtures/live_search.py::_file_lock()`` so batch
    runs don't saturate the orchestrator.
    """
    with _live_search_lock():
        yield
