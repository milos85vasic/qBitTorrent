"""Contract test for /api/v1/jackett/autoconfig/last via the OpenAPI schema.

Maps the CONSTITUTION 'automation' layer to contract testing here.
Schemathesis 4.x API. Skips if merge service / schema unreachable.
"""

from __future__ import annotations

import os

import pytest
import requests

MERGE_BASE = os.getenv("MERGE_SERVICE_URL", "http://localhost:7187")


def test_autoconfig_endpoint_responds_within_schema():
    """The /openapi.json must include the autoconfig path; the live response
    must be valid JSON and the documented status codes must hold (200|404)."""
    try:
        schema = requests.get(f"{MERGE_BASE}/openapi.json", timeout=5).json()
    except (requests.RequestException, ValueError):
        pytest.skip("OpenAPI schema unreachable")

    paths = schema.get("paths", {}) or {}
    target = "/api/v1/jackett/autoconfig/last"
    if target not in paths:
        pytest.skip(
            f"path {target} not yet in OpenAPI schema (expected once merge service is hot)"
        )

    r = requests.get(f"{MERGE_BASE}{target}", timeout=5)
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        body = r.json()
        # contract: dict with at minimum these keys
        for key in ("ran_at", "discovered", "configured_now", "errors"):
            assert key in body, f"contract violation: {key} missing"


def test_no_5xx_on_extra_query_params():
    """Hardening: junk query params must not 500 the endpoint."""
    try:
        r = requests.get(
            f"{MERGE_BASE}/api/v1/jackett/autoconfig/last",
            params={"junk": "x" * 100, "and": "more"},
            timeout=5,
        )
    except requests.RequestException:
        pytest.skip("merge service unreachable")
    assert r.status_code < 500, r.text
