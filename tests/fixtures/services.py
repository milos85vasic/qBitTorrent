"""Live-service fixtures.

Philosophy
----------
Before Phase 0.3, dozens of integration tests looked like::

    def test_something():
        if not requests.get("http://localhost:7187/").ok:
            pytest.skip("merge service unavailable")
        ...

That pattern hides breakage: CI showed "331 passed" while 71 tests were
silently skipped. The completion-initiative (see docs/superpowers/plans/
2026-04-19-completion-initiative.md) replaces those runtime skips with
fixtures that **require** the service to be healthy.

Behaviour:

*   If the service is healthy, the fixture returns the base URL.
*   If the service is unreachable, the fixture **errors** (not skips)
    with a clear message that points the operator at `./start.sh -p`
    or the `requires_compose` marker semantics.
*   Tests that are genuinely credential-gated (e.g. private-tracker
    logins) use the `@pytest.mark.requires_credentials` marker so CI
    can partition runs.

Environment variables
---------------------

``MERGE_SERVICE_URL``     default ``http://localhost:7187``
``QBITTORRENT_URL``       default ``http://localhost:7186``
``WEBUI_BRIDGE_URL``      default ``http://localhost:7188``
``SERVICE_PROBE_TIMEOUT`` default ``3`` (seconds per probe attempt)
``SERVICE_PROBE_RETRIES`` default ``5`` (fixture retries before error)

``MODE=mock`` short-circuits probes and hands back fake URLs that respx
can intercept — useful for running integration tests offline.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

import pytest
import requests

_DEFAULT_TIMEOUT: Final[float] = float(os.environ.get("SERVICE_PROBE_TIMEOUT", "3"))
_DEFAULT_RETRIES: Final[int] = int(os.environ.get("SERVICE_PROBE_RETRIES", "5"))


@dataclass(frozen=True)
class ServiceEndpoint:
    """A live service the test needs."""

    name: str
    url: str
    health_path: str
    expect_substring: str | None = None

    @property
    def health_url(self) -> str:
        return f"{self.url.rstrip('/')}{self.health_path}"


def _probe(ep: ServiceEndpoint, timeout: float = _DEFAULT_TIMEOUT, retries: int = _DEFAULT_RETRIES) -> None:
    """Probe ``ep`` until healthy or raise ``RuntimeError``."""
    last_err: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(ep.health_url, timeout=timeout)
            if resp.status_code < 400:
                if ep.expect_substring is None or ep.expect_substring in resp.text:
                    return
                last_err = AssertionError(
                    f"expected substring {ep.expect_substring!r} not in body of {ep.health_url}"
                )
            else:
                last_err = AssertionError(f"HTTP {resp.status_code} from {ep.health_url}")
        except requests.RequestException as exc:
            last_err = exc
        if attempt < retries:
            time.sleep(min(2.0, 0.3 * attempt))
    raise RuntimeError(
        f"Service '{ep.name}' at {ep.health_url} is not healthy after "
        f"{retries} attempts. Last error: {last_err}. "
        "Start the stack with `./start.sh -p` (rootless Podman is fine) "
        "before running this test. If you are running a mocked suite, "
        "set MODE=mock to bypass live probes."
    )


def _mock_mode() -> bool:
    return os.environ.get("MODE", "").lower() == "mock"


# ---------------------------------------------------------------------------
# Public fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def merge_service_endpoint() -> ServiceEndpoint:
    return ServiceEndpoint(
        name="merge-search",
        url=os.environ.get("MERGE_SERVICE_URL", "http://localhost:7187"),
        health_path="/health",
        expect_substring='"status"',
    )


@pytest.fixture(scope="session")
def qbittorrent_endpoint() -> ServiceEndpoint:
    return ServiceEndpoint(
        name="qbittorrent-webui-proxy",
        url=os.environ.get("QBITTORRENT_URL", "http://localhost:7186"),
        health_path="/",
    )


@pytest.fixture(scope="session")
def webui_bridge_endpoint() -> ServiceEndpoint:
    return ServiceEndpoint(
        name="webui-bridge",
        url=os.environ.get("WEBUI_BRIDGE_URL", "http://localhost:7188"),
        health_path="/health",
    )


def _live_service_fixture(endpoint_fixture: str) -> Callable[..., str]:
    """Factory that builds a session-scoped live-URL fixture.

    Each live fixture probes the matching endpoint; on failure the test
    errors with the message from :func:`_probe`. When ``MODE=mock`` the
    fixture short-circuits and returns the base URL unchanged so that
    respx/responses stubs can intercept it.
    """

    def _fixture(request: pytest.FixtureRequest) -> str:
        ep: ServiceEndpoint = request.getfixturevalue(endpoint_fixture)
        if _mock_mode():
            return ep.url
        _probe(ep)
        return ep.url

    _fixture.__name__ = endpoint_fixture.replace("_endpoint", "_live")
    return _fixture


merge_service_live = pytest.fixture(scope="session")(_live_service_fixture("merge_service_endpoint"))
qbittorrent_live = pytest.fixture(scope="session")(_live_service_fixture("qbittorrent_endpoint"))
webui_bridge_live = pytest.fixture(scope="session")(_live_service_fixture("webui_bridge_endpoint"))


@pytest.fixture(scope="session")
def all_services_live(merge_service_live: str, qbittorrent_live: str) -> dict[str, str]:
    """Aggregate fixture for tests that need multiple services."""
    return {"merge_service": merge_service_live, "qbittorrent": qbittorrent_live}
