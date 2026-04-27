"""Integration tests for jackett_autoconfig against a running Jackett.

Requires the full compose stack to be up. Skips if Jackett unreachable.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"),
)

import importlib.util

import pytest
import requests

JACKETT_URL = os.getenv("JACKETT_URL", "http://localhost:9117")
MERGE_BASE = os.getenv("MERGE_SERVICE_URL", "http://localhost:7187")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_MS_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src", "merge_service")
sys.modules.setdefault("merge_service", type(sys)("merge_service"))
sys.modules["merge_service"].__path__ = [_MS_PATH]
_ac_spec = importlib.util.spec_from_file_location(
    "merge_service.jackett_autoconfig",
    os.path.join(_MS_PATH, "jackett_autoconfig.py"),
)
_ac_mod = importlib.util.module_from_spec(_ac_spec)
sys.modules["merge_service.jackett_autoconfig"] = _ac_mod
_ac_spec.loader.exec_module(_ac_mod)


def _read_jackett_api_key() -> str:
    path = os.path.join(_REPO_ROOT, "config", "jackett", "Jackett", "ServerConfig.json")
    if not os.path.isfile(path):
        return ""
    with open(path) as f:
        return json.load(f).get("APIKey", "")


@pytest.fixture(scope="module")
def jackett_ready():
    try:
        r = requests.get(f"{JACKETT_URL}/UI/Login", timeout=3)
        if r.status_code >= 500:
            pytest.skip(f"Jackett unhealthy ({r.status_code})")
    except requests.RequestException:
        pytest.skip("Jackett unreachable")
    key = _read_jackett_api_key()
    if not key:
        pytest.skip("Jackett API key not yet generated")
    return key


@pytest.fixture(scope="module")
def merge_ready():
    try:
        r = requests.get(f"{MERGE_BASE}/health", timeout=3)
        if not r.ok:
            pytest.skip(f"merge service unhealthy ({r.status_code})")
    except requests.RequestException:
        pytest.skip("merge service unreachable")


def test_autoconfig_endpoint_returns_live_result(merge_ready, jackett_ready):
    r = requests.get(f"{MERGE_BASE}/api/v1/jackett/autoconfig/last", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert "ran_at" in body
    assert "discovered" in body
    assert "configured_now" in body
    assert "already_present" in body
    assert "errors" in body


def test_autoconfig_no_credential_leakage_in_response(merge_ready, jackett_ready):
    r = requests.get(f"{MERGE_BASE}/api/v1/jackett/autoconfig/last", timeout=5)
    if r.status_code != 200:
        pytest.skip("autoconfig has not run")
    body = r.text
    # Read .env to find credential VALUES (not names) and assert none leak
    env_path = os.path.join(_REPO_ROOT, ".env")
    if not os.path.isfile(env_path):
        pytest.skip(".env not present")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if "=" not in line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if not value or len(value) < 4:
                continue
            if any(s in key.upper() for s in ("PASSWORD", "COOKIES", "API_KEY", "TOKEN")):
                # The Jackett API key WILL appear in connection logs but never
                # in the response body of /jackett/autoconfig/last.
                if key.startswith("JACKETT_API_KEY"):
                    continue
                assert value not in body, f"credential value for {key} leaked into response"


def test_jackett_has_at_least_the_indexers_we_configured(merge_ready, jackett_ready):
    """Cross-check: every entry in our 'configured_now' or 'already_present'
    should appear in Jackett's actual configured-indexer list."""
    r = requests.get(f"{MERGE_BASE}/api/v1/jackett/autoconfig/last", timeout=5)
    if r.status_code != 200:
        pytest.skip("autoconfig has not run")
    body = r.json()
    expected = set(body["configured_now"]) | set(body["already_present"])
    if not expected:
        pytest.skip("autoconfig did not configure any indexers")

    s = requests.Session()
    s.post(f"{JACKETT_URL}/UI/Dashboard", data={"password": ""}, allow_redirects=True, timeout=5)
    indexers = s.get(
        f"{JACKETT_URL}/api/v2.0/indexers", params={"apikey": jackett_ready}, timeout=5
    ).json()
    actually_configured = {x["id"] for x in indexers if x.get("configured")}
    missing = expected - actually_configured
    assert not missing, f"reported configured but not actually present in Jackett: {missing}"


def test_module_orchestrator_is_idempotent_on_second_invocation(jackett_ready):
    """Calling autoconfigure_jackett() twice in a row should report
    already_present (or skip) the second time, never re-configure."""
    import asyncio

    autoconfigure_jackett = _ac_mod.autoconfigure_jackett

    async def run_twice():
        env = {"TESTONLY_USERNAME": "a", "TESTONLY_PASSWORD": "b"}
        r1 = await autoconfigure_jackett(
            jackett_url=JACKETT_URL, api_key=jackett_ready, env=env, timeout=8.0
        )
        r2 = await autoconfigure_jackett(
            jackett_url=JACKETT_URL, api_key=jackett_ready, env=env, timeout=8.0
        )
        return r1, r2

    r1, r2 = asyncio.run(run_twice())
    # Whatever r1 configured, r2 must NOT configure-now again.
    for indexer in r1.configured_now:
        assert indexer not in r2.configured_now, (
            f"indexer {indexer} configured twice — idempotency broken"
        )
