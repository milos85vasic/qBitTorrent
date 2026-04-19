"""Guards the per-element drop-shadow tokens.

The user asked for accent-coloured elements (blood red in Darcula,
different hues in other palettes) to carry a *black* drop-shadow so
they don't look flat against any background. These tests assert:

1. The global stylesheet ships the expected shadow tokens at :root.
2. The light-palette override (``html[data-mode="light"]``) redefines
   them with softer alphas.
3. The dashboard stylesheet references the tokens on the elements
   that are styled with ``var(--color-accent)`` — h1, h2 inside cards,
   stat-value numbers, active tab, tracker-tag freeleech, merged
   indicator, auth-indicator dot, column headers.
4. Buttons carry elevation shadows on the base + hover + active
   states.
5. Shadow values are always black (rgba 0,0,0,...) never coloured,
   so they read across every palette without per-palette tuning.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STYLES = REPO / "frontend" / "src" / "styles.scss"
DASHBOARD = REPO / "frontend" / "src" / "app" / "components" / "dashboard" / "dashboard.component.scss"
FOOTER = REPO / "frontend" / "src" / "app" / "components" / "site-footer" / "site-footer.component.ts"
TRACKER_DIALOG = REPO / "frontend" / "src" / "app" / "components" / "tracker-stat-dialog" / "tracker-stat-dialog.component.scss"
CONFIRM = REPO / "frontend" / "src" / "app" / "components" / "confirm-dialog" / "confirm-dialog.component.ts"
MAGNET = REPO / "frontend" / "src" / "app" / "components" / "magnet-dialog" / "magnet-dialog.component.ts"
QBIT_LOGIN = REPO / "frontend" / "src" / "app" / "components" / "qbit-login-dialog" / "qbit-login-dialog.component.ts"
TOAST = REPO / "frontend" / "src" / "app" / "components" / "toast-container" / "toast-container.component.ts"
THEME_PICKER = REPO / "frontend" / "src" / "app" / "components" / "theme-picker" / "theme-picker.component.scss"


REQUIRED_SHADOW_TOKENS = [
    "--shadow-text-xs",
    "--shadow-text-sm",
    "--shadow-text-md",
    "--shadow-text-lg",
    "--shadow-elev-1",
    "--shadow-elev-2",
    "--shadow-elev-3",
    "--shadow-glow-dot",
]


@pytest.fixture(scope="module")
def styles() -> str:
    return STYLES.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dashboard_scss() -> str:
    return DASHBOARD.read_text(encoding="utf-8")


@pytest.mark.parametrize("token", REQUIRED_SHADOW_TOKENS)
def test_styles_scss_defines_shadow_token_under_root(token: str, styles: str) -> None:
    """Every documented shadow token is defined under :root."""
    # Use a regex without \b because CSS custom properties start with a
    # non-word character (`-`), which stops word-boundary matching.
    assert re.search(rf":root\s*\{{[^}}]*{re.escape(token)}\s*:", styles, re.DOTALL), (
        f"{token} must be declared inside :root {{}} in frontend/src/styles.scss"
    )


@pytest.mark.parametrize("token", REQUIRED_SHADOW_TOKENS)
def test_styles_scss_overrides_shadow_token_for_light_mode(token: str, styles: str) -> None:
    """The light-mode override block redefines every shadow token."""
    m = re.search(
        r'html\[data-mode="light"\]\s*\{([^}]+)\}',
        styles,
        re.DOTALL,
    )
    assert m is not None, "styles.scss must contain an html[data-mode=\"light\"] block"
    assert re.search(rf"{re.escape(token)}\s*:", m.group(1)), (
        f"{token} must be redefined in html[data-mode=\"light\"]"
    )


def test_shadow_tokens_are_always_black(styles: str) -> None:
    """Shadows must use rgba(0,0,0, ...) so they read on every palette."""
    # Extract every shadow-token rule across :root + light-mode override.
    lines = [ln for ln in styles.splitlines() if "--shadow-" in ln and ":" in ln]
    assert lines, "expected at least one shadow-token line"
    # Normalise whitespace.
    colour_only = re.compile(r"rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0?\.?\d+\s*\)")
    for ln in lines:
        # Strip the declaration's LHS.
        rhs = ln.split(":", 1)[1]
        # Every rgba(...) on the RHS must be black.
        for rgba in re.findall(r"rgba\([^)]+\)", rhs):
            assert colour_only.fullmatch(rgba), (
                f"shadow token uses a non-black rgba: {rgba!r} in line {ln.strip()!r}"
            )


@pytest.mark.parametrize(
    "selector,expected_token",
    [
        ("h1 {", "--shadow-text-lg"),
        ("  h2 {", "--shadow-text-md"),          # h2 inside .card
        (".stat-value", "--shadow-text-lg"),
        (".tab {", "--shadow-text-sm"),           # .tab.active label
        (".auth-indicator {", "--shadow-glow-dot"),
        (".card {", "--shadow-elev-3"),
        (".stat-item {", "--shadow-elev-1"),
        (".merged-indicator {", "--shadow-elev-1"),
        (".tracker-tag {", "--shadow-elev-1"),
        (".download-btn {", "--shadow-elev-1"),
        (".type-badge, .quality-badge {", "--shadow-elev-1"),
    ],
)
def test_dashboard_applies_shadow_on(selector: str, expected_token: str, dashboard_scss: str) -> None:
    """Every accent-coloured element in dashboard.scss references a
    shadow token within its rule block.
    """
    # Find the selector + its immediate rule body.
    idx = dashboard_scss.find(selector)
    assert idx >= 0, f"selector {selector!r} not found in dashboard.component.scss"
    # Walk forward to its closing brace, matching nested blocks.
    depth = 0
    body_start = dashboard_scss.find("{", idx)
    assert body_start >= 0
    i = body_start
    while i < len(dashboard_scss):
        ch = dashboard_scss[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    body = dashboard_scss[body_start : i + 1]
    assert expected_token in body, (
        f"{selector!r} rule body should reference {expected_token}; got {body[:200]!r}..."
    )


def test_search_form_button_lifts_on_hover(dashboard_scss: str) -> None:
    """The Search CTA button chain must be elevation-2 base → 3 hover
    → 1 active, so it reads as a real affordance.
    """
    # Isolate the .search-form button block.
    block = re.search(r"\.search-form \{.*?\n\}", dashboard_scss, re.DOTALL)
    assert block is not None
    body = block.group(0)
    # Base state — elevation 2
    assert "box-shadow: var(--shadow-elev-2)" in body, "Search button must have elevation-2 at rest"
    # Hover state — elevation 3
    assert ":hover" in body and "--shadow-elev-3" in body
    # Active state — elevation 1
    assert ":active" in body and "--shadow-elev-1" in body


def test_footer_heart_and_link_have_text_shadow() -> None:
    src = FOOTER.read_text(encoding="utf-8")
    # Both the heart and the vd-link carry --shadow-text-sm.
    assert src.count("text-shadow: var(--shadow-text-sm)") >= 2, (
        "site-footer heart AND Vasic Digital link must both carry --shadow-text-sm"
    )


@pytest.mark.parametrize(
    "path,marker",
    [
        (TRACKER_DIALOG, "--shadow-elev-3"),   # .modal
        (TRACKER_DIALOG, "--shadow-text-md"),  # h3
        (CONFIRM, "--shadow-elev-3"),
        (CONFIRM, "--shadow-text-md"),
        (MAGNET, "--shadow-elev-3"),
        (MAGNET, "--shadow-text-md"),
        (QBIT_LOGIN, "--shadow-elev-3"),
        (QBIT_LOGIN, "--shadow-text-md"),
        (TOAST, "--shadow-elev-3"),
        (THEME_PICKER, "--shadow-elev-1"),
        (THEME_PICKER, "--shadow-elev-3"),
    ],
)
def test_component_uses_shadow_token(path: Path, marker: str) -> None:
    src = path.read_text(encoding="utf-8")
    assert marker in src, f"{path.name} must reference {marker}"
