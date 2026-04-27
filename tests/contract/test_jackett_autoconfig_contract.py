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
    pytest.skip(
        "endpoint moved to boba-jackett:7189 — see qBitTorrent-go/tests/contract/openapi_test.go"
    )


def test_no_5xx_on_extra_query_params():
    pytest.skip(
        "endpoint moved to boba-jackett:7189 — see qBitTorrent-go/tests/contract/openapi_test.go"
    )
