"""Palette catalogue validator.

The source of truth for the runtime-switchable colour system lives in
``frontend/src/app/models/palette.model.ts``. This suite parses that
TypeScript file and asserts every palette:

- declares both ``light`` and ``dark`` variants,
- supplies every one of the 15 tokens in each variant,
- uses only valid CSS colours (``#RRGGBB`` or ``rgba(...)``),
- has a unique id,
- has a name + a source URL,
- honours the Darcula logo blood-red requirement (dark accent ==
  ``#9d001e``).

The per-palette parametrisation is deliberate so failures name the
offender instead of reporting a vague "some palette is broken".
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PALETTE_TS = REPO_ROOT / "frontend" / "src" / "app" / "models" / "palette.model.ts"

REQUIRED_TOKENS = (
    "bgPrimary",
    "bgSecondary",
    "bgTertiary",
    "border",
    "textPrimary",
    "textSecondary",
    "accent",
    "accentHover",
    "contrast",
    "success",
    "danger",
    "warning",
    "info",
    "purple",
    "shadow",
)

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
RGBA_RE = re.compile(r"^rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*([0-9]*\.?[0-9]+)\s*\)$")


def _slice_palettes_array(text: str) -> str:
    """Return the raw text of the ``PALETTES`` array literal."""
    marker = "export const PALETTES: Palette[] = ["
    start = text.find(marker)
    if start == -1:
        raise AssertionError(f"PALETTES marker not found in {PALETTE_TS}")
    depth = 0
    i = start + len(marker) - 1  # position of the opening `[`
    assert text[i] == "["
    while i < len(text):
        ch = text[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start + len(marker) - 1 : i + 1]
        i += 1
    raise AssertionError("unterminated PALETTES array")


def _strip_comments(text: str) -> str:
    # Block comments `/* ... */`
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    # Line comments `// ...` — but NOT `://` inside string literals
    # (URLs). Only strip when the `//` appears outside single or
    # double-quoted strings.
    out = []
    i = 0
    n = len(text)
    in_single = False
    in_double = False
    while i < n:
        ch = text[i]
        if in_single:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue
        if ch == "'":
            in_single = True
            out.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            # skip to end of line
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _normalise_strings_and_keys(text: str) -> str:
    """Walk ``text`` and produce a JSON-friendly version:

    - Single-quoted strings become double-quoted (with internal
      double-quotes escaped, and internal single-quote escapes
      un-escaped).
    - Bare identifier keys (``id:``, ``light:``) become
      double-quoted keys.
    - Contents of strings are left untouched.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            # Pass double-quoted string through verbatim.
            j = i + 1
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            out.append(text[i:j])
            i = j
            continue
        if ch == "'":
            # Collect the single-quoted string, converting to a valid
            # JSON double-quoted string.
            j = i + 1
            buf: list[str] = []
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    # Pass through escape sequences, but drop `\'`
                    # (which is just an escaped single quote) and turn
                    # it into a bare apostrophe.
                    nxt = text[j + 1]
                    if nxt == "'":
                        buf.append("'")
                    else:
                        buf.append("\\" + nxt)
                    j += 2
                    continue
                if text[j] == "'":
                    j += 1
                    break
                buf.append(text[j])
                j += 1
            # Escape double quotes inside the new string.
            content = "".join(buf).replace("\\", "\\\\").replace('"', '\\"')
            # Undo the overly eager escaping of already-escaped
            # sequences: we only intended to escape raw backslashes
            # that had no following escape char. The earlier pass
            # preserved `\x` pairs as `\x` so the double-escape we
            # just did is fine for our palette payload which has no
            # backslashes. Keep it simple.
            out.append('"' + content + '"')
            i = j
            continue
        out.append(ch)
        i += 1
    stitched = "".join(out)

    # Quote bare identifier keys.
    stitched = re.sub(
        r"([{,\s])([A-Za-z_][A-Za-z0-9_]*)\s*:",
        r'\1"\2":',
        stitched,
    )
    # Drop trailing commas before ] or }.
    stitched = re.sub(r",(\s*[}\]])", r"\1", stitched)
    return stitched


def _ts_literal_to_python(text: str) -> Any:
    """Convert the palette array literal into a Python data structure.

    The TypeScript literal is close to JSON but uses:
    - unquoted identifier keys (``id:``, ``light:``, …),
    - single or double quoted strings,
    - trailing commas.

    Strategy: strip comments, normalise strings + bare keys, then
    ``json.loads``.
    """
    text = _strip_comments(text)
    normalised = _normalise_strings_and_keys(text)
    try:
        return json.loads(normalised)
    except Exception:
        return ast.literal_eval(normalised)


@pytest.fixture(scope="module")
def palettes() -> list[dict[str, Any]]:
    text = PALETTE_TS.read_text(encoding="utf-8")
    raw = _slice_palettes_array(text)
    data = _ts_literal_to_python(raw)
    assert isinstance(data, list), "PALETTES must parse to a list"
    return data


@pytest.fixture(scope="module")
def palette_ids(palettes: list[dict[str, Any]]) -> list[str]:
    return [p["id"] for p in palettes]


def _is_valid_css_colour(value: str) -> bool:
    if not isinstance(value, str):
        return False
    if HEX_RE.match(value):
        return True
    m = RGBA_RE.match(value)
    if not m:
        return False
    r, g, b = (int(m.group(i)) for i in (1, 2, 3))
    a = float(m.group(4))
    return all(0 <= c <= 255 for c in (r, g, b)) and 0 <= a <= 1


def test_source_file_present() -> None:
    assert PALETTE_TS.is_file(), PALETTE_TS


def test_default_palette_id_points_at_existing_palette(palette_ids: list[str]) -> None:
    text = PALETTE_TS.read_text(encoding="utf-8")
    m = re.search(r"export\s+const\s+DEFAULT_PALETTE_ID\s*=\s*['\"]([^'\"]+)['\"]", text)
    assert m, "DEFAULT_PALETTE_ID export not found"
    default_id = m.group(1)
    assert default_id in palette_ids, f"DEFAULT_PALETTE_ID={default_id!r} not in {palette_ids!r}"


def test_no_duplicate_palette_ids(palette_ids: list[str]) -> None:
    dupes = [p for p in palette_ids if palette_ids.count(p) > 1]
    assert not dupes, f"Duplicate palette ids: {sorted(set(dupes))}"


def test_darcula_accent_is_blood_red(palettes: list[dict[str, Any]]) -> None:
    darcula = next((p for p in palettes if p["id"] == "darcula"), None)
    assert darcula is not None, "Darcula palette must exist"
    assert darcula["dark"]["accent"].lower() == "#9d001e", darcula["dark"]["accent"]


def _get_palette_ids_for_param() -> list[str]:
    """Read palette ids eagerly so @pytest.mark.parametrize can name
    each palette as a sub-test. Falls back to an empty list if the TS
    file is unreadable — the test_source_file_present guard will flag
    the underlying problem."""
    try:
        text = PALETTE_TS.read_text(encoding="utf-8")
        raw = _slice_palettes_array(text)
        data = _ts_literal_to_python(raw)
        return [p["id"] for p in data]
    except Exception:
        return []


@pytest.mark.parametrize("palette_id", _get_palette_ids_for_param())
def test_palette_has_light_and_dark_with_all_valid_tokens(palette_id: str, palettes: list[dict[str, Any]]) -> None:
    p = next(x for x in palettes if x["id"] == palette_id)
    # Name + source sanity.
    assert p.get("name"), f"{palette_id}: missing name"
    assert p.get("source", "").startswith("http"), f"{palette_id}: missing/invalid source URL"

    for variant in ("light", "dark"):
        assert variant in p, f"{palette_id}: missing {variant} variant"
        tokens = p[variant]
        for key in REQUIRED_TOKENS:
            assert key in tokens, f"{palette_id}.{variant}: missing token {key!r}"
            value = tokens[key]
            assert _is_valid_css_colour(value), f"{palette_id}.{variant}.{key}={value!r} is not a valid CSS colour"
