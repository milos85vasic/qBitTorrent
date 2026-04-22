import subprocess
from pathlib import Path

COURSES_DIR = Path(__file__).resolve().parent.parent.parent / "courses"
COURSE_DIRS = sorted(COURSES_DIR.glob("0*"))
FORBIDDEN_PATTERNS = ["sudo ", "read -p", "read -r -p"]


class TestCourseDirectories:
    def test_courses_root_exists(self) -> None:
        assert COURSES_DIR.is_dir(), f"courses/ directory not found at {COURSES_DIR}"

    def test_expected_course_count(self) -> None:
        expected = {"01-operator", "02-plugin-author", "03-contributor", "04-security-ops"}
        actual = {d.name for d in COURSE_DIRS}
        assert actual == expected, f"Expected {expected}, got {actual}"

    def test_each_course_has_script_md(self) -> None:
        for course_dir in COURSE_DIRS:
            script = course_dir / "script.md"
            assert script.is_file(), f"Missing script.md in {course_dir.name}"

    def test_each_course_has_readme(self) -> None:
        for course_dir in COURSE_DIRS:
            readme = course_dir / "README.md"
            assert readme.is_file(), f"Missing README.md in {course_dir.name}"

    def test_each_course_has_demo_script(self) -> None:
        for course_dir in COURSE_DIRS:
            demo = course_dir / "demo.sh"
            assert demo.is_file(), f"Missing demo.sh in {course_dir.name}"


class TestDemoScriptSyntax:
    def test_demo_scripts_pass_bash_n(self) -> None:
        for course_dir in COURSE_DIRS:
            demo = course_dir / "demo.sh"
            result = subprocess.run(
                ["bash", "-n", str(demo)],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, (
                f"bash -n failed for {demo}: {result.stderr}"
            )


class TestDemoScriptForbiddenPatterns:
    def test_no_forbidden_patterns(self) -> None:
        for course_dir in COURSE_DIRS:
            demo = course_dir / "demo.sh"
            content = demo.read_text()
            for pattern in FORBIDDEN_PATTERNS:
                assert pattern not in content, (
                    f"Forbidden pattern '{pattern}' found in {demo}"
                )

    def test_has_set_euo_pipefail(self) -> None:
        for course_dir in COURSE_DIRS:
            demo = course_dir / "demo.sh"
            content = demo.read_text()
            assert "set -euo pipefail" in content, (
                f"Missing 'set -euo pipefail' in {demo}"
            )
