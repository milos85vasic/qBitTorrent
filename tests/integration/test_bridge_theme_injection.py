"""Guards that the webui-bridge at :7188 injects the theme bridge
assets exactly the way the download-proxy at :7186 does.

The user reported that opening qBittorrent WebUI through the bridge
displayed an unthemed qBittorrent page because the injector only
lived in plugins/download_proxy.py. The shared helpers now live in
plugins/theme_injector.py and webui-bridge.py imports from there.
These tests assert the wiring.
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BRIDGE_SRC = REPO / "webui-bridge.py"
SHARED_SRC = REPO / "plugins" / "theme_injector.py"


@pytest.fixture(scope="module")
def bridge_src() -> str:
    return BRIDGE_SRC.read_text(encoding="utf-8")


def test_shared_theme_injector_module_exists() -> None:
    assert SHARED_SRC.is_file(), SHARED_SRC
    # Make sure the public surface we need is exported.
    text = SHARED_SRC.read_text(encoding="utf-8")
    for symbol in (
        "def inject_theme_assets(",
        "def serve_theme_asset(",
        "def rewrite_csp(",
        "def maybe_decode_body(",
        "THEME_INJECTION_MARKER",
        "THEME_SKIN_CSS",
        "THEME_BOOTSTRAP_JS",
    ):
        assert symbol in text, f"plugins/theme_injector.py missing {symbol!r}"


def test_bridge_imports_theme_injector(bridge_src: str) -> None:
    assert "import theme_injector" in bridge_src, "webui-bridge.py must import theme_injector from plugins/"
    # Confirm the sys.path injection is there — without it the import
    # would fail since webui-bridge.py lives at repo root.
    assert "sys.path.insert(0, _PLUGINS_DIR)" in bridge_src


def test_bridge_serves_theme_assets_locally(bridge_src: str) -> None:
    """The bridge must NOT forward /__qbit_theme__/* requests to
    qBittorrent (those paths do not exist upstream). Instead it calls
    theme_injector.serve_theme_asset() directly.
    """
    # The check must be before the torrent-download-url branch and
    # before proxy_to_qbittorrent. Regex sniffs for the branch.
    assert 'path.startswith("/__qbit_theme__/")' in bridge_src
    assert "theme_injector.serve_theme_asset(path)" in bridge_src


def test_bridge_injects_theme_on_html_responses(bridge_src: str) -> None:
    """The proxy_to_qbittorrent method must call inject_theme_assets
    on text/html responses and strip Content-Encoding when it
    decompressed the upstream body.
    """
    m = re.search(r"def proxy_to_qbittorrent\(.*?\n(?:\n{2,}|\Z)", bridge_src, re.DOTALL)
    assert m is not None
    body = m.group(0)
    assert "inject_theme_assets" in body
    assert "maybe_decode_body" in body
    assert "rewrite_csp" in body
    # When we mutate, we must rewrite Content-Length.
    assert 'self.send_header("Content-Length"' in body


# ---------------------------------------------------------------------------
# Live smoke — skips cleanly if bridge not up
# ---------------------------------------------------------------------------


@pytest.mark.timeout(15)
def test_bridge_serves_skin_css_live(webui_bridge_live: str) -> None:
    with urllib.request.urlopen(f"{webui_bridge_live}/__qbit_theme__/skin.css", timeout=10) as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8")
        assert "--color-accent" in body
        assert resp.headers.get("Content-Type", "").startswith("text/css")


@pytest.mark.timeout(15)
def test_bridge_serves_bootstrap_js_live(webui_bridge_live: str) -> None:
    with urllib.request.urlopen(f"{webui_bridge_live}/__qbit_theme__/bootstrap.js", timeout=10) as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8")
        # Palette catalog must be inlined.
        for pid in ("darcula", "nord", "gruvbox", "dracula"):
            assert f'"{pid}"' in body, f"bootstrap.js missing palette id {pid!r}"
        # Event listener for live updates must be present.
        assert "addEventListener" in body and "theme" in body


@pytest.mark.timeout(30)
def test_bridge_html_response_contains_injected_tags_live(webui_bridge_live: str) -> None:
    """After logging in, GET / must have both the <link> and <script>
    bridge tags injected into the HTML.
    """
    # Post credentials + keep cookie.
    import http.cookiejar

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    data = urllib.parse.urlencode({"username": "admin", "password": "admin"}).encode()
    req = urllib.request.Request(
        f"{webui_bridge_live}/api/v2/auth/login",
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": webui_bridge_live,
        },
        method="POST",
    )
    with opener.open(req, timeout=10) as resp:
        assert resp.status == 200, f"login returned {resp.status}"

    # Fetch a theme-relevant page: the WebUI shell at /.
    req2 = urllib.request.Request(
        f"{webui_bridge_live}/",
        headers={"Accept-Encoding": "identity"},
    )
    with opener.open(req2, timeout=5) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
    assert "/__qbit_theme__/skin.css" in body, "bridge did not inject skin.css <link> tag"
    assert "/__qbit_theme__/bootstrap.js" in body, "bridge did not inject bootstrap.js <script> tag"
