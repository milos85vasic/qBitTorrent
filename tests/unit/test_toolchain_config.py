"""Tests that the repo's unified tool config (pyproject.toml) declares
pytest, coverage, ruff, and mypy sections with the values required by
the completion-initiative plan (Phase 0.1).

These tests are the RED step — they fail until Phase 0.1 lands.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"


@pytest.fixture(scope="module")
def pyproject() -> dict:
    assert PYPROJECT.is_file(), f"pyproject.toml is missing at {PYPROJECT}"
    return tomllib.loads(PYPROJECT.read_text())


def test_pyproject_declares_project_metadata(pyproject: dict) -> None:
    project = pyproject.get("project", {})
    assert project.get("name") == "qbittorrent-fixed"
    assert project.get("requires-python", "").startswith(">=3.12")


def test_pytest_ini_options_strict_and_cov(pyproject: dict) -> None:
    """Strictness knobs must be on by default; coverage flags moved
    out of `addopts` and into ``scripts/run-tests.sh`` on 2026-04-20
    so single-file pytest runs stop failing the 1 % `fail_under`
    gate. See CLAUDE.md + docs/TEST_SUITE_GUIDE.md.
    """
    opts = pyproject["tool"]["pytest"]["ini_options"]
    addopts_joined = " ".join(opts["addopts"])
    for flag in ("-ra", "--strict-markers", "--strict-config"):
        assert flag in addopts_joined, f"pytest addopts missing {flag!r}: {addopts_joined!r}"
    # Coverage flags MUST NOT be in default addopts (they live in
    # scripts/run-tests.sh instead).
    for banned in ("--cov=", "--cov-report"):
        assert banned not in addopts_joined, (
            f"pytest addopts must not contain {banned!r}; coverage lives "
            f"in scripts/run-tests.sh now"
        )
    # But the run-tests.sh wrapper must still configure coverage.
    import pathlib
    runner = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "run-tests.sh"
    assert runner.is_file(), "scripts/run-tests.sh must exist"
    runner_src = runner.read_text(encoding="utf-8")
    for flag in ("--cov=download-proxy/src", "--cov=plugins", "--cov-report=term-missing"):
        assert flag in runner_src, f"scripts/run-tests.sh missing {flag!r}"
    assert opts["testpaths"] == ["tests"]
    assert "asyncio_mode" in opts
    assert opts["asyncio_mode"] == "auto"


def test_pytest_registers_required_markers(pyproject: dict) -> None:
    markers = pyproject["tool"]["pytest"]["ini_options"]["markers"]
    required = {
        "requires_credentials",
        "requires_compose",
        "slow",
        "stress",
        "security",
        "contract",
        "property",
    }
    marker_names = {m.split(":", 1)[0].strip() for m in markers}
    missing = required - marker_names
    assert not missing, f"missing markers: {missing}"


def test_coverage_source_and_report(pyproject: dict) -> None:
    run = pyproject["tool"]["coverage"]["run"]
    assert "download-proxy/src" in run["source"]
    assert "plugins" in run["source"]
    report = pyproject["tool"]["coverage"]["report"]
    assert report["fail_under"] >= 1  # baseline gate; raised per phase
    assert report["show_missing"] is True
    assert report["skip_empty"] is True


def test_ruff_config_migrated(pyproject: dict) -> None:
    ruff = pyproject["tool"]["ruff"]
    assert ruff["target-version"] == "py312"
    assert ruff["line-length"] == 120
    select = ruff["lint"]["select"]
    for code in ("E", "F", "W", "I", "UP", "B", "SIM", "RUF", "ASYNC"):
        assert code in select, f"ruff select missing {code!r}: {select}"


def test_mypy_strict_on_new_modules(pyproject: dict) -> None:
    mypy = pyproject["tool"]["mypy"]
    assert mypy["python_version"] == "3.12"
    assert mypy["strict"] is True
    assert mypy["warn_unused_ignores"] is True
    assert mypy["warn_redundant_casts"] is True
