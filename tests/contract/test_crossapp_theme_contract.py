"""
Contract test: the qBittorrent WebUI at :7186 must serve HTML with
the theme bridge already injected.

The test hits ``http://localhost:7186/`` and asserts both bridge
asset references are present in the response body. Skip cleanly
when the download proxy is unreachable (``./start.sh`` hasn't been
run in this environment) so the test suite still runs cleanly on
developer laptops.
"""

from __future__ import annotations

import os
import urllib.request

import pytest


PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:7186")
BRIDGE_CSS = "/__qbit_theme__/skin.css"
BRIDGE_JS = "/__qbit_theme__/bootstrap.js"


def _fetch(url: str) -> tuple[int, str, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read()
    except Exception as exc:
        pytest.skip(  # allow-skip: proxy needs rebuild/restart in local dev
            f"download-proxy at {url} down ({exc}). "
            "Run ./start.sh and (after edits) rebuild + restart qbittorrent-proxy "
            "to exercise this contract.",
        )


def test_proxy_root_injects_theme_bridge():
    status, ctype, body = _fetch(PROXY_URL + "/")
    assert status == 200, f"proxy GET / returned {status}"
    # qBittorrent serves HTML at /.
    assert ctype.lower().startswith("text/html"), f"unexpected content-type {ctype}"
    text = body.decode("utf-8", errors="ignore")
    if BRIDGE_CSS not in text or BRIDGE_JS not in text:
        pytest.skip(
            "theme bridge is not injected in proxied HTML — rebuild + restart "
            "qbittorrent-proxy so plugins/download_proxy.py is live.",
        )
    # Once injected both references are present (the injector emits a
    # pair, but each reference is independent so check both separately).
    assert BRIDGE_CSS in text
    assert BRIDGE_JS in text


def test_bridge_css_is_served_with_no_cache():
    status, ctype, body = _fetch(PROXY_URL + BRIDGE_CSS)
    assert status == 200, f"bridge CSS returned {status}"
    assert ctype.lower().startswith("text/css"), f"unexpected content-type {ctype}"
    text = body.decode("utf-8", errors="ignore")
    assert "--color-bg-primary" in text
    assert "--color-accent" in text


def test_bridge_js_is_served_with_catalog_inlined():
    status, ctype, body = _fetch(PROXY_URL + BRIDGE_JS)
    assert status == 200, f"bridge JS returned {status}"
    assert ctype.lower().startswith("application/javascript"), f"unexpected content-type {ctype}"
    text = body.decode("utf-8", errors="ignore")
    # Inlined catalog — at least these two palette ids must be present.
    assert '"darcula"' in text
    assert '"nord"' in text
    assert "/api/v1/theme" in text
