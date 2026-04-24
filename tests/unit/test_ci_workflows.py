"""Validate that the auto-triggered CI workflow suite exists and has the
correct trigger configuration.

Phase 0.4: Split manual CI into auto-triggered workflows per
docs/superpowers/plans/2026-04-19-completion-initiative.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

REQUIRED_WORKFLOWS: dict[str, dict[str, set[str]]] = {
    "syntax.yml": {"on": {"push", "pull_request"}},
    "unit.yml": {"on": {"push", "pull_request"}},
    "integration.yml": {"on": {"push", "pull_request"}},
    "nightly.yml": {"on": {"schedule", "workflow_dispatch"}},
    "security.yml": {"on": {"schedule", "workflow_dispatch"}},
}


@pytest.mark.parametrize("name", sorted(REQUIRED_WORKFLOWS))
def test_workflow_file_exists(name: str) -> None:
    assert (WORKFLOW_DIR / name).is_file(), f"missing .github/workflows/{name}"


@pytest.mark.skipif(yaml is None, reason="PyYAML not installed")  # SKIP-OK: #legacy-untriaged
@pytest.mark.parametrize(("name", "spec"), sorted(REQUIRED_WORKFLOWS.items()))
def test_workflow_triggers(name: str, spec: dict[str, set[str]]) -> None:
    raw = (WORKFLOW_DIR / name).read_text()
    data = yaml.safe_load(raw)
    triggers = data.get(True, data.get("on"))
    assert triggers, f"{name} has no `on:` triggers"

    if isinstance(triggers, dict):
        actual_keys = set(triggers.keys())
    elif isinstance(triggers, list):
        actual_keys = set(triggers)
    else:
        actual_keys = {triggers}

    required = spec["on"]
    missing = required - actual_keys
    assert not missing, f"{name} missing triggers {missing} (has {actual_keys})"
