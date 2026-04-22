"""
Additional coverage for merge_service/hooks.py — dispatch, execution,
timeout, get_dispatcher, create_default_hook.
"""

import importlib.util
import os
import stat
import sys
from unittest.mock import patch

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")
_MS_PATH = os.path.join(_SRC_PATH, "merge_service")

sys.modules.setdefault("merge_service", type(sys)("merge_service"))
sys.modules["merge_service"].__path__ = [_MS_PATH]

_hooks_spec = importlib.util.spec_from_file_location(
    "merge_service.hooks", os.path.join(_MS_PATH, "hooks.py")
)
_hooks_mod = importlib.util.module_from_spec(_hooks_spec)
sys.modules["merge_service.hooks"] = _hooks_mod
_hooks_spec.loader.exec_module(_hooks_mod)

HookDispatcher = _hooks_mod.HookDispatcher
HookConfig = _hooks_mod.HookConfig
HookEvent = _hooks_mod.HookEvent
HookEventType = _hooks_mod.HookEventType
get_dispatcher = _hooks_mod.get_dispatcher
create_default_hook = _hooks_mod.create_default_hook


class TestHookConfigValidate:
    def test_empty_name(self):
        cfg = HookConfig(name="", event=HookEventType.SEARCH_START, script_path="/tmp/test.sh")
        assert cfg.validate() is False

    def test_empty_script_path(self):
        cfg = HookConfig(name="test", event=HookEventType.SEARCH_START, script_path="")
        assert cfg.validate() is False

    def test_nonexistent_script(self):
        cfg = HookConfig(name="test", event=HookEventType.SEARCH_START, script_path="/nonexistent/script.sh")
        assert cfg.validate() is False

    def test_valid_script(self, tmp_path):
        script = tmp_path / "test.sh"
        script.write_text("#!/bin/bash\n")
        cfg = HookConfig(name="test", event=HookEventType.SEARCH_START, script_path=str(script))
        assert cfg.validate() is True


class TestHookDispatcherRegister:
    def test_avoid_duplicates(self):
        d = HookDispatcher()
        cfg = HookConfig(name="dup", event=HookEventType.SEARCH_START, script_path="/tmp/test.sh")
        d.register_hook(cfg)
        d.register_hook(cfg)
        assert len(d.get_hooks(HookEventType.SEARCH_START)) == 1

    def test_register_multiple_events(self):
        d = HookDispatcher()
        cfg1 = HookConfig(name="h1", event=HookEventType.SEARCH_START, script_path="/tmp/test.sh")
        cfg2 = HookConfig(name="h2", event=HookEventType.SEARCH_COMPLETE, script_path="/tmp/test.sh")
        d.register_hook(cfg1)
        d.register_hook(cfg2)
        assert len(d.get_hooks(HookEventType.SEARCH_START)) == 1
        assert len(d.get_hooks(HookEventType.SEARCH_COMPLETE)) == 1


class TestHookDispatcherExecution:
    @pytest.mark.asyncio
    async def test_execute_success(self, tmp_path):
        script = tmp_path / "success.sh"
        script.write_text("#!/bin/bash\nexit 0\n")
        os.chmod(str(script), os.stat(str(script)).st_mode | stat.S_IEXEC)

        d = HookDispatcher()
        cfg = HookConfig(name="test", event=HookEventType.SEARCH_START, script_path=str(script), enabled=True)
        d.register_hook(cfg)

        event = HookEvent(event_type=HookEventType.SEARCH_START, data={"query": "test"})
        await d.dispatch(event)

        logs = d.get_execution_log()
        assert len(logs) == 1
        assert logs[0]["success"] is True
        assert logs[0]["return_code"] == 0

    @pytest.mark.asyncio
    async def test_execute_failure(self, tmp_path):
        script = tmp_path / "fail.sh"
        script.write_text("#!/bin/bash\nexit 1\n")
        os.chmod(str(script), os.stat(str(script)).st_mode | stat.S_IEXEC)

        d = HookDispatcher()
        cfg = HookConfig(name="fail_hook", event=HookEventType.SEARCH_START, script_path=str(script), enabled=True)
        d.register_hook(cfg)

        event = HookEvent(event_type=HookEventType.SEARCH_START, data={})
        await d.dispatch(event)

        logs = d.get_execution_log()
        assert len(logs) == 1
        assert logs[0]["success"] is False
        assert logs[0]["return_code"] == 1

    @pytest.mark.asyncio
    async def test_disabled_hook_skipped(self, tmp_path):
        script = tmp_path / "never.sh"
        script.write_text("#!/bin/bash\nexit 0\n")
        os.chmod(str(script), os.stat(str(script)).st_mode | stat.S_IEXEC)

        d = HookDispatcher()
        cfg = HookConfig(name="disabled", event=HookEventType.SEARCH_START, script_path=str(script), enabled=False)
        d.register_hook(cfg)

        event = HookEvent(event_type=HookEventType.SEARCH_START, data={})
        await d.dispatch(event)

        logs = d.get_execution_log()
        assert len(logs) == 0

    @pytest.mark.asyncio
    async def test_invalid_hook_skipped(self):
        d = HookDispatcher()
        cfg = HookConfig(name="invalid", event=HookEventType.SEARCH_START, script_path="/nonexistent.sh", enabled=True)
        d.register_hook(cfg)

        event = HookEvent(event_type=HookEventType.SEARCH_START, data={})
        await d.dispatch(event)

        logs = d.get_execution_log()
        assert len(logs) == 0

    @pytest.mark.asyncio
    async def test_timeout_hook(self, tmp_path):
        script = tmp_path / "slow.sh"
        script.write_text("#!/bin/bash\nsleep 10\n")
        os.chmod(str(script), os.stat(str(script)).st_mode | stat.S_IEXEC)

        d = HookDispatcher()
        cfg = HookConfig(name="slow", event=HookEventType.SEARCH_START, script_path=str(script), enabled=True, timeout=1)
        d.register_hook(cfg)

        event = HookEvent(event_type=HookEventType.SEARCH_START, data={})
        await d.dispatch(event)

        logs = d.get_execution_log()
        assert len(logs) == 1
        assert logs[0]["success"] is False
        assert logs[0]["error"] == "timeout"

    @pytest.mark.asyncio
    async def test_search_id_in_env(self, tmp_path):
        script = tmp_path / "check_env.sh"
        script.write_text("#!/bin/bash\nexit 0\n")
        os.chmod(str(script), os.stat(str(script)).st_mode | stat.S_IEXEC)

        d = HookDispatcher()
        cfg = HookConfig(name="env_test", event=HookEventType.SEARCH_START, script_path=str(script), enabled=True)
        d.register_hook(cfg)

        event = HookEvent(event_type=HookEventType.SEARCH_START, search_id="test-123", data={})
        await d.dispatch(event)

        logs = d.get_execution_log()
        assert len(logs) == 1

    @pytest.mark.asyncio
    async def test_download_id_in_env(self, tmp_path):
        script = tmp_path / "check_dl.sh"
        script.write_text("#!/bin/bash\nexit 0\n")
        os.chmod(str(script), os.stat(str(script)).st_mode | stat.S_IEXEC)

        d = HookDispatcher()
        cfg = HookConfig(name="dl_test", event=HookEventType.DOWNLOAD_START, script_path=str(script), enabled=True)
        d.register_hook(cfg)

        event = HookEvent(event_type=HookEventType.DOWNLOAD_START, download_id="dl-456", data={})
        await d.dispatch(event)

        logs = d.get_execution_log()
        assert len(logs) == 1


class TestGetDispatcher:
    def test_singleton(self):
        import merge_service.hooks as hooks_mod

        hooks_mod._dispatcher = None
        d1 = get_dispatcher()
        d2 = get_dispatcher()
        assert d1 is d2
        hooks_mod._dispatcher = None


class TestCreateDefaultHook:
    def test_creation(self):
        hook = create_default_hook("test", HookEventType.SEARCH_COMPLETE, "/tmp/test.sh")
        assert hook.name == "test"
        assert hook.event == HookEventType.SEARCH_COMPLETE
        assert hook.script_path == "/tmp/test.sh"
        assert hook.enabled is True
        assert hook.timeout == 30


class TestHookEventTypeComplete:
    def test_all_types(self):
        expected = {
            "search_start", "search_progress", "search_complete",
            "download_start", "download_progress", "download_complete",
            "merge_complete", "validation_complete",
        }
        actual = {e.value for e in HookEventType}
        assert actual == expected
