"""Pytest configuration and shared fixtures for qBittorrent-Fixed.

Fixture locations:

*   Mocks and sample data — this file.
*   Live-service fixtures (``merge_service_live``, ``qbittorrent_live``,
    ``webui_bridge_live``, ``all_services_live``) — :mod:`tests.fixtures.services`.

The live fixtures deliberately error (not skip) when services are down,
so that CI reports breakage instead of silently passing. See
docs/superpowers/plans/2026-04-19-completion-initiative.md Phase 0.3.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, Mock

import pytest

_POLLUTING_ROOTS = ("api", "merge_service", "config")


@pytest.fixture(autouse=True)
def _isolate_download_proxy_modules(request):
    """Keep each test's ``sys.modules`` scribbles from leaking into the next.

    Several pre-existing UNIT-test files install throw-away stub packages
    for ``api`` and ``merge_service`` (so they can import leaf modules
    without executing ``api/__init__.py``, which boots FastAPI). If those
    stubs leak into the next test, any subsequent ``from api.routes
    import X`` fails with ``'api' is not a package``.

    The isolation is RESTRICTED to ``tests/unit/`` because those are the
    only callers that install stubs. Integration + e2e tests import the
    real modules and keep live references — wiping ``merge_service.*``
    out from under them while pytest-asyncio still has scheduled
    coroutines produced KeyError/Exception-ignored cascades that broke
    ``tests/e2e/test_full_pipeline.py``.
    """
    test_path = str(request.node.fspath)
    if "/tests/unit/" not in test_path.replace("\\", "/"):
        yield
        return
    saved = {
        k: v
        for k, v in sys.modules.items()
        if k in _POLLUTING_ROOTS or any(k.startswith(root + ".") for root in _POLLUTING_ROOTS)
    }
    try:
        yield
    finally:
        for k in list(sys.modules):
            if k in _POLLUTING_ROOTS or any(k.startswith(root + ".") for root in _POLLUTING_ROOTS):
                del sys.modules[k]
        sys.modules.update(saved)

# Re-export live-service fixtures so that tests can request them by name
# from any conftest without an explicit import.
from tests.fixtures.services import (  # noqa: F401 -- re-exported
    all_services_live,
    merge_service_endpoint,
    merge_service_live,
    qbittorrent_endpoint,
    qbittorrent_live,
    webui_bridge_endpoint,
    webui_bridge_live,
)
from tests.fixtures.live_search import (  # noqa: F401 -- re-exported
    _live_search_cache,
    fresh_magnet_hash,
    fresh_magnet_uri,
    live_search_result,
)


@pytest.fixture
def qbittorrent_host() -> str:
    """Default qBittorrent host."""
    return os.environ.get("QBITTORRENT_HOST", "localhost")


@pytest.fixture
def qbittorrent_port() -> str:
    """Default qBittorrent WebUI port (proxy)."""
    return os.environ.get("QBITTORRENT_PORT", "7185")


@pytest.fixture
def qbittorrent_url(qbittorrent_host: str, qbittorrent_port: str) -> str:
    """Full qBittorrent WebUI URL (container-internal)."""
    return f"http://{qbittorrent_host}:{qbittorrent_port}"


@pytest.fixture
def mock_qbittorrent_api() -> Mock:
    """Mock qBittorrent API client for unit tests."""
    api = Mock()
    api.get_torrents = AsyncMock(return_value=[])
    api.add_torrent = AsyncMock(return_value={"hash": "abc123"})
    api.get_torrent_files = AsyncMock(return_value=[])
    return api


@pytest.fixture
def sample_search_result() -> dict:
    """One novaprinter-shaped search hit."""
    return {
        "name": "Ubuntu 22.04 LTS",
        "link": "magnet:?xt=urn:btih:abc123",
        "size": "2.5 GB",
        "seeds": "100",
        "leechers": "20",
        "engine_url": "https://example-tracker.com",
        "desc_link": "https://example-tracker.com/details/123",
    }


@pytest.fixture
def sample_merged_result() -> dict:
    """One merge-service-shaped merged result."""
    return {
        "canonical_name": "Ubuntu 22.04 LTS",
        "canonical_infohash": "abc123",
        "size": "2.5 GB",
        "sources": [
            {"tracker": "tracker1.com", "seeds": 100, "leechers": 20},
            {"tracker": "tracker2.com", "seeds": 80, "leechers": 15},
        ],
        "total_seeds": 180,
        "total_leechers": 35,
        "download_urls": [
            "magnet:?xt=urn:btih:abc123",
            "https://tracker1.com/download/123",
            "https://tracker2.com/download/456",
        ],
    }
