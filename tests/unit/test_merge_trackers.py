import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src"))

from merge_service.search import (
    PRIVATE_TRACKERS,
    PUBLIC_TRACKERS,
    SearchOrchestrator,
    SearchResult,
    TrackerSource,
)


class TestPublicTrackersRegistry:
    def test_public_trackers_not_empty(self):
        assert len(PUBLIC_TRACKERS) > 0

    def test_all_public_trackers_have_urls(self):
        for name, url in PUBLIC_TRACKERS.items():
            assert url.startswith("http"), f"{name} has invalid URL: {url}"

    def test_expected_public_tracker_count(self):
        assert len(PUBLIC_TRACKERS) == 37

    def test_specific_trackers_present(self):
        expected = [
            "piratebay",
            "nyaa",
            "yts",
            "torrentgalaxy",
            "one337x",
            "kickass",
            "eztv",
            "torlock",
            "solidtorrents",
            "rutor",
            "limetorrents",
            "extratorrent",
            "therarbg",
            "bt4g",
            "torrentdownload",
            "torrentfunk",
            "torrentscsv",
            "btsow",
            "snowfl",
            "rockbox",
            "megapeer",
        ]
        for t in expected:
            assert t in PUBLIC_TRACKERS, f"Missing public tracker: {t}"

    def test_no_private_trackers_in_public_registry(self):
        for name in PRIVATE_TRACKERS:
            assert name not in PUBLIC_TRACKERS

    def test_private_trackers_defined(self):
        assert "rutracker" in PRIVATE_TRACKERS
        assert "kinozal" in PRIVATE_TRACKERS
        assert "nnmclub" in PRIVATE_TRACKERS
        assert "iptorrents" in PRIVATE_TRACKERS


class TestGetEnabledTrackers:
    def setup_method(self):
        self.orch = SearchOrchestrator()

    def test_public_trackers_always_enabled(self):
        with patch.dict(os.environ, {}, clear=True):
            trackers = self.orch._get_enabled_trackers()
            names = [t.name for t in trackers]
            for name in PUBLIC_TRACKERS:
                assert name in names, f"Public tracker {name} missing from enabled list"

    def test_private_trackers_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            trackers = self.orch._get_enabled_trackers()
            names = [t.name for t in trackers]
            assert "rutracker" not in names
            assert "kinozal" not in names
            assert "nnmclub" not in names
            assert "iptorrents" not in names

    def test_rutracker_with_credentials(self):
        with patch.dict(os.environ, {"RUTRACKER_USERNAME": "u", "RUTRACKER_PASSWORD": "p"}, clear=True):
            trackers = self.orch._get_enabled_trackers()
            names = [t.name for t in trackers]
            assert "rutracker" in names

    def test_kinozal_with_credentials(self):
        with patch.dict(os.environ, {"KINOZAL_USERNAME": "u", "KINOZAL_PASSWORD": "p"}, clear=True):
            trackers = self.orch._get_enabled_trackers()
            names = [t.name for t in trackers]
            assert "kinozal" in names

    def test_nnmclub_with_cookies(self):
        with patch.dict(os.environ, {"NNMCLUB_COOKIES": "phpbb2mysql_4_sid=abc123"}, clear=True):
            trackers = self.orch._get_enabled_trackers()
            names = [t.name for t in trackers]
            assert "nnmclub" in names

    def test_iptorrents_with_credentials(self):
        with patch.dict(os.environ, {"IPTORRENTS_USERNAME": "u", "IPTORRENTS_PASSWORD": "p"}, clear=True):
            trackers = self.orch._get_enabled_trackers()
            names = [t.name for t in trackers]
            assert "iptorrents" in names

    def test_all_trackers_with_all_credentials(self):
        env = {
            "RUTRACKER_USERNAME": "u",
            "RUTRACKER_PASSWORD": "p",
            "KINOZAL_USERNAME": "u",
            "KINOZAL_PASSWORD": "p",
            "NNMCLUB_COOKIES": "phpbb2mysql_4_sid=abc",
            "IPTORRENTS_USERNAME": "u",
            "IPTORRENTS_PASSWORD": "p",
        }
        with patch.dict(os.environ, env, clear=True):
            trackers = self.orch._get_enabled_trackers()
            assert len(trackers) == 4 + len(PUBLIC_TRACKERS)

    def test_tracker_sources_have_urls(self):
        with patch.dict(os.environ, {}, clear=True):
            trackers = self.orch._get_enabled_trackers()
            for t in trackers:
                assert t.url, f"Tracker {t.name} has no URL"
                assert t.enabled is True

    def test_trackers_are_sorted_alphabetically_among_public(self):
        with patch.dict(os.environ, {}, clear=True):
            trackers = self.orch._get_enabled_trackers()
            public_names = [t.name for t in trackers if t.name in PUBLIC_TRACKERS]
            assert public_names == sorted(public_names)


class TestSearchTrackerRouting:
    def setup_method(self):
        self.orch = SearchOrchestrator()

    @pytest.mark.asyncio
    async def test_public_tracker_routes_correctly(self):
        with patch.object(self.orch, "_search_public_tracker", new_callable=AsyncMock) as mock:
            mock.return_value = [
                SearchResult(
                    name="Test",
                    size="1 GB",
                    seeds=10,
                    leechers=5,
                    link="magnet:?",
                    desc_link="http://x",
                    tracker="piratebay",
                    engine_url="https://thepiratebay.org",
                )
            ]
            tracker = TrackerSource(name="piratebay", url="https://thepiratebay.org")
            results = await self.orch._search_tracker(tracker, "ubuntu", "all")
            mock.assert_called_once_with("piratebay", "ubuntu", "all")
            assert len(results) == 1
            assert results[0].tracker == "piratebay"

    @pytest.mark.asyncio
    async def test_private_tracker_rutracker_routes(self):
        with patch.object(self.orch, "_search_rutracker", new_callable=AsyncMock) as mock:
            mock.return_value = []
            tracker = TrackerSource(name="rutracker", url="https://rutracker.org")
            await self.orch._search_tracker(tracker, "test", "all")
            mock.assert_called_once_with("test", "all")

    @pytest.mark.asyncio
    async def test_private_tracker_kinozal_routes(self):
        with patch.object(self.orch, "_search_kinozal", new_callable=AsyncMock) as mock:
            mock.return_value = []
            tracker = TrackerSource(name="kinozal", url="https://kinozal.tv")
            await self.orch._search_tracker(tracker, "test", "all")
            mock.assert_called_once_with("test", "all")

    @pytest.mark.asyncio
    async def test_private_tracker_nnmclub_routes(self):
        with patch.object(self.orch, "_search_nnmclub", new_callable=AsyncMock) as mock:
            mock.return_value = []
            tracker = TrackerSource(name="nnmclub", url="https://nnm-club.me")
            await self.orch._search_tracker(tracker, "test", "all")
            mock.assert_called_once_with("test", "all")

    @pytest.mark.asyncio
    async def test_private_tracker_iptorrents_routes(self):
        with patch.object(self.orch, "_search_iptorrents", new_callable=AsyncMock) as mock:
            mock.return_value = []
            tracker = TrackerSource(name="iptorrents", url="https://iptorrents.com")
            await self.orch._search_tracker(tracker, "test", "all")
            mock.assert_called_once_with("test", "all")

    @pytest.mark.asyncio
    async def test_unknown_tracker_returns_empty(self):
        tracker = TrackerSource(name="nonexistent_tracker", url="http://x")
        results = await self.orch._search_tracker(tracker, "test", "all")
        assert results == []

    @pytest.mark.asyncio
    async def test_tracker_error_returns_empty(self):
        with patch.object(self.orch, "_search_public_tracker", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("Connection error")
            tracker = TrackerSource(name="piratebay", url="https://thepiratebay.org")
            results = await self.orch._search_tracker(tracker, "test", "all")
            assert results == []


class TestSearchPublicTracker:
    def setup_method(self):
        self.orch = SearchOrchestrator()

    @pytest.mark.asyncio
    async def test_successful_plugin_execution(self):
        mock_results = [
            {
                "name": "Ubuntu 22.04",
                "size": "4.0 GB",
                "seeds": 100,
                "leech": 20,
                "link": "magnet:?xt=urn:btih:abc",
                "desc_link": "http://x/details",
            },
        ]
        mock_stdout = __import__("json").dumps(mock_results)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(mock_stdout.encode(), b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            results = await self.orch._search_public_tracker("piratebay", "ubuntu", "all")
            assert len(results) == 1
            assert results[0].name == "Ubuntu 22.04"
            assert results[0].seeds == 100
            assert results[0].tracker == "piratebay"

    @pytest.mark.asyncio
    async def test_empty_results(self):
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"[]", b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            results = await self.orch._search_public_tracker("eztv", "test", "all")
            assert results == []

    @pytest.mark.asyncio
    async def test_plugin_timeout(self):

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(side_effect=TimeoutError())
            mock_exec.return_value = mock_proc

            results = await self.orch._search_public_tracker("slowtracker", "test", "all")
            assert results == []

    @pytest.mark.asyncio
    async def test_plugin_nonzero_exit(self):
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b"ImportError: No module"))
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc

            results = await self.orch._search_public_tracker("broken", "test", "all")
            assert results == []

    @pytest.mark.asyncio
    async def test_plugin_stderr_error(self):
        error_json = '{"error": "module not found"}'
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(error_json.encode(), b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            results = await self.orch._search_public_tracker("broken", "test", "all")
            assert results == []

    @pytest.mark.asyncio
    async def test_malformed_result_skipped(self):
        mock_results = [
            {
                "name": "Bad",
                "size": "1 GB",
                "seeds": "not_a_number",
                "leech": 0,
                "link": "magnet:?",
                "desc_link": "http://x",
            },
            {
                "name": "Good",
                "size": "1 GB",
                "seeds": 5,
                "leech": 0,
                "link": "magnet:?",
                "desc_link": "http://x",
            },
        ]
        mock_stdout = __import__("json").dumps(mock_results)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(mock_stdout.encode(), b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            results = await self.orch._search_public_tracker("test", "test", "all")
            assert len(results) == 1
            assert results[0].name == "Good"

    @pytest.mark.asyncio
    async def test_multiple_results(self):
        mock_results = [
            {
                "name": f"Result {i}",
                "size": f"{i} GB",
                "seeds": i * 10,
                "leech": i,
                "link": f"magnet:?xt=urn:btih:{i}",
                "desc_link": f"http://x/{i}",
            }
            for i in range(5)
        ]
        mock_stdout = __import__("json").dumps(mock_results)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(mock_stdout.encode(), b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            results = await self.orch._search_public_tracker("test", "ubuntu", "all")
            assert len(results) == 5
            for i, r in enumerate(results):
                assert r.name == f"Result {i}"
                assert r.tracker == "test"


class TestConcurrentSearch:
    def setup_method(self):
        self.orch = SearchOrchestrator()

    @pytest.mark.asyncio
    async def test_search_uses_concurrent_execution(self):
        call_order = []

        async def mock_search(tracker, query, category):
            call_order.append(tracker.name)
            if tracker.name == "rutracker":
                return [
                    SearchResult(
                        name="Rutracker Result",
                        size="1 GB",
                        seeds=10,
                        leechers=5,
                        link="magnet:?1",
                        desc_link="http://r",
                        tracker="rutracker",
                        engine_url="https://rutracker.org",
                    )
                ]
            return []

        with patch.dict(os.environ, {"RUTRACKER_USERNAME": "u", "RUTRACKER_PASSWORD": "p"}, clear=True):
            with patch.object(self.orch, "_search_tracker", side_effect=mock_search):
                metadata = await self.orch.search("ubuntu", "all", enable_metadata=False, validate_trackers=False)
                assert metadata.total_results == 1
                assert "rutracker" in metadata.trackers_searched
                total_trackers = 1 + len(PUBLIC_TRACKERS)
                assert len(metadata.trackers_searched) == total_trackers

    @pytest.mark.asyncio
    async def test_search_merges_cross_tracker_results(self):
        async def mock_search(tracker, query, category):
            if tracker.name == "rutracker":
                return [
                    SearchResult(
                        name="Ubuntu 22.04",
                        size="4.0 GB",
                        seeds=50,
                        leechers=10,
                        link="magnet:?rut",
                        desc_link="http://rut",
                        tracker="rutracker",
                        engine_url="https://rutracker.org",
                    )
                ]
            elif tracker.name == "kinozal":
                return [
                    SearchResult(
                        name="Ubuntu 22.04",
                        size="4.0 GB",
                        seeds=30,
                        leechers=5,
                        link="magnet:?kin",
                        desc_link="http://kin",
                        tracker="kinozal",
                        engine_url="https://kinozal.tv",
                    )
                ]
            elif tracker.name == "piratebay":
                return [
                    SearchResult(
                        name="Ubuntu 22.04",
                        size="4.0 GB",
                        seeds=100,
                        leechers=20,
                        link="magnet:?pb",
                        desc_link="http://pb",
                        tracker="piratebay",
                        engine_url="https://thepiratebay.org",
                    )
                ]
            return []

        env = {
            "RUTRACKER_USERNAME": "u",
            "RUTRACKER_PASSWORD": "p",
            "KINOZAL_USERNAME": "u",
            "KINOZAL_PASSWORD": "p",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(self.orch, "_search_tracker", side_effect=mock_search):
                metadata = await self.orch.search("ubuntu", "all", enable_metadata=False, validate_trackers=False)
                stored = self.orch._last_merged_results.get(metadata.search_id)
                merged = stored[0] if stored else []
                ubuntu_merged = [m for m in merged if "Ubuntu 22.04" in m.original_results[0].name]
                assert len(ubuntu_merged) == 1, "Same torrent from multiple trackers should be merged into 1"
                assert len(ubuntu_merged[0].original_results) == 3, "Should have 3 sources"
                assert ubuntu_merged[0].total_seeds == 180, "Seeds should be summed across sources"

    @pytest.mark.asyncio
    async def test_search_handles_partial_failures(self):
        async def mock_search(tracker, query, category):
            if tracker.name == "piratebay":
                return [
                    SearchResult(
                        name="Test",
                        size="1 GB",
                        seeds=10,
                        leechers=5,
                        link="magnet:?",
                        desc_link="http://x",
                        tracker="piratebay",
                        engine_url="https://thepiratebay.org",
                    )
                ]
            if tracker.name == "eztv":
                raise Exception("Connection refused")
            return []

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(self.orch, "_search_tracker", side_effect=mock_search):
                metadata = await self.orch.search("test", "all", enable_metadata=False, validate_trackers=False)
                assert metadata.total_results == 1
                assert metadata.status == "completed"
                assert len(metadata.errors) > 0
