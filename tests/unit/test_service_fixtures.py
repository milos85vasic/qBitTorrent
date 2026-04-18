"""Sanity tests for tests/fixtures/services.py.

These are *unit* tests of the fixture machinery — they don't contact
the real services. The live-service round-trip is exercised by the
integration suite.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from tests.fixtures import services as svc


def test_service_endpoint_health_url_strips_trailing_slash() -> None:
    ep = svc.ServiceEndpoint(name="x", url="http://x:1/", health_path="/h")
    assert ep.health_url == "http://x:1/h"


def test_probe_retries_then_raises() -> None:
    ep = svc.ServiceEndpoint(name="x", url="http://127.0.0.1:1", health_path="/h")
    with patch.object(svc.requests, "get", side_effect=requests.ConnectionError("boom")):
        with pytest.raises(RuntimeError) as exc:
            svc._probe(ep, timeout=0.01, retries=2)
    assert "not healthy after 2 attempts" in str(exc.value)
    assert "./start.sh" in str(exc.value)


def test_probe_succeeds_when_endpoint_returns_200_and_matches_substring() -> None:
    ep = svc.ServiceEndpoint(name="x", url="http://x:1", health_path="/h", expect_substring="ok")
    ok = MagicMock(status_code=200, text='{"status":"ok"}')
    with patch.object(svc.requests, "get", return_value=ok):
        svc._probe(ep, timeout=0.01, retries=1)


def test_probe_fails_when_substring_missing() -> None:
    ep = svc.ServiceEndpoint(name="x", url="http://x:1", health_path="/h", expect_substring="ok")
    bad = MagicMock(status_code=200, text='{"status":"bad"}')
    with patch.object(svc.requests, "get", return_value=bad):
        with pytest.raises(RuntimeError):
            svc._probe(ep, timeout=0.01, retries=1)


def test_probe_fails_on_non_2xx() -> None:
    ep = svc.ServiceEndpoint(name="x", url="http://x:1", health_path="/h")
    bad = MagicMock(status_code=503, text="")
    with patch.object(svc.requests, "get", return_value=bad):
        with pytest.raises(RuntimeError) as exc:
            svc._probe(ep, timeout=0.01, retries=1)
    assert "HTTP 503" in str(exc.value)


def test_mock_mode_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODE", "mock")
    assert svc._mock_mode() is True


def test_mock_mode_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODE", raising=False)
    assert svc._mock_mode() is False
