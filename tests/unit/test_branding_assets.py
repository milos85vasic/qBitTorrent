"""Guards the branding / launcher-icon / PWA-manifest pipeline.

These tests live in the Python suite (not frontend/) because they are
pure file-presence + byte-level checks — they don't need a browser or
Angular to validate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_LOGO = REPO_ROOT / "assets" / "Logo.jpeg"
PUBLIC = REPO_ROOT / "frontend" / "public"
ICONS = PUBLIC / "icons"
DOCS_LOGO = REPO_ROOT / "docs" / "assets" / "logo.png"
WEBSITE_LOGO = REPO_ROOT / "website" / "docs" / "assets" / "logo.png"
INDEX_HTML = REPO_ROOT / "frontend" / "src" / "index.html"
MANIFEST = PUBLIC / "manifest.webmanifest"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def test_source_logo_exists_and_is_reasonable_size() -> None:
    assert SOURCE_LOGO.is_file(), SOURCE_LOGO
    size = SOURCE_LOGO.stat().st_size
    assert 10_000 < size < 10_000_000, f"Logo unusually sized: {size} bytes"


@pytest.mark.parametrize(
    "name",
    [
        "favicon.ico",
        "logo.png",
        "logo-header.png",
        "manifest.webmanifest",
    ],
)
def test_public_branding_asset_present(name: str) -> None:
    assert (PUBLIC / name).is_file(), f"frontend/public/{name} is missing"


@pytest.mark.parametrize(
    "name",
    [
        "apple-touch-icon.png",
        "icon-72x72.png",
        "icon-96x96.png",
        "icon-128x128.png",
        "icon-144x144.png",
        "icon-152x152.png",
        "icon-192x192.png",
        "icon-384x384.png",
        "icon-512x512.png",
    ],
)
def test_launcher_icon_present(name: str) -> None:
    assert (ICONS / name).is_file(), f"frontend/public/icons/{name} is missing"


def test_docs_logo_present() -> None:
    assert DOCS_LOGO.is_file(), DOCS_LOGO
    assert WEBSITE_LOGO.is_file(), WEBSITE_LOGO


def test_index_html_references_favicon_and_manifest() -> None:
    text = INDEX_HTML.read_text()
    for ref in (
        'rel="icon"',
        "favicon.ico",
        'rel="apple-touch-icon"',
        'rel="manifest"',
        "manifest.webmanifest",
        'meta name="theme-color"',
    ):
        assert ref in text, f"index.html missing {ref!r}"


def test_manifest_has_required_pwa_fields(manifest: dict) -> None:
    for field in ("name", "short_name", "start_url", "display", "icons"):
        assert field in manifest, f"manifest missing {field!r}"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"


def test_manifest_icons_cover_launcher_sizes(manifest: dict) -> None:
    declared = {icon["sizes"] for icon in manifest["icons"]}
    required = {"72x72", "96x96", "128x128", "144x144", "152x152", "192x192", "384x384", "512x512"}
    missing = required - declared
    assert not missing, f"manifest missing icon sizes: {missing}"


def test_manifest_has_maskable_icon(manifest: dict) -> None:
    maskable = [icon for icon in manifest["icons"] if "maskable" in (icon.get("purpose") or "")]
    assert maskable, "manifest should declare at least one maskable icon"


def test_dashboard_template_references_logo() -> None:
    tpl = (REPO_ROOT / "frontend" / "src" / "app" / "components" / "dashboard" / "dashboard.component.html").read_text()
    assert "logo-header.png" in tpl or "logo.png" in tpl, "dashboard template should reference the branding logo"
    assert 'class="brand"' in tpl or 'class="brand-logo"' in tpl, "dashboard should have .brand/.brand-logo element"
