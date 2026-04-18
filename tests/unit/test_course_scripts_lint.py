"""`bash -n` syntax lint for every course `demo.sh`.

We cannot rely on `shellcheck` being installed in every CI or
developer environment, but `bash -n` ships with bash itself and
catches all the compile-time syntax errors that matter for a script
meant to run unattended inside an Asciinema recording session.

Each `demo.sh` is a non-interactive replay script (see
`tests/unit/test_courses_scaffold.py` for the content invariants).
This file only worries about syntax.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COURSES_DIR = REPO_ROOT / "courses"

TRACKS = (
    "01-operator",
    "02-plugin-author",
    "03-contributor",
    "04-security-ops",
)


def _bash_binary() -> str | None:
    return shutil.which("bash")


@pytest.mark.parametrize("track", TRACKS)
def test_demo_sh_passes_bash_n(track: str) -> None:
    bash = _bash_binary()
    if bash is None:
        pytest.skip("bash not installed on this host")
    demo = COURSES_DIR / track / "demo.sh"
    assert demo.is_file(), f"courses/{track}/demo.sh missing"
    result = subprocess.run(
        [bash, "-n", str(demo)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"`bash -n {demo}` reported a syntax error:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
