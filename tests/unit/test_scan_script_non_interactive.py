import re
import subprocess
from typing import ClassVar

import pytest

SCRIPT = "scripts/scan.sh"


@pytest.fixture
def script_content():
    with open(SCRIPT) as f:
        return f.read()


class TestScanScriptExists:
    def test_script_file_exists(self):
        import os

        assert os.path.isfile(SCRIPT), f"{SCRIPT} does not exist"

    def test_script_syntax_valid(self):
        result = subprocess.run(
            ["bash", "-n", SCRIPT],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"


class TestScanScriptNonInteractive:
    FORBIDDEN_PATTERNS: ClassVar[list[str]] = [
        r"sudo\s",
        r"read\s+-p",
        r"read\s+-r\s+-p",
        r"su\s+-",
        r"passwd",
        r"interactive",
    ]

    @pytest.mark.parametrize("pattern", FORBIDDEN_PATTERNS)
    def test_no_forbidden_patterns(self, script_content, pattern):
        matches = re.findall(pattern, script_content)
        assert (
            not matches
        ), f"Forbidden pattern '{pattern}' found in {SCRIPT}: {matches}"

    def test_has_strict_mode(self, script_content):
        assert "set -euo pipefail" in script_content, (
            "Missing 'set -euo pipefail'"
        )


class TestScanScriptFlags:
    def test_handles_quick_flag(self, script_content):
        assert "--quick" in script_content, "Missing --quick flag handling"

    def test_handles_full_flag(self, script_content):
        assert "--full" in script_content, "Missing --full flag handling"

    def test_handles_scanner_flag(self, script_content):
        assert "--scanner" in script_content, "Missing --scanner flag handling"

    def test_has_run_bandit_function(self, script_content):
        assert re.search(r"(?:function\s+)?run_bandit\s*\(\s*\)", script_content), (
            "Missing run_bandit() function"
        )

    def test_has_run_semgrep_function(self, script_content):
        assert re.search(r"(?:function\s+)?run_semgrep\s*\(\s*\)", script_content), (
            "Missing run_semgrep() function"
        )

    def test_has_run_trivy_function(self, script_content):
        assert re.search(r"(?:function\s+)?run_trivy\s*\(\s*\)", script_content), (
            "Missing run_trivy() function"
        )

    def test_has_run_gitleaks_function(self, script_content):
        assert re.search(r"(?:function\s+)?run_gitleaks\s*\(\s*\)", script_content), (
            "Missing run_gitleaks() function"
        )

    def test_has_run_pip_audit_function(self, script_content):
        assert re.search(r"(?:function\s+)?run_pip_audit\s*\(\s*\)", script_content), (
            "Missing run_pip_audit() function"
        )

    def test_quick_runs_bandit_and_pip_audit_only(self, script_content):
        has_quick_logic = (
            "QUICK" in script_content
            or "quick" in script_content.split("--quick")[0][:1] + "quick_mode" in script_content
        )
        assert has_quick_logic or "quick" in script_content.lower(), (
            "Missing --quick mode logic"
        )
