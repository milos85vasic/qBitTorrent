"""
Unit tests for public tracker subprocess script generation.

Issue 4: Search hangs / returns 0 results from public trackers because
the subprocess script contains an undefined variable reference.
"""

import asyncio
import os
import sys

import pytest

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from merge_service.search import SearchOrchestrator


class TestPublicTrackerSubprocessScript:
    """The subprocess script must contain the actual tracker name, not a variable reference."""

    def test_script_contains_actual_tracker_name_not_variable(self):
        """Script must hardcode the tracker name, not use {tracker_name} placeholder."""
        orch = SearchOrchestrator()
        # We can't easily call _search_public_tracker without mocking,
        # but we can inspect the method source to verify the script template.
        import inspect
        source = inspect.getsource(orch._search_public_tracker)
        # The buggy code had: importlib.import_module(f'engines.{{tracker_name}}')
        # which produced a literal {tracker_name} in the subprocess.
        # After fix, it should use the actual tracker name.
        assert "f'engines.{{tracker_name}}'" not in source, \
            "Bug: subprocess script uses undefined {tracker_name} variable"
        assert "getattr(_mod, '{{tracker_name}}')" not in source, \
            "Bug: subprocess script uses undefined {tracker_name} variable"

    def test_script_uses_hardcoded_tracker_name(self):
        """Script template must interpolate tracker_name into the string."""
        import inspect
        source = inspect.getsource(SearchOrchestrator._search_public_tracker)
        # Should have direct interpolation like 'engines.{tracker_name}'
        assert "'engines.{tracker_name}'" in source or '"engines.{tracker_name}"' in source, \
            "Fix: tracker name must be hardcoded in subprocess script"

    @pytest.mark.asyncio
    async def test_subprocess_script_compiles(self, tmp_path):
        """The generated script must be valid Python that compiles."""
        orch = SearchOrchestrator()
        # Simulate script generation by calling the method with a mock
        # We extract the script by patching create_subprocess_exec
        captured_script = None

        async def mock_create_subprocess_exec(*args, **kwargs):
            nonlocal captured_script
            if len(args) >= 3 and args[0] == "python3" and args[1] == "-c":
                captured_script = args[2]
            # Return a mock process
            class MockProc:
                returncode = 0
                async def communicate(self):
                    return (b"[]", b"")
            return MockProc()

        original_create = asyncio.create_subprocess_exec
        try:
            asyncio.create_subprocess_exec = mock_create_subprocess_exec
            await orch._search_public_tracker("yts", "test query", "all")
        finally:
            asyncio.create_subprocess_exec = original_create

        assert captured_script is not None, "Script was not captured"
        # The script must compile
        compile(captured_script, "<string>", "exec")
        # It must NOT contain unresolved {tracker_name}
        assert "{tracker_name}" not in captured_script, \
            f"Script contains unresolved {{tracker_name}}: {captured_script}"
        # It MUST contain the actual tracker name
        assert "'engines.yts'" in captured_script or '"engines.yts"' in captured_script, \
            f"Script does not contain hardcoded tracker name: {captured_script}"
        assert "'yts'" in captured_script or '"yts"' in captured_script, \
            f"Script does not reference tracker class: {captured_script}"


class TestPublicTrackerResultParsing:
    """Results from public tracker subprocess must be parsed correctly."""

    def test_search_result_from_plugin_dict(self):
        """Plugin result dict must be converted to SearchResult with correct fields."""
        from merge_service.search import SearchResult
        r = SearchResult(
            name="Test Movie 2024 1080p",
            link="magnet:?xt=urn:btih:abc123",
            size="1.5 GB",
            seeds=100,
            leechers=20,
            engine_url="https://yts.mx",
            tracker="yts",
        )
        assert r.seeds == 100
        assert r.leechers == 20
        assert r.tracker == "yts"

    def test_plugin_dict_with_leech_key(self):
        """Plugins use 'leech' key but SearchResult uses 'leechers'."""
        plugin_dict = {
            "name": "Test",
            "link": "magnet:x",
            "size": "1 GB",
            "seeds": 50,
            "leech": 10,
            "engine_url": "https://test.com",
        }
        # This is how _search_public_tracker parses it
        from merge_service.search import SearchResult
        r = SearchResult(
            name=plugin_dict.get("name", ""),
            size=plugin_dict.get("size", "0 B"),
            seeds=int(plugin_dict.get("seeds", 0)),
            leechers=int(plugin_dict.get("leech", 0)),
            link=plugin_dict.get("link", ""),
            engine_url=plugin_dict.get("engine_url", ""),
            tracker="test",
        )
        assert r.leechers == 10


class TestSearchOrchestratorTrackerCount:
    """Search must use all enabled trackers, not just private ones."""

    def test_get_enabled_trackers_includes_public_trackers(self):
        """Enabled trackers must include public trackers."""
        orch = SearchOrchestrator()
        trackers = orch._get_enabled_trackers()
        names = [t.name for t in trackers]
        # Should have many public trackers
        public_names = ["yts", "piratebay", "nyaa", "rutor", "1337x", "eztv"]
        found = [n for n in public_names if n in names]
        assert len(found) >= 5, f"Too few public trackers enabled: {found}"

    def test_get_enabled_trackers_count(self):
        """Should have 30+ trackers total."""
        orch = SearchOrchestrator()
        trackers = orch._get_enabled_trackers()
        assert len(trackers) >= 30, f"Only {len(trackers)} trackers enabled"
