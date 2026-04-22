import py_compile
from pathlib import Path

COMMUNITY_DIR = Path(__file__).resolve().parent.parent.parent / "plugins" / "community"


def _community_plugins():
    if not COMMUNITY_DIR.exists():
        return []
    return sorted(COMMUNITY_DIR.glob("*.py"))


def test_community_plugins_compile():
    plugins = _community_plugins()
    assert len(plugins) > 0, "No community plugins found"
    for plugin_path in plugins:
        py_compile.compile(str(plugin_path), doraise=True)


def test_community_plugin_names_match_files():
    for plugin_path in _community_plugins():
        assert plugin_path.stem.isidentifier(), (
            f"Plugin filename {plugin_path.name} is not a valid Python identifier"
        )
