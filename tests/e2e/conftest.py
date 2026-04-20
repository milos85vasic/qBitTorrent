"""E2E-test conftest — identical shape to tests/integration/conftest.py.

Same autouse lock so e2e tests (Playwright, multi-service scenarios)
don't race the integration batch.
"""

from __future__ import annotations

import pytest

from tests.fixtures.live_search import _file_lock as _live_search_lock


@pytest.fixture(autouse=True)
def _serialize_live_searches():
    with _live_search_lock():
        yield
