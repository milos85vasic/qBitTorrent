"""Integration test that the live-service fixtures start the required services.

These tests are run with the ``requires_compose`` marker because they
bring up the full docker-compose stack (qbittorrent + proxy) and the
host webui-bridge process.

Phase 0.2 of the completion-initiative mandates that the fixtures
``merge_service_live``, ``qbittorrent_live``, ``webui_bridge_live``
start the services when they are down, rather than merely probing and
erroring.

The three fixtures are tested here to guarantee they return healthy
URLs that can be reached.
"""

import httpx
import pytest


@pytest.mark.requires_compose
def test_merge_service_fixture_returns_healthy_url(merge_service_live: str) -> None:
    """merge_service_live must point to a live merge-service (port 7187)."""
    r = httpx.get(f"{merge_service_live}/health", timeout=5)
    assert r.status_code == 200
    assert "status" in r.text


@pytest.mark.requires_compose
def test_qbittorrent_proxy_fixture_returns_healthy_url(qbittorrent_live: str) -> None:
    """qbittorrent_live must point to the download-proxy (port 7186)."""
    r = httpx.get(qbittorrent_live, timeout=5)
    assert r.status_code == 200


@pytest.mark.requires_compose
def test_webui_bridge_fixture_returns_healthy_url(webui_bridge_live: str) -> None:
    """webui_bridge_live must point to the webui-bridge host process (port 7188)."""
    r = httpx.get(f"{webui_bridge_live}/health", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] in ("ok", "healthy")
