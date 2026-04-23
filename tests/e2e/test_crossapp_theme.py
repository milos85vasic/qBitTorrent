"""
Real cross-app theme e2e test (Phase D of CROSS_APP_THEME_PLAN.md).

Opens the Angular dashboard at :7187, picks Nord in the palette
dropdown, opens a second page at the proxied qBittorrent WebUI
(:7186), and waits for the bridge to apply Nord's bg-primary to
``document.body``. Then switches to Gruvbox and asserts the flip.

The skip-guard looks for ``/__qbit_theme__/skin.css`` in the :7186
HTML response. If that is missing, we skip with an actionable
message ("rebuild + restart qbittorrent-proxy") rather than failing
noisily on an environment that hasn't deployed the bridge yet.

Any real failure in the cross-app sync path (palette mismatch, SSE
silence, side-channel missing) makes the test fail — *not* skip —
so the signal is trustworthy.
"""

from __future__ import annotations

import os
import urllib.request

import pytest

# playwright is a hard requirement for these e2e tests. If the import
# fails, the tests legitimately cannot run and the failure is visible
# rather than hidden behind a skip.
from playwright.sync_api import sync_playwright

DASHBOARD_URL = os.environ.get("MERGE_SERVICE_URL", "http://localhost:7187").rstrip("/")
PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:7186").rstrip("/")

# Nord + Gruvbox dark bg-primary values from the catalogue — these
# must match frontend/src/app/models/palette.model.ts exactly.
NORD_DARK_BG = "#2e3440"
GRUVBOX_DARK_BG = "#282828"


def _hex_to_rgb(hex6: str) -> str:
    hex6 = hex6.lstrip("#")
    r, g, b = int(hex6[0:2], 16), int(hex6[2:4], 16), int(hex6[4:6], 16)
    return f"rgb({r}, {g}, {b})"


def _preflight() -> None:
    """Fail loudly when services are down; skip cleanly when the
    bridge is not yet deployed (rebuild + restart needed).
    """
    # 1) Dashboard reachable.
    with urllib.request.urlopen(DASHBOARD_URL + "/", timeout=5) as resp:
        assert resp.status == 200, f"Dashboard returned {resp.status}"
        body = resp.read().decode("utf-8", errors="ignore")

    # 2) Dashboard bundle has the theme picker.
    import re as _re

    m = _re.search(r"main-[A-Z0-9]+\.js", body)
    assert m, (
        "Could not locate main-*.js in the index HTML — rebuild the "
        "frontend (`cd frontend && ng build`) and restart qbittorrent-proxy"
    )
    with urllib.request.urlopen(f"{DASHBOARD_URL}/{m.group(0)}", timeout=10) as r:
        bundle = r.read().decode("utf-8", errors="ignore")
    assert "theme-picker" in bundle or "palette-dropdown" in bundle, (
        "Dashboard bundle does not include the theme-picker — rebuild + restart qbittorrent-proxy and re-run"
    )

    # 3) Proxy reachable.
    with urllib.request.urlopen(PROXY_URL + "/", timeout=5) as resp:
        proxy_body = resp.read().decode("utf-8", errors="ignore")

    # 4) Bridge injected.
    assert "/__qbit_theme__/skin.css" in proxy_body, (
        "qBittorrent WebUI is not serving the theme bridge yet — rebuild "
        "+ restart qbittorrent-proxy so plugins/download_proxy.py is live"
    )


@pytest.fixture(scope="module", autouse=True)
def _check_environment() -> None:
    _preflight()


def _select_palette(page, palette_id: str) -> None:
    page.click("app-theme-picker .palette-dropdown")
    page.wait_for_selector("app-theme-picker .palette-menu li", timeout=5000)
    page.click(f'app-theme-picker li[data-palette-id="{palette_id}"]')
    page.wait_for_function(
        f"() => document.documentElement.getAttribute('data-palette') === {palette_id!r}",
        timeout=5000,
    )


def test_crossapp_theme_sync_nord_then_gruvbox() -> None:
    # Force dark mode before the test. Without this, whichever mode
    # was last persisted in /api/v1/theme leaks in and the
    # ``NORD_DARK_BG`` / ``GRUVBOX_DARK_BG`` assertions fail because
    # the palette's LIGHT bg-primary is what the bridge applies.
    import json as _json

    req = urllib.request.Request(
        f"{DASHBOARD_URL}/api/v1/theme",
        data=_json.dumps({"paletteId": "nord", "mode": "dark"}).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 200, f"PUT /api/v1/theme returned {r.status}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            dashboard = context.new_page()
            dashboard.goto(DASHBOARD_URL + "/", wait_until="domcontentloaded")
            dashboard.wait_for_selector("app-theme-picker .palette-dropdown", timeout=15000)

            # Reset to Nord on the dashboard.
            _select_palette(dashboard, "nord")
            stored = dashboard.evaluate("() => window.localStorage.getItem('qbit.theme')")
            assert stored and '"nord"' in stored, f"dashboard did not persist Nord: {stored!r}"

            # Open qBittorrent WebUI via the proxy.
            webui = context.new_page()
            webui.goto(PROXY_URL + "/", wait_until="domcontentloaded")

            # Wait for the bridge to apply Nord. The bridge fetches
            # /api/v1/theme on first paint + subscribes to the SSE
            # stream — under batch load this can take a few seconds.
            webui.wait_for_function(
                "(expectedRgb) => {\n"
                "  const v = getComputedStyle(document.documentElement).getPropertyValue('--color-bg-primary').trim().toLowerCase();\n"
                "  return v === expectedRgb.toLowerCase() || v === expectedRgb.toUpperCase();\n"
                "}",
                arg=NORD_DARK_BG,
                timeout=30000,
            )

            # The side-channel shows the adopted palette.
            side = webui.evaluate("() => window.__qbitTheme && window.__qbitTheme.paletteId")
            assert side == "nord", f"window.__qbitTheme.paletteId on :7186 is {side!r}, expected 'nord'"

            # Flip to Gruvbox on the dashboard.
            _select_palette(dashboard, "gruvbox")
            stored2 = dashboard.evaluate("() => window.localStorage.getItem('qbit.theme')")
            assert stored2 and '"gruvbox"' in stored2

            # qBittorrent WebUI should mirror within a few seconds
            # via SSE — allow up to 15 s because the stream's event
            # cadence can be paced down under batch load.
            webui.wait_for_function(
                "(expectedHex) => {\n"
                "  const v = getComputedStyle(document.documentElement).getPropertyValue('--color-bg-primary').trim().toLowerCase();\n"
                "  return v === expectedHex.toLowerCase();\n"
                "}",
                arg=GRUVBOX_DARK_BG,
                timeout=15000,
            )
            side2 = webui.evaluate("() => window.__qbitTheme && window.__qbitTheme.paletteId")
            assert side2 == "gruvbox", f"window.__qbitTheme.paletteId on :7186 is {side2!r}, expected 'gruvbox'"
        finally:
            browser.close()
