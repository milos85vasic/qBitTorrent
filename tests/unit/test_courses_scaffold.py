"""Structural guards for the Asciinema video-course scaffold.

These tests fail loudly if:

- `courses/` disappears or any of the four canonical tracks is
  missing.
- A track drops `README.md`, `script.md`, `demo.sh`, or `demo.cast`.
- Any `demo.sh` loses the `set -euo pipefail` header, acquires a
  `sudo`, gains an interactive `read -p`, or adds an
  `--interactive` flag.
- Any `demo.cast` is not valid Asciinema v2 JSON-lines (header
  object with `version: 2`, `width`, `height`; subsequent lines are
  JSON arrays of length three).
- `courses/README.md` drops below 40 lines.

Kept deliberately offline: no network, no asciinema binary, no bash
invocation. Pure text assertions over committed files.

Part of Phase 9 of the completion-initiative plan.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COURSES_DIR = REPO_ROOT / "courses"

EXPECTED_TRACKS = (
    "01-operator",
    "02-plugin-author",
    "03-contributor",
    "04-security-ops",
)

REQUIRED_TRACK_FILES = ("README.md", "script.md", "demo.sh", "demo.cast")

FORBIDDEN_DEMO_TOKENS = (
    "sudo ",
    "read -p",
    "--interactive",
)

REQUIRED_DEMO_HEADER = "set -euo pipefail"

COURSES_README_MIN_LINES = 40


# --------------------------------------------------------------------------- #
# directory layout
# --------------------------------------------------------------------------- #


def test_courses_directory_exists() -> None:
    assert COURSES_DIR.is_dir(), f"courses/ is missing at {COURSES_DIR}"


def test_courses_readme_exists_and_is_substantive() -> None:
    readme = COURSES_DIR / "README.md"
    assert readme.is_file(), "courses/README.md is missing"
    line_count = sum(1 for _ in readme.read_text(encoding="utf-8").splitlines())
    assert line_count >= COURSES_README_MIN_LINES, (
        f"courses/README.md must be at least {COURSES_README_MIN_LINES} lines "
        f"(got {line_count})"
    )


@pytest.mark.parametrize("track", EXPECTED_TRACKS)
def test_track_directory_exists(track: str) -> None:
    track_dir = COURSES_DIR / track
    assert track_dir.is_dir(), f"courses/{track}/ is missing"


@pytest.mark.parametrize("track", EXPECTED_TRACKS)
@pytest.mark.parametrize("filename", REQUIRED_TRACK_FILES)
def test_track_has_required_file(track: str, filename: str) -> None:
    path = COURSES_DIR / track / filename
    assert path.is_file(), f"courses/{track}/{filename} is missing"
    assert path.stat().st_size > 0, f"courses/{track}/{filename} is empty"


# --------------------------------------------------------------------------- #
# demo.sh invariants
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("track", EXPECTED_TRACKS)
def test_demo_sh_has_strict_header(track: str) -> None:
    body = (COURSES_DIR / track / "demo.sh").read_text(encoding="utf-8")
    assert REQUIRED_DEMO_HEADER in body, (
        f"courses/{track}/demo.sh must contain `{REQUIRED_DEMO_HEADER}`"
    )


@pytest.mark.parametrize("track", EXPECTED_TRACKS)
@pytest.mark.parametrize("token", FORBIDDEN_DEMO_TOKENS)
def test_demo_sh_is_non_interactive(track: str, token: str) -> None:
    body = (COURSES_DIR / track / "demo.sh").read_text(encoding="utf-8")
    assert token not in body, (
        f"courses/{track}/demo.sh must not contain `{token.strip()}` "
        "(interactive / privileged)"
    )


# --------------------------------------------------------------------------- #
# demo.cast format validation
# --------------------------------------------------------------------------- #


def _parse_cast_lines(cast_path: Path) -> tuple[dict, list[list]]:
    """Return (header, events). Raises AssertionError on malformed input."""
    raw_lines = cast_path.read_text(encoding="utf-8").splitlines()
    non_empty = [line for line in raw_lines if line.strip()]
    assert non_empty, f"{cast_path} is empty"

    try:
        header = json.loads(non_empty[0])
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{cast_path} header is not valid JSON: {exc}") from exc
    assert isinstance(header, dict), f"{cast_path} header must be a JSON object"

    events: list[list] = []
    for idx, line in enumerate(non_empty[1:], start=2):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"{cast_path}:{idx} is not valid JSON: {exc}"
            ) from exc
        assert isinstance(event, list), (
            f"{cast_path}:{idx} must be a JSON array, got {type(event).__name__}"
        )
        assert len(event) == 3, (
            f"{cast_path}:{idx} must have exactly 3 elements (timestamp, type, data); "
            f"got {len(event)}"
        )
        events.append(event)
    return header, events


@pytest.mark.parametrize("track", EXPECTED_TRACKS)
def test_demo_cast_header_is_valid_v2(track: str) -> None:
    cast = COURSES_DIR / track / "demo.cast"
    header, _events = _parse_cast_lines(cast)
    assert header.get("version") == 2, (
        f"{cast} header must have version: 2 (got {header.get('version')!r})"
    )
    assert "width" in header, f"{cast} header is missing `width`"
    assert "height" in header, f"{cast} header is missing `height`"
    assert isinstance(header["width"], int) and header["width"] > 0
    assert isinstance(header["height"], int) and header["height"] > 0


@pytest.mark.parametrize("track", EXPECTED_TRACKS)
def test_demo_cast_has_at_least_one_event(track: str) -> None:
    cast = COURSES_DIR / track / "demo.cast"
    _header, events = _parse_cast_lines(cast)
    assert events, f"{cast} has a header but no events; need at least one `[ts, type, data]` row"
