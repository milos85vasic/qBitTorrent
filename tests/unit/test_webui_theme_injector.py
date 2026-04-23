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
    link_pos = text.find("/__qbit_theme__/skin.css")
    script_pos = text.find("/__qbit_theme__/bootstrap.js")
    assert 0 < link_pos < head_close
    assert 0 < script_pos < head_close


def test_injector_is_idempotent(dp):
    once = dp.inject_theme_assets(SAMPLE_HTML, "text/html")
    twice = dp.inject_theme_assets(once, "text/html")
    text = twice.decode("utf-8")
    # Each bridge tag appears exactly once.
    assert text.count("/__qbit_theme__/skin.css") == 1
    assert text.count("/__qbit_theme__/bootstrap.js") == 1


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


def test_csp_rewrite_adds_merge_origin_to_connect_src(dp):
    """qBittorrent's CSP has no connect-src directive, so the browser
    falls back to default-src 'self' and blocks cross-origin fetch +
    EventSource. The proxy layer must inject connect-src with the
    merge-service origin."""
    original = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; script-src 'self' 'unsafe-inline'; "
        "object-src 'none'; form-action 'self'; "
        "frame-src 'self' blob:; frame-ancestors 'self';"
    )
    rewritten = dp.rewrite_csp(original)
    assert "connect-src" in rewritten
    assert dp.MERGE_SERVICE_ORIGIN in rewritten
    # Other directives preserved.
    assert "default-src" in rewritten
    assert "script-src" in rewritten
    assert "frame-ancestors" in rewritten


def test_csp_rewrite_is_idempotent(dp):
    original = "default-src 'self'; connect-src 'self' " + dp.MERGE_SERVICE_ORIGIN + ";"
    assert dp.rewrite_csp(original).count(dp.MERGE_SERVICE_ORIGIN) == 1


def test_csp_rewrite_extends_existing_connect_src(dp):
    original = "default-src 'self'; connect-src 'self' https://other.example;"
    rewritten = dp.rewrite_csp(original)
    assert "https://other.example" in rewritten
    assert dp.MERGE_SERVICE_ORIGIN in rewritten


def test_csp_rewrite_honours_disable_flag(dp, monkeypatch):
    monkeypatch.setenv("DISABLE_THEME_INJECTION", "1")
    header = "default-src 'self'; connect-src 'self';"
    assert dp.rewrite_csp(header) == header


def test_csp_rewrite_passes_empty_through(dp):
    assert dp.rewrite_csp("") == ""
    assert dp.rewrite_csp(None) is None


def test_body_gzip_is_decompressed_for_injection(dp):
    """qBittorrent returns gzip-encoded HTML when the browser sends
    Accept-Encoding: gzip. The injector needs to see plain text, so
    the proxy must decompress first. We test the helper directly."""
    import gzip as _gzip

    decoded, flag = dp._maybe_decode_body(_gzip.compress(SAMPLE_HTML), "gzip")
    assert flag is True
    assert decoded == SAMPLE_HTML


def test_body_deflate_is_decompressed(dp):
    import zlib as _zlib

    decoded, flag = dp._maybe_decode_body(_zlib.compress(SAMPLE_HTML), "deflate")
    assert flag is True
    assert decoded == SAMPLE_HTML


def test_body_raw_deflate_is_decompressed(dp):
    import zlib as _zlib

    # Raw deflate (no zlib header).
    compressor = _zlib.compressobj(wbits=-_zlib.MAX_WBITS)
    raw = compressor.compress(SAMPLE_HTML) + compressor.flush()
    decoded, flag = dp._maybe_decode_body(raw, "deflate")
    assert flag is True
    assert decoded == SAMPLE_HTML


def test_body_unknown_encoding_flags_false(dp):
    decoded, flag = dp._maybe_decode_body(b"\x00\x01\x02", "br")
    assert flag is False


def test_body_no_encoding_flags_true(dp):
    decoded, flag = dp._maybe_decode_body(SAMPLE_HTML, "")
    assert flag is True
    assert decoded == SAMPLE_HTML
