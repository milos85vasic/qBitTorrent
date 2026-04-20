"""Meta-test: every TS file under frontend/src/app/ must have a sibling spec.

Phase 5 of the completion-initiative plan expanded frontend Vitest
coverage from a single smoke spec to per-component/service/model
coverage. This test locks that expansion in — if somebody adds a new
component or service without a spec, the test fails, nudging them to
write the spec alongside the code.

Rules:
- Every production ``.ts`` file under ``frontend/src/app/`` must have a
  sibling ``<name>.spec.ts`` (same stem + ``.spec.ts``).
- The following files are excluded from the requirement:
  ``*.spec.ts``, ``*.module.ts``, ``*.config.ts``, ``*.routes.ts``,
  barrel ``index.ts``, and ``*.d.ts`` declaration files.
- The project must ship at least 12 spec files (the Phase-5 baseline).
"""
from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "frontend" / "src" / "app"

EXCLUDED_SUFFIXES = (
    ".spec.ts",
    ".module.ts",
    ".config.ts",
    ".routes.ts",
    ".d.ts",
)
EXCLUDED_BASENAMES = ("index.ts",)
MIN_SPEC_COUNT = 12


def _is_production_ts(path: Path) -> bool:
    name = path.name
    if name in EXCLUDED_BASENAMES:
        return False
    return not any(name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES)


def _collect_production_ts() -> list[Path]:
    assert APP_ROOT.is_dir(), f"Frontend app root must exist at {APP_ROOT}"
    return sorted(p for p in APP_ROOT.rglob("*.ts") if _is_production_ts(p))


def _expected_spec_for(src: Path) -> Path:
    return src.with_name(src.stem + ".spec.ts")


def test_frontend_app_root_exists() -> None:
    assert APP_ROOT.is_dir(), f"Expected Angular app root at {APP_ROOT}"


def test_every_production_ts_has_sibling_spec() -> None:
    """Every non-scaffolding TS file gets a co-located .spec.ts."""
    missing: list[tuple[Path, Path]] = []
    for src in _collect_production_ts():
        spec = _expected_spec_for(src)
        if not spec.is_file():
            missing.append((src.relative_to(PROJECT_ROOT), spec.relative_to(PROJECT_ROOT)))
    assert not missing, (
        "Production TS files missing a sibling .spec.ts:\n"
        + "\n".join(f"  {src} -> missing {spec}" for src, spec in missing)
    )


def test_spec_count_meets_baseline() -> None:
    specs = list(APP_ROOT.rglob("*.spec.ts"))
    assert len(specs) >= MIN_SPEC_COUNT, (
        f"Expected at least {MIN_SPEC_COUNT} spec files under {APP_ROOT}, "
        f"found {len(specs)}."
    )


def test_specs_are_non_trivial() -> None:
    """Guard against empty stub specs — every spec must contain at least one it/test."""
    empty: list[Path] = []
    for spec in APP_ROOT.rglob("*.spec.ts"):
        text = spec.read_text(encoding="utf-8")
        if "it(" not in text and "test(" not in text:
            empty.append(spec.relative_to(PROJECT_ROOT))
    assert not empty, (
        "Spec files without any it()/test() blocks:\n"
        + "\n".join(f"  {p}" for p in empty)
    )
