"""
Tests for freeleech handling and deduplication rules.

Verifies:
1. IPTorrents freeleech results get [free] suffix
2. Non-freeleech IPTorrents results never merge with other trackers
3. Freeleech IPTorrents results CAN merge with other trackers
4. API response includes freeleech field
5. Kinozal credentials fall back to IPTorrents credentials
"""

import os
import sys

_src = os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src")
_src = os.path.abspath(_src)
if _src not in sys.path:
    sys.path.insert(0, _src)

from merge_service.deduplicator import Deduplicator
from merge_service.search import SearchResult


class TestFreeleechSuffix:
    def test_freeleech_gets_free_suffix(self):
        orch = __import__("merge_service.search", fromlist=["SearchOrchestrator"]).SearchOrchestrator()
        html = """<table id="torrents"><tr>
<td><a class=" hv" href="/t/100">Ubuntu 22.04</a><span class="free">Free!</span></td>
<td><a href="/download.php/100/ubuntu.torrent">DL</a></td>
<td>4.5 GB</td><td>50</td><td>10</td></tr>
</table>"""
        results = orch._parse_iptorrents_html(html, "https://iptorrents.com")
        assert len(results) == 1
        assert "[free]" in results[0].name
        assert results[0].freeleech is True

    def test_non_freeleech_no_suffix(self):
        orch = __import__("merge_service.search", fromlist=["SearchOrchestrator"]).SearchOrchestrator()
        html = """<table id="torrents"><tr>
<td><a class=" hv" href="/t/200">Ubuntu 20.04</a></td>
<td><a href="/download.php/200/ubuntu.torrent">DL</a></td>
<td>3.2 GB</td><td>30</td><td>5</td></tr>
</table>"""
        results = orch._parse_iptorrents_html(html, "https://iptorrents.com")
        assert len(results) == 1
        assert "[free]" not in results[0].name
        assert results[0].freeleech is False

    def test_already_has_free_suffix_not_doubled(self):
        orch = __import__("merge_service.search", fromlist=["SearchOrchestrator"]).SearchOrchestrator()
        html = """<table id="torrents"><tr>
<td><a class=" hv" href="/t/300">Ubuntu [free]</a><span class="free">Free!</span></td>
<td><a href="/download.php/300/ubuntu.torrent">DL</a></td>
<td>2 GB</td><td>10</td><td>2</td></tr>
</table>"""
        results = orch._parse_iptorrents_html(html, "https://iptorrents.com")
        assert len(results) == 1
        assert results[0].name.count("[free]") == 1


class TestFreeleechDeduplication:
    def _make_result(self, name, tracker, freeleech=False, link="magnet:?xt=urn:btih:ABC123"):
        return SearchResult(
            name=name,
            link=link,
            size="4.5 GB",
            seeds=100,
            leechers=20,
            engine_url=f"https://{tracker}.com",
            tracker=tracker,
            freeleech=freeleech,
        )

    def test_non_free_iptorrents_does_not_merge_with_rutracker(self):
        dedup = Deduplicator()
        results = [
            self._make_result("Ubuntu 22.04 LTS", "rutracker", link="magnet:?xt=urn:btih:AAA111"),
            self._make_result("Ubuntu 22.04 LTS", "iptorrents", freeleech=False, link="magnet:?xt=urn:btih:BBB222"),
        ]
        merged = dedup.merge_results(results)
        assert len(merged) == 2, "Non-free IPTorrents should NOT merge with other tracker"

    def test_free_iptorrents_does_merge_with_rutracker(self):
        dedup = Deduplicator()
        results = [
            self._make_result("Ubuntu 22.04 LTS", "rutracker", link="magnet:?xt=urn:btih:AAA111"),
            self._make_result("Ubuntu 22.04 LTS", "iptorrents", freeleech=True, link="magnet:?xt=urn:btih:BBB222"),
        ]
        merged = dedup.merge_results(results)
        assert len(merged) == 1, "Free IPTorrents SHOULD merge with other tracker"

    def test_two_non_free_iptorrents_do_merge(self):
        dedup = Deduplicator()
        results = [
            self._make_result("Ubuntu 22.04 LTS", "iptorrents", freeleech=False, link="magnet:?xt=urn:btih:AAA111"),
            self._make_result("Ubuntu 22.04 LTS", "iptorrents", freeleech=False, link="magnet:?xt=urn:btih:AAA111"),
        ]
        merged = dedup.merge_results(results)
        assert len(merged) == 1, "Same-tracker IPTorrents should merge"

    def test_two_rutracker_results_merge(self):
        dedup = Deduplicator()
        results = [
            self._make_result("Ubuntu 22.04 LTS", "rutracker", link="magnet:?xt=urn:btih:AAA111"),
            self._make_result("Ubuntu 22.04 LTS", "rutracker", link="magnet:?xt=urn:btih:AAA111"),
        ]
        merged = dedup.merge_results(results)
        assert len(merged) == 1

    def test_mixed_free_and_non_free_across_trackers(self):
        dedup = Deduplicator()
        results = [
            self._make_result("Movie 2024", "rutracker", link="magnet:?xt=urn:btih:CCC333"),
            self._make_result("Movie 2024", "iptorrents", freeleech=False, link="magnet:?xt=urn:btih:DDD444"),
            self._make_result("Movie 2024 1080p", "rutor", link="magnet:?xt=urn:btih:EEE555"),
        ]
        merged = dedup.merge_results(results)
        ipt_groups = [m for m in merged if any(r.tracker == "iptorrents" for r in m.original_results)]
        other_groups = [m for m in merged if not any(r.tracker == "iptorrents" for r in m.original_results)]
        for g in ipt_groups:
            for r in g.original_results:
                if r.tracker == "iptorrents":
                    continue
                assert False, f"Non-free IPTorrents merged with {r.tracker}!"


class TestKinozalCredentialFallback:
    def test_kinozal_falls_back_to_iptorrents(self):
        os.environ.pop("KINOZAL_USERNAME", None)
        os.environ.pop("KINOZAL_PASSWORD", None)
        os.environ["IPTORRENTS_USERNAME"] = "testuser"
        os.environ["IPTORRENTS_PASSWORD"] = "testpass"

        try:
            from config import load_env

            cfg = load_env()
            assert cfg.kinozal_username == "testuser"
            assert cfg.kinozal_password == "testpass"
        finally:
            os.environ.pop("IPTORRENTS_USERNAME", None)
            os.environ.pop("IPTORRENTS_PASSWORD", None)

    def test_kinozal_owns_credentials_take_priority(self):
        os.environ["KINOZAL_USERNAME"] = "kinozal_user"
        os.environ["KINOZAL_PASSWORD"] = "kinozal_pass"
        os.environ["IPTORRENTS_USERNAME"] = "ipt_user"
        os.environ["IPTORRENTS_PASSWORD"] = "ipt_pass"

        try:
            from config import load_env

            cfg = load_env()
            assert cfg.kinozal_username == "kinozal_user"
            assert cfg.kinozal_password == "kinozal_pass"
        finally:
            os.environ.pop("KINOZAL_USERNAME", None)
            os.environ.pop("KINOZAL_PASSWORD", None)
            os.environ.pop("IPTORRENTS_USERNAME", None)
            os.environ.pop("IPTORRENTS_PASSWORD", None)


class TestSearchResultFreeleechField:
    def test_search_result_default_not_freeleech(self):
        r = SearchResult(name="test", link="magnet:x", size="1 GB", seeds=1, leechers=0, engine_url="http://test")
        assert r.freeleech is False

    def test_search_result_can_be_freeleech(self):
        r = SearchResult(
            name="test [free]",
            link="magnet:x",
            size="1 GB",
            seeds=1,
            leechers=0,
            engine_url="http://test",
            tracker="iptorrents",
            freeleech=True,
        )
        assert r.freeleech is True

    def test_to_dict_includes_freeleech(self):
        r = SearchResult(
            name="test", link="magnet:x", size="1 GB", seeds=1, leechers=0, engine_url="http://test", freeleech=True
        )
        d = r.to_dict()
        assert d["freeleech"] is True
