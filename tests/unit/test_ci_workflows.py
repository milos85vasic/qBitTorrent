"""Tests that the expected set of CI workflows exist and have the shape
documented in docs/superpowers/plans/2026-04-19-completion-initiative.md
Phase 0.4.

This catches silent removal/rename of a workflow file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

try:  # PyYAML is ubiquitous in CI, but not a hard dep locally.
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

REQUIRED_WORKFLOWS: dict[str, dict] = {
    "syntax.yml": {"on": {"push", "pull_request"}},
    "unit.yml": {"on": {"push", "pull_request"}},
    "integration.yml": {"on": {"push", "pull_request"}},
    "nightly.yml": {"on": {"schedule"}},
    "security.yml": {"on": {"schedule"}},
}


@pytest.mark.parametrize("name", sorted(REQUIRED_WORKFLOWS))
def test_workflow_file_exists(name: str) -> None:
    assert (WORKFLOW_DIR / name).is_file(), f"missing .github/workflows/{name}"


@pytest.mark.skipif(yaml is None, reason="PyYAML not installed")
@pytest.mark.parametrize("name,spec", sorted(REQUIRED_WORKFLOWS.items()))
def test_workflow_triggers(name: str, spec: dict) -> None:
    data = yaml.safe_load((WORKFLOW_DIR / name).read_text())
    # PyYAML turns the `on:` key into Python True (boolean) because YAML 1.1.
    triggers = data.get(True, data.get("on"))
    assert triggers, f"{name} has no `on:` triggers"
    if isinstance(triggers, dict) or isinstance(triggers, list):
        actual = set(triggers)
    else:
        actual = {triggers}
    required = spec["on"]
    missing = required - actual
    assert not missing, f"{name} missing triggers {missing} (has {actual})"
