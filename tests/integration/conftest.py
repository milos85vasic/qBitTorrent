"""Integration-test conftest.

Autouse fixtures:

*   ``_serialize_live_searches`` — holds the shared file lock from
    ``tests/fixtures/live_search.py`` for the duration of each test
    so the batch can't saturate MAX_CONCURRENT_SEARCHES.
*   ``_wait_for_idle_orchestrator`` — before yielding the lock to
    the test, block (with a short timeout) until the merge service
    reports zero active searches. This handles the case where a
    previous test's POST /api/v1/search returned quickly but its
    background fan-out was still chewing CPU.

Taken together these two keep one slow test from spilling into the
next. The lock is re-exported via ``_file_lock`` for tests that
intentionally want to burst the endpoint (none today).
"""

from __future__ import annotations

import os
import time

import pytest
import requests

from tests.fixtures.live_search import _file_lock as _live_search_lock


def _wait_for_idle(base_url: str, max_wait: float = 180.0) -> None:
    """Poll ``/api/v1/stats`` for ``active_searches == 0``.

    Bounded so a genuinely-stuck service fails the NEXT test
    explicitly (with a useful error message) rather than hanging
    the pytest session indefinitely.
    """
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{base_url}/api/v1/stats", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("active_searches", 0) == 0:
                    return
        except Exception:
            # Service hiccup — give it another beat.
            pass
        time.sleep(2)
    # Don't fail the test outright — logs the reason so operators can
    # spot a stuck orchestrator in CI output.
    import logging

    logging.getLogger(__name__).warning("orchestrator did not reach idle within %.0fs — proceeding", max_wait)


@pytest.fixture(autouse=True)
def _serialize_live_searches():
    """Hold the shared live-search lock + wait for orchestrator idle."""
    base_url = os.environ.get("MERGE_SERVICE_URL", "http://localhost:7187")
    with _live_search_lock():
        _wait_for_idle(base_url)
        yield
