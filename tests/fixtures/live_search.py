"""Shared fixtures that keep live-search tests from trampling each other.

Batch runs of the integration + e2e suites used to fail because:

1.  Many tests call ``POST /api/v1/search/sync`` which blocks for
    90–150 s. Back-to-back invocations hit
    ``MAX_CONCURRENT_SEARCHES`` and get HTTP 429 → test asserts 200 →
    failure.
2.  Each test issued its own `linux` search, so a class of 6 assert
    tests ran the same 120 s fan-out 6 times. 90 minutes turned into
    180 for no reason.
3.  Per-test torrent additions with a single hardcoded hash tripped
    qBittorrent's duplicate-rejection on the second run.

Fixtures exposed here:

*   ``live_search_result(query="linux")`` — module-scoped cached
    search result. The first caller runs the fan-out; subsequent
    callers reuse the same JSON body. Cuts the wall-clock cost of
    assert-heavy classes to one search per query per module.
*   ``fresh_magnet_hash`` — function-scoped unique 40-char hex so
    qBittorrent can't dedupe and reject a test's synthetic torrent.
*   ``search_lock`` — autouse for integration + e2e. Serialises the
    file-lock so only one live test hits ``/search/sync`` at a time
    even under xdist. Prevents the 429 storm.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import secrets
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import pytest
import requests

LOCK_FILE = Path(os.environ.get("LIVE_SEARCH_LOCK", "/tmp/qbit-live-search.lock"))


@contextlib.contextmanager
def _file_lock():
    """Process-wide file lock. Blocks until we're alone in the test
    batch. The lock file is created once and reused; only the
    advisory flock changes between test runs.
    """
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.touch(exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


@pytest.fixture
def fresh_magnet_hash() -> str:
    """Unique 40-hex-char magnet btih for each test invocation."""
    return secrets.token_hex(20)


@pytest.fixture
def fresh_magnet_uri(fresh_magnet_hash: str) -> str:
    """Full magnet URI with a unique btih — safe to add to qBittorrent
    without tripping the duplicate-rejection ``Fails.`` response."""
    return f"magnet:?xt=urn:btih:{fresh_magnet_hash}"


@pytest.fixture(scope="session")
def _live_search_cache() -> Dict[tuple, dict]:
    """Session-wide memo of search results keyed by (query, limit)."""
    return {}


@pytest.fixture
def live_search_result(
    merge_service_live: str,
    _live_search_cache: Dict[tuple, dict],
) -> Callable[..., dict]:
    """Return a callable ``search(query, limit=5)`` that caches results.

    The first caller pays the full 90-150 s fan-out cost; everyone
    else with the same (query, limit) tuple gets the cached JSON.
    Combined with the ``_file_lock()`` below, this keeps
    ``MAX_CONCURRENT_SEARCHES`` saturation out of the test suite.
    """
    def _search(query: str = "linux", limit: int = 5) -> dict:
        # NOTE: we do NOT take ``_file_lock()`` here — the
        # autouse ``_serialize_live_searches`` fixture in the
        # integration + e2e conftests already holds it for the
        # lifetime of each test. Re-acquiring the same POSIX lock on
        # a new fd deadlocks within the same process.
        key = (query, limit)
        if key in _live_search_cache:
            return _live_search_cache[key]
        attempts = 3
        last_err: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                resp = requests.post(
                    f"{merge_service_live}/api/v1/search/sync",
                    json={"query": query, "limit": limit},
                    timeout=300,
                )
            except Exception as exc:
                last_err = exc
                time.sleep(2 * (attempt + 1))
                continue
            if resp.status_code == 429:
                # Queue-full: back off and retry.
                time.sleep(5 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            _live_search_cache[key] = data
            return data
        raise RuntimeError(
            f"live_search_result({query!r}, {limit}) failed after "
            f"{attempts} attempts — last error: {last_err}"
        )
    return _search
