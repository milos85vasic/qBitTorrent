import tomllib
from pathlib import Path
from typing import ClassVar

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent

CONFIG_FILES = [
    "sonar-project.properties",
    ".snyk",
    ".semgrep.yml",
    ".gitleaks.toml",
    ".trivyignore.yaml",
]


class TestScannerConfigsExist:
    def test_all_config_files_exist(self):
        for name in CONFIG_FILES:
            assert (ROOT / name).is_file(), f"missing scanner config: {name}"


class TestSonarProjectProperties:
    REQUIRED_KEYS: ClassVar[list[str]] = [
        "sonar.sources",
        "sonar.tests",
        "sonar.python.coverage.reportPaths",
    ]

    def _parse(self):
        props: dict[str, str] = {}
        for line in (ROOT / "sonar-project.properties").read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, value = stripped.partition("=")
                props[key.strip()] = value.strip()
        return props

    def test_has_required_keys(self):
        props = self._parse()
        for key in self.REQUIRED_KEYS:
            assert key in props, f"sonar-project.properties missing key: {key}"

    def test_python_version_is_312(self):
        props = self._parse()
        assert props.get("sonar.python.version") == "3.12"

    def test_source_encoding(self):
        props = self._parse()
        assert props.get("sonar.sourceEncoding") == "UTF-8"


class TestSemgrepYml:
    def test_valid_yaml(self):
        data = yaml.safe_load((ROOT / ".semgrep.yml").read_text())
        assert isinstance(data, dict)

    def test_has_rules(self):
        data = yaml.safe_load((ROOT / ".semgrep.yml").read_text())
        assert "rules" in data
        assert isinstance(data["rules"], list)
        assert len(data["rules"]) > 0

    def test_rules_have_required_fields(self):
        data = yaml.safe_load((ROOT / ".semgrep.yml").read_text())
        for rule in data["rules"]:
            assert "id" in rule, f"semgrep rule missing id: {rule}"
            assert "message" in rule, f"semgrep rule missing message: {rule.get('id')}"
            assert "severity" in rule, f"semgrep rule missing severity: {rule.get('id')}"


class TestGitleaksToml:
    def test_valid_toml(self):
        data = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
        assert isinstance(data, dict)

    def test_has_allowlist(self):
        data = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
        assert "allowlist" in data

    def test_allowlist_has_paths(self):
        data = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
        assert "paths" in data["allowlist"]
        assert isinstance(data["allowlist"]["paths"], list)

    def test_allowlist_excludes_test_fixtures_and_config(self):
        data = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
        paths_text = " ".join(data["allowlist"]["paths"])
        assert "tests/fixtures" in paths_text
        assert "config/" in paths_text or "config" in paths_text

    def test_uses_default_rules(self):
        data = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
        assert "extend" in data
        assert data["extend"].get("useDefault") is True


class TestSnykPolicy:
    def test_valid_yaml(self):
        data = yaml.safe_load((ROOT / ".snyk").read_text())
        assert isinstance(data, dict)

    def test_has_severity_threshold(self):
        data = yaml.safe_load((ROOT / ".snyk").read_text())
        assert "severity-threshold" in data or "severity" in str(data).lower()

    def test_has_fail_on(self):
        data = yaml.safe_load((ROOT / ".snyk").read_text())
        assert "fail-on" in data or "fail" in str(data).lower()

    def test_has_ignore_section(self):
        data = yaml.safe_load((ROOT / ".snyk").read_text())
        assert "ignore" in data


class TestTrivyIgnoreYaml:
    def test_valid_yaml(self):
        data = yaml.safe_load((ROOT / ".trivyignore.yaml").read_text())
        assert isinstance(data, dict)

    def test_has_ignores_section(self):
        data = yaml.safe_load((ROOT / ".trivyignore.yaml").read_text())
        assert "ignores" in data or "vulnerabilities" in data or "ids" in data
