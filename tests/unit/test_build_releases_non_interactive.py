"""Guards the release builder against interactive prompts and privilege
escalation, per the same invariants enforced on scripts/scan.sh.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SH = REPO_ROOT / "scripts" / "build-releases.sh"
RELEASES_DIR = REPO_ROOT / "releases"
RELEASES_README = RELEASES_DIR / "README.md"

FORBIDDEN_PATTERNS = [
    "sudo ",
    "sudo\t",
    "read -p",
    "read -sp",
    "passwd ",
    "su - ",
    "su -c ",
    "--interactive",
]


def test_build_releases_exists_and_executable() -> None:
    assert BUILD_SH.is_file()
    assert BUILD_SH.stat().st_mode & 0o111


def test_build_releases_has_strict_flags() -> None:
    assert "set -euo pipefail" in BUILD_SH.read_text()


@pytest.mark.parametrize("pattern", FORBIDDEN_PATTERNS)
def test_build_releases_non_interactive(pattern: str) -> None:
    assert pattern not in BUILD_SH.read_text(), f"forbidden pattern: {pattern!r}"


def test_build_releases_autodetects_container_runtime() -> None:
    text = BUILD_SH.read_text()
    assert "detect_container_runtime" in text
    assert "podman" in text
    assert "docker" in text


def test_releases_directory_exists_and_has_readme() -> None:
    assert RELEASES_DIR.is_dir()
    assert RELEASES_README.is_file()
    assert RELEASES_README.stat().st_size > 200


def test_releases_directory_is_gitignored() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text()
    assert "releases/" in gitignore
    # The two tracked files must be re-included
    assert "!releases/README.md" in gitignore
    assert "!releases/.gitkeep" in gitignore
