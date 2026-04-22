import importlib
import importlib.util
from pathlib import Path

UI_INIT = Path(__file__).resolve().parents[2] / "download-proxy" / "src" / "ui" / "__init__.py"


def test_ui_module_importable():
    """ui module is importable as a static assets directory."""
    spec = importlib.util.spec_from_file_location("ui", UI_INIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod is not None


def test_ui_init_is_no_op():
    """ui/__init__.py is a static assets directory with no Python functionality."""
    content = UI_INIT.read_text().strip()
    lines = [l for l in content.splitlines() if l and not l.startswith("#")]
    assert len(lines) == 0, f"ui/__init__.py should be no-op but has: {lines}"
