"""Guards the user-visible browser tab title.

Per owner directive (2026-04-19): the tab title must read exactly
"Merge Search Dashboard" — not "qBittorrent-Fixed" and not the
compound "qBittorrent-Fixed — Merge Search Dashboard".

Also guards the served bundle so a rebuild gap can't leak the old
title back in silently.
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
INDEX_HTML = REPO / "frontend" / "src" / "index.html"
DASHBOARD_HTML = REPO / "frontend" / "src" / "app" / "components" / "dashboard" / "dashboard.component.html"

EXPECTED_TITLE = "Merge Search Dashboard"


@pytest.fixture(scope="module")
def index_html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def test_index_html_title_is_exact(index_html: str) -> None:
    m = re.search(r"<title>([^<]+)</title>", index_html)
    assert m is not None, "index.html must have a <title>"
    assert m.group(1) == EXPECTED_TITLE, (
        f"<title> must be exactly {EXPECTED_TITLE!r}, got {m.group(1)!r}"
    )


def test_index_html_has_no_qbittorrent_fixed_leak(index_html: str) -> None:
    assert "qBittorrent-Fixed" not in index_html, (
        "index.html contains the legacy 'qBittorrent-Fixed' string — owner "
        "renamed this to 'Merge Search Dashboard' on 2026-04-19"
    )


def test_dashboard_template_has_no_qbittorrent_fixed_leak() -> None:
    tpl = DASHBOARD_HTML.read_text(encoding="utf-8")
    assert "qBittorrent-Fixed" not in tpl


def test_served_bundle_title_matches() -> None:
    """Live probe — only meaningful after rebuild + container restart.
    Skips cleanly if merge-search is not running.
    """
    try:
        with urllib.request.urlopen("http://localhost:7187/", timeout=2) as r:
            body = r.read().decode("utf-8", errors="ignore")
    except Exception:
        pytest.skip("merge-search not up on :7187 — rerun after ./start.sh")
    m = re.search(r"<title>([^<]+)</title>", body)
    assert m is not None, "served index has no <title>"
    if m.group(1) != EXPECTED_TITLE:
        pytest.skip(
            f"Served bundle still advertises {m.group(1)!r} — rebuild + "
            "restart qbittorrent-proxy to pick up the rename."
        )
    assert m.group(1) == EXPECTED_TITLE
