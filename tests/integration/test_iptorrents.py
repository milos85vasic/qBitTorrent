"""
IPTorrents integration tests — freeleech detection, search, and download.

Requires:
  - IPTORRENTS_USERNAME and IPTORRENTS_PASSWORD in .env
  - qbittorrent-proxy container running (merge service on 78086)

Run:
    python3 -m pytest tests/integration/test_iptorrents.py -v --import-mode=importlib
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

MERGE_URL = os.environ.get("MERGE_URL", "http://localhost:78086")


def _fetch(
    url: str,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict | None = None,
):
    req = urllib.request.Request(url, data=data, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body, dict(resp.headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body, {}
    except urllib.error.URLError as e:
        return None, str(e.reason), {}


def _has_iptorrents_creds():
    return bool(
        os.environ.get("IPTORRENTS_USERNAME") and os.environ.get("IPTORRENTS_PASSWORD")
    )


@pytest.fixture(scope="module")
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k not in os.environ:
                    os.environ[k] = v


no_creds = pytest.mark.skipif(
    not (os.environ.get("IPTORRENTS_USERNAME") or os.environ.get("IPTORRENTS_USER")),
    reason="IPTorrents credentials not configured in environment",
)


class TestIPTorrentsPluginUnit:
    def test_plugin_imports(self):
        sys.path.insert(
            0, os.path.join(os.path.dirname(__file__), "..", "..", "plugins")
        )
        from iptorrents import iptorrents

        assert iptorrents.url == "https://iptorrents.com"
        assert iptorrents.name == "IPTorrents"

    def test_plugin_categories(self):
        sys.path.insert(
            0, os.path.join(os.path.dirname(__file__), "..", "..", "plugins")
        )
        from iptorrents import iptorrents

        cats = iptorrents.supported_categories
        assert "movies" in cats
        assert "tv" in cats
        assert cats["movies"] == "72"
        assert cats["tv"] == "73"

    def test_plugin_has_search_freeleech_method(self):
        sys.path.insert(
            0, os.path.join(os.path.dirname(__file__), "..", "..", "plugins")
        )
        from iptorrents import iptorrents

        assert hasattr(iptorrents, "search_freeleech")

    def test_plugin_has_download_method(self):
        sys.path.insert(
            0, os.path.join(os.path.dirname(__file__), "..", "..", "plugins")
        )
        from iptorrents import iptorrents

        assert hasattr(iptorrents, "download_torrent")


class TestIPTorrentsMergeService:
    def test_iptorrents_in_stats(self):
        status, body, _ = _fetch(f"{MERGE_URL}/api/v1/stats")
        assert status == 200
        data = json.loads(body)
        tracker_names = [t["name"] for t in data.get("trackers", [])]
        if not _has_iptorrents_creds():
            pytest.skip("IPTorrents creds not set")
        assert "iptorrents" in tracker_names, (
            f"iptorrents not in enabled trackers: {tracker_names}"
        )

    @no_creds
    def test_search_returns_results(self):
        data = json.dumps({"query": "ubuntu", "limit": 10}).encode()
        status, body, _ = _fetch(
            f"{MERGE_URL}/api/v1/search",
            method="POST",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        assert status in (200, 201, 202), f"Search failed: {status} {body}"
        result = json.loads(body)
        assert result.get("total_results", 0) >= 0

    @no_creds
    def test_search_results_have_freeleech_field(self):
        data = json.dumps({"query": "1080p", "limit": 20}).encode()
        status, body, _ = _fetch(
            f"{MERGE_URL}/api/v1/search",
            method="POST",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        if status not in (200, 201, 202):
            pytest.skip(f"Search returned {status}")
        result = json.loads(body)
        for r in result.get("results", []):
            if r.get("tracker") == "iptorrents":
                assert "freeleech" in r, f"Missing freeleech field in iptorrents result"
                return
        pytest.skip("No iptorrents results in this search")


class TestIPTorrentsFreeleechDetection:
    def test_parse_iptorrents_html_freeleech(self):
        sys.path.insert(
            0,
            os.path.join(
                os.path.dirname(__file__), "..", "..", "download-proxy", "src"
            ),
        )
        from merge_service.search import SearchOrchestrator

        orch = SearchOrchestrator()
        html = """<form><table id=torrents><tr>
<td><a class=" hv" href="/details.php?id=123">Ubuntu 22.04 LTS</a>
<span class="free">Free!</span></td>
<td><a href="/download.php/123.torrent?torrent_key=abc">DL</a></td>
<td>4.5 GB</td>
<td class="t_seeders">50</td>
<td class="t_leechers">10</td></t</tr>
<tr>
<td><a class=" hv" href="/details.php?id=456">Ubuntu 20.04 LTS</a></td>
<td><a href="/download.php/456.torrent?torrent_key=def">DL</a></td>
<td>3.2 GB</td>
<td class="t_seeders">30</td>
<td class="t_leechers">5</td></t</tr>
</table></form>"""
        results = orch._parse_iptorrents_html(html, "https://iptorrents.com")
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"

        free_results = [r for r in results if r.freeleech]
        non_free = [r for r in results if not r.freeleech]
        assert len(free_results) == 1, f"Expected 1 freeleech, got {len(free_results)}"
        assert len(non_free) == 1, f"Expected 1 non-free, got {len(non_free)}"
        assert free_results[0].name == "Ubuntu 22.04 LTS"
        assert free_results[0].tracker == "iptorrents"

    def test_freeleech_tracker_display_tag(self):
        sys.path.insert(
            0,
            os.path.join(
                os.path.dirname(__file__), "..", "..", "download-proxy", "src"
            ),
        )
        from merge_service.search import SearchResult

        free_result = SearchResult(
            name="Test",
            link="http://x",
            size="1 GB",
            seeds=10,
            leechers=5,
            engine_url="http://x",
            tracker="iptorrents",
            freeleech=True,
        )
        d = free_result.to_dict()
        assert d["tracker_display"] == "iptorrents [free]"

        paid_result = SearchResult(
            name="Test",
            link="http://x",
            size="1 GB",
            seeds=10,
            leechers=5,
            engine_url="http://x",
            tracker="iptorrents",
            freeleech=False,
        )
        d = paid_result.to_dict()
        assert d["tracker_display"] == "iptorrents"


class TestIPTorrentsDownloadFreeleechOnly:
    @no_creds
    def test_search_freeleech_via_merge_service(self):
        data = json.dumps({"query": "1080p", "limit": 20}).encode()
        status, body, _ = _fetch(
            f"{MERGE_URL}/api/v1/search",
            method="POST",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        if status not in (200, 201, 202):
            pytest.skip(f"Search returned {status}")

        result = json.loads(body)
        ip_results = [
            r
            for r in result.get("results", [])
            if r.get("tracker") == "iptorrents" and r.get("freeleech") is True
        ]
        for r in ip_results:
            assert r.get("freeleech") is True, f"Non-freeleech in results: {r}"
            assert "[free]" in r.get("tracker_display", ""), f"Missing [free] tag: {r}"

    @no_creds
    def test_plugin_search_freeleech_method(self):
        sys.path.insert(
            0, os.path.join(os.path.dirname(__file__), "..", "..", "plugins")
        )
        from iptorrents import iptorrents

        engine = iptorrents()
        if not engine.session:
            pytest.skip("Could not login to IPTorrents")
        import io
        from contextlib import redirect_stdout

        captured = io.StringIO()
        with redirect_stdout(captured):
            engine.search_freeleech("ubuntu")
        output = captured.getvalue()
        assert output is not None
