"""
Tests for CI pipeline script and systemd service.
"""

import os
import sys
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestCIScript:
    def test_ci_script_exists(self):
        assert os.path.isfile(os.path.join(REPO_ROOT, "ci.sh"))

    def test_ci_script_is_executable(self):
        path = os.path.join(REPO_ROOT, "ci.sh")
        assert os.access(path, os.X_OK)

    def test_ci_script_syntax_valid(self):
        import subprocess

        result = subprocess.run(["bash", "-n", os.path.join(REPO_ROOT, "ci.sh")], capture_output=True, text=True)
        assert result.returncode == 0, f"ci.sh syntax error: {result.stderr}"


class TestSystemdService:
    def test_service_file_exists(self):
        assert os.path.isfile(os.path.join(REPO_ROOT, "webui-bridge.service"))

    def test_setup_script_exists(self):
        assert os.path.isfile(os.path.join(REPO_ROOT, "setup-webui-bridge-service.sh"))

    def test_setup_script_is_executable(self):
        path = os.path.join(REPO_ROOT, "setup-webui-bridge-service.sh")
        assert os.access(path, os.X_OK)

    def test_service_contains_no_secrets(self):
        path = os.path.join(REPO_ROOT, "webui-bridge.service")
        with open(path) as f:
            content = f.read()
        for secret_pattern in ["password=", "secret=", "api_key=", "token="]:
            assert secret_pattern not in content.lower(), f"Service file contains potential secret: {secret_pattern}"

    def test_service_uses_env_file(self):
        path = os.path.join(REPO_ROOT, "webui-bridge.service")
        with open(path) as f:
            content = f.read()
        assert "EnvironmentFile" in content, "Service should load .env via EnvironmentFile"


class TestStartProxy:
    def test_start_proxy_installs_requirements(self):
        path = os.path.join(REPO_ROOT, "start-proxy.sh")
        with open(path) as f:
            content = f.read()
        assert "requirements.txt" in content, "start-proxy.sh should install from requirements.txt"
        assert "pip install" in content

    def test_start_proxy_syntax(self):
        import subprocess

        result = subprocess.run(["sh", "-n", os.path.join(REPO_ROOT, "start-proxy.sh")], capture_output=True, text=True)
        assert result.returncode == 0, f"start-proxy.sh syntax error: {result.stderr}"


class TestGitignore:
    def test_env_is_gitignored(self):
        path = os.path.join(REPO_ROOT, ".gitignore")
        with open(path) as f:
            content = f.read()
        assert ".env" in content
        assert "!.env.example" in content

    def test_qbit_env_is_gitignored(self):
        path = os.path.join(REPO_ROOT, ".gitignore")
        with open(path) as f:
            content = f.read()
        assert ".qbit.env" in content

    def test_key_files_are_gitignored(self):
        path = os.path.join(REPO_ROOT, ".gitignore")
        with open(path) as f:
            content = f.read()
        assert "*.key" in content
        assert "*.pem" in content

    def test_env_not_tracked(self):
        import subprocess

        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".env"], capture_output=True, text=True, cwd=REPO_ROOT
        )
        assert result.returncode != 0, ".env should NOT be tracked by git"
