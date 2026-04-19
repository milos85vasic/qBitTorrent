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
# Per owner directive (2026-04-19) all GitHub Actions were disabled.
# The YAMLs still live in .github/workflows-disabled/ so they can be
# re-enabled with a single `git mv`. Until then, this test validates
# their presence + shape at the DISABLED location so silent removal
# or accidental re-introduction of triggers is caught.
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows-disabled"

REQUIRED_WORKFLOWS: dict[str, dict] = {
    "syntax.yml": {"on": {"push", "pull_request"}},
    "unit.yml": {"on": {"push", "pull_request"}},
    "integration.yml": {"on": {"push", "pull_request"}},
    "nightly.yml": {"on": {"schedule"}},
    "security.yml": {"on": {"schedule"}},
}


def test_active_workflows_directory_is_empty() -> None:
    """GitHub Actions directory must not contain active YAML triggers
    while workflows are disabled. A stray file here would re-activate
    CI by accident.
    """
    active = REPO_ROOT / ".github" / "workflows"
    if not active.exists():
        return
    yamls = [p for p in active.iterdir() if p.suffix in (".yml", ".yaml")]
    assert yamls == [], f".github/workflows/ must be empty while disabled, found: {yamls}"


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
