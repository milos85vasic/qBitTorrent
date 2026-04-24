"""Edge-case challenges for the merge service.

These tests target the gap between "tests pass" and "product works".
Real trackers emit malformed, inconsistent, and unexpected data.  If
our code silently drops results or crashes the fan-out, the user sees
empty trackers with no explanation.

Every test here documents a real-world edge case observed in public
tracker responses or inferred from the code's exception-handling
structure.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

REPO = Path(__file__).resolve().parents[3]
_MS_PATH = REPO / "download-proxy" / "src" / "merge_service"

# The deduplicator does ``from api.routes import _detect_quality`` at
# runtime inside _update_best_quality.  In this isolated test context
# the ``api`` package does not exist, so tests that exercise the merge
# path install a lightweight stub via a helper.


def _install_api_stub():
    _api_stub = types.ModuleType("api")
    _api_routes_stub = types.ModuleType("api.routes")
    _api_routes_stub._detect_quality = lambda name, size: None
    sys.modules.setdefault("api", _api_stub)
    sys.modules.setdefault("api.routes", _api_routes_stub)


sys.modules.setdefault("merge_service", type(sys)("merge_service"))
sys.modules["merge_service"].__path__ = [str(_MS_PATH)]  # type: ignore[attr-defined]

_spec = importlib.util.spec_from_file_location("merge_service.search", str(_MS_PATH / "search.py"))
_search = importlib.util.module_from_spec(_spec)
sys.modules["merge_service.search"] = _search
_spec.loader.exec_module(_search)  # type: ignore[union-attr]

_dedup_spec = importlib.util.spec_from_file_location("merge_service.deduplicator", str(_MS_PATH / "deduplicator.py"))
_dedup_mod = importlib.util.module_from_spec(_dedup_spec)
sys.modules["merge_service.deduplicator"] = _dedup_mod
_dedup_spec.loader.exec_module(_dedup_mod)  # type: ignore[union-attr]

_enricher_spec = importlib.util.spec_from_file_location("merge_service.enricher", str(_MS_PATH / "enricher.py"))
_enricher_mod = importlib.util.module_from_spec(_enricher_spec)
sys.modules["merge_service.enricher"] = _enricher_mod
_enricher_spec.loader.exec_module(_enricher_mod)  # type: ignore[union-attr]

SearchResult = _search.SearchResult
SearchOrchestrator = _search.SearchOrchestrator
Deduplicator = _dedup_mod.Deduplicator


class TestDeduplicatorSizeParsing:
    """The deduplicator must not crash or silently mis-parse sizes."""

    @pytest.fixture
    def dedup(self):
        return Deduplicator()

    @pytest.mark.parametrize(
        "size_str,expected_bytes",
        [
            ("2.5 GB", 2.5 * 1024**3),
            ("500 MB", 500 * 1024**2),
            ("1 TB", 1024**4),
            ("  2.5   GB  ", 2.5 * 1024**3),
            ("0 B", 0),
            ("10 KB", 10 * 1024),
        ],
    )
    def test_valid_sizes_parsed_correctly(self, dedup, size_str, expected_bytes):
        assert dedup._parse_size(size_str) == expected_bytes

    @pytest.mark.parametrize(
        "size_str",
        [
            None,
            "",
            "   ",
            "unknown",
            "N/A",
            "1,5 GB",  # European decimal comma  -  unsupported, must not crash
            "1.5GiB",  # Binary suffix  -  unsupported, must not crash
            # "1.5 gb" is valid because upper() makes it "1.5 GB"
            -1,
            -1.5,
            [],
            {},
        ],
    )
    def test_malformed_sizes_return_none_not_crash(self, dedup, size_str):
        """Malformed sizes must return None, never raise."""
        result = dedup._parse_size(size_str)
        assert result is None

    def test_size_comparison_with_none_does_not_crash(self, dedup):
        """If one result has a parsable size and the other does not,
        the comparison must not raise."""
        r1 = SearchResult(
            name="Test",
            link="m",
            size="2.0 GB",
            seeds=1,
            leechers=0,
            engine_url="e",
        )
        r2 = SearchResult(
            name="Test",
            link="m",
            size="unknown",
            seeds=1,
            leechers=0,
            engine_url="e",
        )
        # Must not raise  -  the method is private but we exercise the path.
        assert dedup._compare_name_and_size(r1, r2) in (True, False)


class TestPublicTrackerResultParsing:
    """Public tracker plugins emit messy NDJSON.  Every row that can be
    salvaged MUST be salvaged; only truly unparseable rows should be
    dropped.
    """

    def _proc_mock(self, lines: list[bytes], returncode: int = 0) -> AsyncMock:
        mock = AsyncMock()
        mock.returncode = returncode
        mock.stdout = MagicMock()
        mock.stdout.readline = AsyncMock(side_effect=lines + [b""])
        mock.stderr = MagicMock()
        mock.stderr.read = AsyncMock(return_value=b"")
        mock.wait = AsyncMock(return_value=returncode)
        mock.kill = MagicMock()
        return mock

    def test_seeds_with_plus_sign_is_silently_dropped(self):
        """CRITICAL: plugins sometimes emit ``seeds: "100+"``.

        ``int("100+")`` raises ValueError inside _append, which catches
        the exception and drops the WHOLE result.  This is silent data
        loss  -  the user sees fewer results than the tracker actually
        returned.

        This test documents the current (broken) behaviour so a future
        fix can turn it GREEN.
        """
        orch = SearchOrchestrator()

        row = json.dumps({"name": "Ubuntu", "size": "2 GB", "seeds": "100+", "leech": 0, "link": "m", "desc_link": "d"})

        async def fake_subprocess(*args, **kwargs):
            return self._proc_mock([row.encode()])

        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
            results = asyncio.run(orch._search_public_tracker("piratebay", "q", "all"))

        # Current behaviour: the row is dropped because int("100+") fails.
        # A proper fix would sanitize seeds before casting.
        assert len(results) == 0, "documenting current silent-drop behaviour"

    def test_seeds_as_string_integer_succeeds(self):
        """Some plugins emit ``seeds: "42"`` (string integer)."""
        orch = SearchOrchestrator()

        row = json.dumps({"name": "Ubuntu", "size": "2 GB", "seeds": "42", "leech": "5", "link": "m", "desc_link": "d"})

        async def fake_subprocess(*args, **kwargs):
            return self._proc_mock([row.encode()])

        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
            results = asyncio.run(orch._search_public_tracker("piratebay", "q", "all"))

        assert len(results) == 1
        assert results[0].seeds == 42
        assert results[0].leechers == 5

    def test_partial_json_line_is_skipped_not_crash(self):
        """A truncated NDJSON line must not crash the fan-out."""
        orch = SearchOrchestrator()

        lines = [
            b'{"name":"good","size":"1 B","seeds":1,"leech":0,"link":"m","desc_link":"d"}\n',
            b'{"name":"truncated","size":',
            b'{"name":"also_good","size":"2 B","seeds":2,"leech":0,"link":"m","desc_link":"d"}\n',
        ]

        async def fake_subprocess(*args, **kwargs):
            return self._proc_mock(lines)

        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
            results = asyncio.run(orch._search_public_tracker("piratebay", "q", "all"))

        assert len(results) == 2
        assert results[0].name == "good"
        assert results[1].name == "also_good"

    def test_mixed_stdout_stderr_does_not_confuse_parser(self):
        """Plugins that log warnings to stdout must not break NDJSON parsing."""
        orch = SearchOrchestrator()

        lines = [
            b"WARNING: deprecated call\n",
            b'{"name":"good","size":"1 B","seeds":1,"leech":0,"link":"m","desc_link":"d"}\n',
        ]

        async def fake_subprocess(*args, **kwargs):
            return self._proc_mock(lines)

        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
            results = asyncio.run(orch._search_public_tracker("piratebay", "q", "all"))

        assert len(results) == 1
        assert results[0].name == "good"

    def test_empty_name_becomes_empty_string_not_crash(self):
        """A plugin emitting ``name: ""`` must not crash _append."""
        orch = SearchOrchestrator()

        row = json.dumps({"name": "", "size": "1 B", "seeds": 1, "leech": 0, "link": "m", "desc_link": "d"})

        async def fake_subprocess(*args, **kwargs):
            return self._proc_mock([row.encode()])

        with patch("asyncio.create_subprocess_exec", side_effect=fake_subprocess):
            results = asyncio.run(orch._search_public_tracker("piratebay", "q", "all"))

        assert len(results) == 1
        assert results[0].name == ""


class TestEnricherResilience:
    """The enricher calls external APIs.  Every call path must be resilient
    to network flakes, malformed JSON, and unexpected status codes.
    """

    @pytest.fixture
    def enricher(self):
        return _enricher_mod.MetadataEnricher()

    def test_resolve_with_no_api_keys_skips_keyed_apis(self, enricher):
        """When no API keys are configured, resolve() must skip TMDB and
        OMDb gracefully and fall through to key-less APIs (OpenLibrary,
        TVMaze, MusicBrainz) or return None.  No exception must escape.
        """
        import asyncio

        # aiohttp is imported locally inside each _lookup_* method, so we
        # stub it in sys.modules to prevent real network calls.
        fake_aiohttp = types.ModuleType("aiohttp")

        async def _fake_session(*args, **kwargs):
            pass

        class _FakeResponseCM:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *args):
                return False

        class _FakeClientSession:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            def get(self, *args, **kwargs):
                resp = AsyncMock()
                resp.status = 200
                resp.json = AsyncMock(return_value={"docs": []})
                return _FakeResponseCM(resp)

            def post(self, *args, **kwargs):
                resp = AsyncMock()
                resp.status = 200
                resp.json = AsyncMock(return_value={"data": {"Media": None}})
                return _FakeResponseCM(resp)

        fake_aiohttp.ClientSession = _FakeClientSession
        fake_aiohttp.ClientTimeout = lambda *a, **k: None

        with patch.dict(sys.modules, {"aiohttp": fake_aiohttp}):
            result = asyncio.run(enricher.resolve("Test Movie"))
            # With empty mocked responses, all APIs return None.
            assert result is None

    def test_detect_quality_with_none_name(self, enricher):
        """``detect_quality`` must not crash when given ``None``."""
        assert enricher.detect_quality(None) is None

    def test_detect_quality_with_empty_name(self, enricher):
        """Empty string must return None, not crash."""
        assert enricher.detect_quality("") is None


class TestOrchestratorCacheEviction:
    """The orchestrator uses TTLCache for active searches.  When the cache
    is full, old entries are evicted.  The code must handle missing
    entries gracefully.
    """

    def test_get_search_status_returns_none_after_eviction(self):
        """If a search ID is evicted from the TTLCache, get_search_status
        must return None  -  not raise KeyError.
        """
        orch = SearchOrchestrator()
        # Replace the cache with a tiny one so eviction is deterministic.
        from cachetools import TTLCache

        orch._active_searches = TTLCache(maxsize=1, ttl=3600)
        orch._tracker_results = TTLCache(maxsize=1, ttl=3600)

        meta1 = orch.start_search("query1", "all")
        meta2 = orch.start_search("query2", "all")

        # meta1 should have been evicted.
        assert orch.get_search_status(meta1.search_id) is None
        # meta2 should still be present.
        assert orch.get_search_status(meta2.search_id) is meta2

    def test_search_orchestrator_handles_negative_max_active_env(self):
        """A malicious or typo'd ``MAX_ACTIVE_SEARCHES`` must not crash
        initialization.
        """
        with patch.dict(os.environ, {"MAX_ACTIVE_SEARCHES": "-5"}):
            orch = SearchOrchestrator()
            # The code does max(1, int(...)) so it should be at least 1.
            assert orch._active_searches.maxsize >= 1


class TestDeduplicatorFuzzyMatching:
    """Fuzzy matching must be robust to real-world naming inconsistencies."""

    @pytest.fixture
    def dedup(self):
        return Deduplicator()

    def test_very_similar_names_match(self, dedup):
        sim = dedup._calculate_similarity(
            "Ubuntu 22.04 LTS Desktop amd64",
            "Ubuntu 22.04 LTS Desktop AMD64",
        )
        assert sim >= 0.85

    def test_unicode_names_do_not_crash(self, dedup):
        """Trackers in non-Latin locales emit Cyrillic, CJK, etc."""
        sim = dedup._calculate_similarity(
            "Фильм 2023 HDRip",
            "Фильм 2023 WEB-DL",
        )
        # Must not crash; similarity may be low but must be a number.
        assert isinstance(sim, float)
        assert 0.0 <= sim <= 1.0

    def test_empty_name_similarity_is_zero(self, dedup):
        assert dedup._calculate_similarity("", "Something") == 0.0
        assert dedup._calculate_similarity("Something", "") == 0.0
        # Levenshtein.ratio("", "") returns 1.0 (identical empty strings).
        assert dedup._calculate_similarity("", "") == 1.0

    def test_merge_with_unicode_names(self, dedup):
        """A full merge cycle must not crash on unicode names.

        The deduplicator imports ``_detect_quality`` from ``api.routes``.
        In this isolated test context we install a stub so the merge can
        complete without the real api package.
        """
        _install_api_stub()
        results = [
            SearchResult(
                name="Фильм Название 2023",
                link="magnet:?xt=urn:btih:abc",
                size="2 GB",
                seeds=10,
                leechers=1,
                engine_url="e",
                tracker="t1",
            ),
            SearchResult(
                name="Фильм Название 2023 HDRip",
                link="magnet:?xt=urn:btih:abc",
                size="2 GB",
                seeds=5,
                leechers=0,
                engine_url="e",
                tracker="t2",
            ),
        ]
        merged = dedup.merge_results(results)
        assert len(merged) == 1
        assert merged[0].total_seeds == 15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
