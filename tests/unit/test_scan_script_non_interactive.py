"""Guards the non-interactive / no-sudo invariants of scripts/scan.sh.

These invariants come directly from the user's constraint that
*no command we run may prompt for a root/sudo password* and from the
completion-initiative plan Part E.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_SH = REPO_ROOT / "scripts" / "scan.sh"

FORBIDDEN_PATTERNS = [
    "sudo ",
    "sudo\t",
    "read -p",
    "read -sp",
    r"passwd ",
    "su - ",
    "su -c ",
    "--interactive",
]


def test_scan_sh_exists_and_is_executable() -> None:
    assert SCAN_SH.is_file(), SCAN_SH
    assert SCAN_SH.stat().st_mode & 0o111, "scripts/scan.sh must be executable"


def test_scan_sh_has_strict_flags() -> None:
    text = SCAN_SH.read_text()
    assert "set -euo pipefail" in text, "scripts/scan.sh must `set -euo pipefail`"


@pytest.mark.parametrize("pattern", FORBIDDEN_PATTERNS)
def test_scan_sh_has_no_interactive_or_privilege_patterns(pattern: str) -> None:
    text = SCAN_SH.read_text()
    # Allow the string to appear only inside docstrings/comments is awkward
    # to detect. The simplest rule is: forbid entirely — if we need them,
    # document the exception here and add an explicit allowlist.
    assert pattern not in text, f"scripts/scan.sh contains forbidden pattern {pattern!r}"


def test_scan_sh_never_reads_from_stdin() -> None:
    # `read` without `-p` or a here-doc is still stdin-gated and may hang
    # non-interactive runs. We forbid bare `read ` invocations.
    text = SCAN_SH.read_text()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Allow `read -r line` only inside explicit here-strings (detected by `<<<`).
        if stripped.startswith("read ") and "<<<" not in stripped:
            pytest.fail(f"`read` reads from stdin non-interactively: {line!r}")


def test_scan_sh_respects_container_runtime_autodetect() -> None:
    text = SCAN_SH.read_text()
    assert "detect_container_runtime" in text, "scripts/scan.sh must implement runtime auto-detection (constitution IV)"
    assert "podman" in text
    assert "docker" in text
