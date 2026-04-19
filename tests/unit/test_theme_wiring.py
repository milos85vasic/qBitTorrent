"""Integration guard for the runtime theme system.

These assertions cover the glue between the palette model, the
ThemeService, and the dashboard template. They complement the
parametric catalogue test (`test_palette_catalog.py`) and the frontend
Vitest specs — this suite makes sure the **wiring** stays correct even
when component refactors happen.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

STYLES_SCSS = REPO_ROOT / "frontend" / "src" / "styles.scss"
DASHBOARD_SCSS = (
    REPO_ROOT / "frontend" / "src" / "app" / "components" / "dashboard" / "dashboard.component.scss"
)
DASHBOARD_HTML = (
    REPO_ROOT / "frontend" / "src" / "app" / "components" / "dashboard" / "dashboard.component.html"
)
THEME_SERVICE = REPO_ROOT / "frontend" / "src" / "app" / "services" / "theme.service.ts"
PALETTE_MODEL = REPO_ROOT / "frontend" / "src" / "app" / "models" / "palette.model.ts"
THEME_PICKER_DIR = (
    REPO_ROOT / "frontend" / "src" / "app" / "components" / "theme-picker"
)

REQUIRED_CSS_VARS = (
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
)


def test_styles_scss_declares_all_root_fallbacks() -> None:
    text = STYLES_SCSS.read_text(encoding="utf-8")
    root_block = re.search(r":root\s*\{([^}]+)\}", text, re.S)
    assert root_block, f"{STYLES_SCSS} must declare a :root block"
    body = root_block.group(1)
    for var in REQUIRED_CSS_VARS:
        assert var in body, f"{STYLES_SCSS} :root missing {var}"


def test_dashboard_scss_uses_css_variables_not_sass_variables() -> None:
    text = DASHBOARD_SCSS.read_text(encoding="utf-8")
    # No Sass colour variables should leak through.
    forbidden_pattern = re.compile(
        r"\$(accent|accent-hover|bg-primary|bg-secondary|bg-tertiary|border|text-primary|"
        r"text-secondary|success|danger|warning|info|purple)\b"
    )
    hits = forbidden_pattern.findall(text)
    assert not hits, f"{DASHBOARD_SCSS} still references Sass colour variables: {hits}"
    # Positive assertion: the var() references are actually there.
    for var in ("--color-accent", "--color-bg-primary", "--color-text-primary"):
        assert f"var({var})" in text, f"{DASHBOARD_SCSS} should use var({var})"


def test_dashboard_template_includes_theme_picker() -> None:
    html = DASHBOARD_HTML.read_text(encoding="utf-8")
    assert "<app-theme-picker>" in html, "dashboard template must render <app-theme-picker>"


def test_dashboard_component_imports_theme_picker() -> None:
    ts = (
        REPO_ROOT / "frontend" / "src" / "app" / "components" / "dashboard" / "dashboard.component.ts"
    ).read_text(encoding="utf-8")
    assert "ThemePickerComponent" in ts
    assert "from '../theme-picker/theme-picker.component'" in ts


def test_theme_service_imports_palettes() -> None:
    ts = THEME_SERVICE.read_text(encoding="utf-8")
    # The service must import the catalogue from the model.
    assert "PALETTES" in ts
    assert "DEFAULT_PALETTE_ID" in ts
    assert "../models/palette.model" in ts


def test_theme_picker_component_files_present() -> None:
    for name in (
        "theme-picker.component.ts",
        "theme-picker.component.html",
        "theme-picker.component.scss",
        "theme-picker.component.spec.ts",
    ):
        assert (THEME_PICKER_DIR / name).is_file(), f"{name} missing"


def test_palette_model_exports_token_css_var_map() -> None:
    ts = PALETTE_MODEL.read_text(encoding="utf-8")
    # The service relies on this map to apply the 15 tokens by name.
    assert "TOKEN_CSS_VAR" in ts
    for var in REQUIRED_CSS_VARS:
        assert f"'{var}'" in ts, f"TOKEN_CSS_VAR map missing {var}"


@pytest.mark.parametrize("css_var", REQUIRED_CSS_VARS)
def test_dashboard_scss_references_every_css_var(css_var: str) -> None:
    """Every tokenised var must be used somewhere in the dashboard SCSS
    or the global styles — otherwise the token is dead weight."""
    merged = DASHBOARD_SCSS.read_text(encoding="utf-8") + STYLES_SCSS.read_text(encoding="utf-8")
    assert f"var({css_var})" in merged or css_var in merged, f"{css_var} is declared but unused"
