"""Architecture-diagram contract tests.

Fails if any of the five Mermaid architecture diagrams promised by
Phase 7 of the completion-initiative plan disappears from
`docs/architecture/`.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIAGRAMS_DIR = ROOT / "docs" / "architecture"


REQUIRED_DIAGRAMS = [
    "container-topology.mmd",
    "search-lifecycle.mmd",
    "plugin-execution.mmd",
    "private-tracker-bridge.mmd",
    "shutdown-sequence.mmd",
]


def test_architecture_directory_exists():
    assert DIAGRAMS_DIR.is_dir(), f"docs/architecture/ is missing — expected at {DIAGRAMS_DIR}"


def test_every_required_diagram_is_present():
    missing: list[str] = []
    for filename in REQUIRED_DIAGRAMS:
        if not (DIAGRAMS_DIR / filename).is_file():
            missing.append(filename)
    assert missing == [], f"missing diagrams under docs/architecture/: {missing}"


def test_diagrams_are_non_trivial():
    """A mostly-empty .mmd file defeats the purpose of the guard."""
    undersize: list[str] = []
    for filename in REQUIRED_DIAGRAMS:
        path = DIAGRAMS_DIR / filename
        if path.is_file() and path.stat().st_size < 100:
            undersize.append(filename)
    assert undersize == [], f"diagram files under 100 bytes: {undersize}"


def test_diagrams_declare_a_mermaid_directive():
    """Every .mmd should start with a Mermaid comment or a known diagram type."""
    broken: list[str] = []
    valid_starts = (
        "%%",
        "graph ",
        "flowchart ",
        "sequenceDiagram",
        "classDiagram",
        "stateDiagram",
        "erDiagram",
        "gantt",
        "pie",
        "journey",
    )
    for filename in REQUIRED_DIAGRAMS:
        path = DIAGRAMS_DIR / filename
        if not path.is_file():
            continue
        first_line = path.read_text().lstrip().splitlines()[0] if path.read_text().strip() else ""
        if not any(first_line.startswith(prefix) for prefix in valid_starts):
            broken.append(filename)
    assert broken == [], f"diagrams missing a Mermaid directive on the first non-blank line: {broken}"
