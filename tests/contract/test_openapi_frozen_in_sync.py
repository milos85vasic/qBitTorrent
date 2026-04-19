"""Fails when docs/api/openapi.json drifts from the live schema.

Run ``./scripts/freeze-openapi.sh`` after intentional API changes to
regenerate the committed snapshot. CI running this test catches
accidental contract drift.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "download-proxy" / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

FROZEN = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"


@pytest.fixture(scope="module")
def frozen_schema() -> dict:
    assert FROZEN.is_file(), f"missing {FROZEN} — run scripts/freeze-openapi.sh"
    return json.loads(FROZEN.read_text())


@pytest.fixture(scope="module")
def live_schema() -> dict:
    os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost")
    from api import app

    return app.openapi()


def _operations(schema: dict) -> set[str]:
    out: set[str] = set()
    for path, methods in schema.get("paths", {}).items():
        for method in methods:
            if method.lower() in {"parameters", "summary", "description"}:
                continue
            out.add(f"{method.upper()} {path}")
    return out


def test_frozen_and_live_have_same_operations(frozen_schema: dict, live_schema: dict) -> None:
    frozen_ops = _operations(frozen_schema)
    live_ops = _operations(live_schema)
    removed = frozen_ops - live_ops
    added = live_ops - frozen_ops
    assert not removed, f"API operations removed: {removed}. Run scripts/freeze-openapi.sh if intentional."
    assert not added, f"API operations added: {added}. Run scripts/freeze-openapi.sh to snapshot."


def test_frozen_and_live_have_same_schemas(frozen_schema: dict, live_schema: dict) -> None:
    frozen_schemas = set(frozen_schema.get("components", {}).get("schemas", {}))
    live_schemas = set(live_schema.get("components", {}).get("schemas", {}))
    removed = frozen_schemas - live_schemas
    added = live_schemas - frozen_schemas
    assert not removed, f"Schema types removed: {removed}. Run scripts/freeze-openapi.sh if intentional."
    assert not added, f"Schema types added: {added}. Run scripts/freeze-openapi.sh to snapshot."
