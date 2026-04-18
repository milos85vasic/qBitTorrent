"""Docs-presence contract tests.

These tests fail if a top-level directory loses its README.md, or if a
canonical subsystem document disappears from `docs/`. They lock the
documentation contract delivered in Phase 7 of the completion-initiative
plan so a later refactor cannot silently delete these files.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


TOP_LEVEL_DIRS_WITH_README = [
    "docs",
    "download-proxy",
    "plugins",
    "specs",
    "tools",
    "config",
    "Upstreams",
    "tmp",
    ".specify",
]


REQUIRED_SUBSYSTEM_DOCS = [
    "TESTING",
    "SECURITY",
    "CONCURRENCY",
    "OBSERVABILITY",
    "PERFORMANCE",
    "DATA_MODEL",
    "SCANNING",
    "QUALITY_STACK",
    "COVERAGE_BASELINE",
]


def test_every_top_level_directory_has_readme():
    missing: list[str] = []
    for name in TOP_LEVEL_DIRS_WITH_README:
        readme = ROOT / name / "README.md"
        if not readme.is_file():
            missing.append(str(readme.relative_to(ROOT)))
    assert missing == [], f"missing README.md files: {missing}"


def test_required_subsystem_docs_exist():
    missing: list[str] = []
    for stem in REQUIRED_SUBSYSTEM_DOCS:
        doc = ROOT / "docs" / f"{stem}.md"
        if not doc.is_file():
            missing.append(str(doc.relative_to(ROOT)))
    assert missing == [], f"missing subsystem docs under docs/: {missing}"


def test_readmes_are_non_empty():
    """A present-but-empty README defeats the purpose of this guard."""
    undersize: list[str] = []
    for name in TOP_LEVEL_DIRS_WITH_README:
        readme = ROOT / name / "README.md"
        if readme.is_file() and readme.stat().st_size < 200:
            undersize.append(str(readme.relative_to(ROOT)))
    assert undersize == [], f"README.md files under 200 bytes: {undersize}"
