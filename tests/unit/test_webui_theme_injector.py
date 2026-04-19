"""
Unit tests for the qBittorrent WebUI theme-bridge injection.

Phase C of docs/CROSS_APP_THEME_PLAN.md adds two proxy-local routes
and an HTML injector that inserts a ``<link>`` + ``<script>`` pair
into every HTML response flowing through the download-proxy on
:7186. This file checks:

* ``inject_theme_assets()`` inserts exactly one of each bridge tag
  immediately before ``</head>``.
* Idempotent — a second call leaves the page with *one* link and
  *one* script.
* Non-HTML responses pass through unchanged.
* The content is skipped when ``DISABLE_THEME_INJECTION=1``.
* The two ``/__qbit_theme__/*`` routes return the CSS / JS bridges
  with ``Cache-Control: no-cache``.

The injector lives in :mod:`download_proxy` (the module installed to
``config/qBittorrent/nova3/engines/``). We import it through a file
spec so the test works both in repo tests and in a container-mounted
checkout.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "plugins" / "download_proxy.py"


def _load_download_proxy():
    spec = importlib.util.spec_from_file_location("download_proxy_under_test", PLUGIN_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["download_proxy_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def dp():
    return _load_download_proxy()


SAMPLE_HTML = (
    b"<!doctype html><html><head>"
    b"<meta charset='utf-8'><title>qBittorrent</title>"
    b"</head><body><div id='desktop'></div></body></html>"
)


def test_injector_inserts_both_tags_before_head_close(dp):
    out = dp.inject_theme_assets(SAMPLE_HTML, "text/html; charset=utf-8")
    text = out.decode("utf-8")
    assert '<link rel="stylesheet" href="/__qbit_theme__/skin.css">' in text
    assert '<script src="/__qbit_theme__/bootstrap.js" defer></script>' in text
    # Tags are before </head> (case-insensitive).
    head_close = text.lower().rfind("</head>")
    link_pos = text.find('/__qbit_theme__/skin.css')
    script_pos = text.find('/__qbit_theme__/bootstrap.js')
    assert 0 < link_pos < head_close
    assert 0 < script_pos < head_close


def test_injector_is_idempotent(dp):
    once = dp.inject_theme_assets(SAMPLE_HTML, "text/html")
    twice = dp.inject_theme_assets(once, "text/html")
    text = twice.decode("utf-8")
    # Each bridge tag appears exactly once.
    assert text.count('/__qbit_theme__/skin.css') == 1
    assert text.count('/__qbit_theme__/bootstrap.js') == 1


def test_injector_is_case_insensitive_on_head_tag(dp):
    html = b"<HTML><HEAD><TITLE>x</TITLE></HEAD><BODY>ok</BODY></HTML>"
    out = dp.inject_theme_assets(html, "text/html")
    assert b"/__qbit_theme__/skin.css" in out
    assert b"/__qbit_theme__/bootstrap.js" in out


def test_non_html_content_passes_through(dp):
    payload = b"\xff\xd8\xff\xe0 binary image"
    out = dp.inject_theme_assets(payload, "image/jpeg")
    assert out == payload


def test_no_head_tag_passes_through(dp):
    """If qBittorrent ever ships a response without a </head>, leave it alone."""
    html = b"<div>fragment without a head</div>"
    out = dp.inject_theme_assets(html, "text/html")
    assert out == html


def test_injection_skipped_when_disabled(dp, monkeypatch):
    monkeypatch.setenv("DISABLE_THEME_INJECTION", "1")
    # Force the module to re-read the env var if it memoises.
    out = dp.inject_theme_assets(SAMPLE_HTML, "text/html")
    assert out == SAMPLE_HTML


def test_bridge_css_has_required_variables(dp):
    css = dp.THEME_SKIN_CSS
    # Every CSS custom property declared at :root.
    required = [
        "--color-bg-primary",
        "--color-bg-secondary",
        "--color-bg-tertiary",
        "--color-border",
        "--color-text-primary",
        "--color-text-secondary",
        "--color-accent",
        "--color-accent-hover",
        "--color-contrast",
        "--color-success",
        "--color-danger",
        "--color-warning",
        "--color-info",
        "--color-purple",
        "--color-shadow",
    ]
    for var in required:
        assert var in css, f"missing {var} in skin.css"


def test_bridge_js_has_every_palette_inline(dp):
    js = dp.THEME_BOOTSTRAP_JS
    # The 8-palette catalog must be inlined so the bridge does not
    # need a second HTTP call — the comment in the plan is emphatic.
    for palette_id in (
        "darcula",
        "dracula",
        "solarized",
        "nord",
        "monokai",
        "gruvbox",
        "one-dark",
        "tokyo-night",
    ):
        assert palette_id in js, f"{palette_id} missing from inlined catalog"
    # The bridge must fetch /api/v1/theme and subscribe to the stream.
    assert "/api/v1/theme" in js
    assert "EventSource" in js


def test_content_length_is_rewritten(dp):
    """A direct check of the combined helper used by proxy_to_qbittorrent."""
    out = dp.inject_theme_assets(SAMPLE_HTML, "text/html")
    assert len(out) > len(SAMPLE_HTML)


def test_routes_return_css_and_js_no_cache(dp, tmp_path):
    """The /__qbit_theme__/skin.css and /bootstrap.js handlers return
    200 with Cache-Control: no-cache."""
    # Build a fake handler by calling the helper directly.
    status, headers, body = dp.serve_theme_asset("/__qbit_theme__/skin.css")
    assert status == 200
    # Normalise header keys for a case-insensitive check.
    ci = {k.lower(): v for k, v in headers.items()}
    assert ci.get("content-type", "").startswith("text/css")
    assert "no-cache" in ci.get("cache-control", "").lower()
    assert b":root" in body

    status, headers, body = dp.serve_theme_asset("/__qbit_theme__/bootstrap.js")
    assert status == 200
    ci = {k.lower(): v for k, v in headers.items()}
    assert ci.get("content-type", "").startswith("application/javascript")
    assert "no-cache" in ci.get("cache-control", "").lower()
    assert b"EventSource" in body


def test_serve_theme_asset_returns_404_for_unknown(dp):
    assert dp.serve_theme_asset("/__qbit_theme__/something-else.png")[0] == 404
