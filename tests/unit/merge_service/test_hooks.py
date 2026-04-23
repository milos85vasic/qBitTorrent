"""
Unit tests for the hooks module.
"""

import importlib.util
import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SRC_PATH = os.path.join(_REPO_ROOT, "download-proxy", "src")
_MS_PATH = os.path.join(_SRC_PATH, "merge_service")

sys.modules.setdefault("merge_service", type(sys)("merge_service"))
sys.modules["merge_service"].__path__ = [_MS_PATH]

_hooks_spec = importlib.util.spec_from_file_location("merge_service.hooks", os.path.join(_MS_PATH, "hooks.py"))
_hooks_mod = importlib.util.module_from_spec(_hooks_spec)
sys.modules["merge_service.hooks"] = _hooks_mod
_hooks_spec.loader.exec_module(_hooks_mod)

HookDispatcher = _hooks_mod.HookDispatcher
HookConfig = _hooks_mod.HookConfig
HookEvent = _hooks_mod.HookEvent
HookEventType = _hooks_mod.HookEventType

from merge_service.hooks import (
    HookConfig,
    HookDispatcher,
    HookEvent,
    HookEventType,
)


class TestHookEventType:
    """Tests for HookEventType enum."""

    def test_values(self):
        """Test all hook event type values."""
        assert HookEventType.SEARCH_START.value == "search_start"
        assert HookEventType.SEARCH_COMPLETE.value == "search_complete"
        assert HookEventType.DOWNLOAD_START.value == "download_start"
        assert HookEventType.DOWNLOAD_COMPLETE.value == "download_complete"


class TestHookEvent:
    """Tests for HookEvent dataclass."""

    def test_creation(self):
        """Test HookEvent creation."""
        event = HookEvent(
            event_type=HookEventType.SEARCH_COMPLETE,
            search_id="test-123",
            data={"results": 10},
        )

        assert event.event_type == HookEventType.SEARCH_COMPLETE
        assert event.search_id == "test-123"
        assert event.data["results"] == 10

    def test_to_dict(self):
        """Test HookEvent serialization."""
        event = HookEvent(
            event_type=HookEventType.SEARCH_START,
            search_id="test-123",
            data={"query": "Ubuntu"},
        )

        data = event.to_dict()

        assert data["event_type"] == "search_start"
        assert data["search_id"] == "test-123"
        assert data["data"]["query"] == "Ubuntu"
        assert "timestamp" in data


class TestHookConfig:
    """Tests for HookConfig dataclass."""

    def test_creation(self):
        """Test HookConfig creation."""
        config = HookConfig(
            name="test_hook",
            event=HookEventType.SEARCH_COMPLETE,
            script_path="/tmp/test.sh",
            enabled=True,
            timeout=30,
        )

        assert config.name == "test_hook"
        assert config.event == HookEventType.SEARCH_COMPLETE
        assert config.script_path == "/tmp/test.sh"
        assert config.enabled == True
        assert config.timeout == 30

    def test_validate_missing_path(self):
        """Test validation with non-existent script."""
        config = HookConfig(
            name="test",
            event=HookEventType.SEARCH_COMPLETE,
            script_path="/nonexistent/script.sh",
        )

        # Validation should return False but not crash
        assert config.validate() == False


class TestHookDispatcher:
    """Tests for HookDispatcher class."""

    @pytest.fixture
    def dispatcher(self):
        """Create dispatcher instance."""
        return HookDispatcher(timeout=5)

    def test_init(self, dispatcher):
        """Test dispatcher initialization."""
        assert dispatcher._hooks == {}
        assert dispatcher._timeout == 5
        assert dispatcher._execution_log == []

    def test_register_hook(self, dispatcher):
        """Test hook registration."""
        config = HookConfig(
            name="test_hook",
            event=HookEventType.SEARCH_COMPLETE,
            script_path="/tmp/test.sh",
        )

        dispatcher.register_hook(config)

        assert HookEventType.SEARCH_COMPLETE in dispatcher._hooks
        assert len(dispatcher._hooks[HookEventType.SEARCH_COMPLETE]) == 1

    def test_get_hooks(self, dispatcher):
        """Test getting hooks by event type."""
        config = HookConfig(
            name="test_hook",
            event=HookEventType.SEARCH_COMPLETE,
            script_path="/tmp/test.sh",
        )

        dispatcher.register_hook(config)

        hooks = dispatcher.get_hooks(HookEventType.SEARCH_COMPLETE)

        assert len(hooks) == 1
        assert hooks[0].name == "test_hook"

    def test_get_hooks_empty(self, dispatcher):
        """Test getting hooks when none registered."""
        hooks = dispatcher.get_hooks(HookEventType.SEARCH_COMPLETE)

        assert hooks == []

    def test_unregister_hook(self, dispatcher):
        """Test hook unregistration."""
        config = HookConfig(
            name="test_hook",
            event=HookEventType.SEARCH_COMPLETE,
            script_path="/tmp/test.sh",
        )

        dispatcher.register_hook(config)
        dispatcher.unregister_hook("test_hook", HookEventType.SEARCH_COMPLETE)

        hooks = dispatcher.get_hooks(HookEventType.SEARCH_COMPLETE)
        assert hooks == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
