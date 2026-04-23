"""
The qBittorrent WebUI theme bridge lives in ``plugins/download_proxy.py``
and runs inside the ``qbittorrent-proxy`` container. It cannot import
the TypeScript palette catalogue at runtime, so the catalog is
mirrored as a Python dict.

This guard-test parses the authoritative TS file and asserts that the
Python copy has the same ids, the same tokens, and the same values in
each token, for both light and dark variants. If they drift, the two
ports will render slightly different colours — so we fail loudly here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_PATH = REPO_ROOT / "plugins" / "download_proxy.py"
PALETTE_TS = REPO_ROOT / "frontend" / "src" / "app" / "models" / "palette.model.ts"


def _load_ts_palettes() -> dict[str, dict[str, dict[str, str]]]:
    # Reuse the TS parser from test_palette_catalog.py.
    spec = importlib.util.spec_from_file_location(
        "palette_catalog_parser_mirror",
        Path(__file__).resolve().parent / "test_palette_catalog.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["palette_catalog_parser_mirror"] = mod
    spec.loader.exec_module(mod)

    text = PALETTE_TS.read_text(encoding="utf-8")
    raw = mod._slice_palettes_array(text)
    data = mod._ts_literal_to_python(raw)
    return {p["id"]: {"dark": p["dark"], "light": p["light"]} for p in data}


def _load_python_palettes() -> dict[str, dict[str, dict[str, str]]]:
    spec = importlib.util.spec_from_file_location("download_proxy_mirror", PLUGIN_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["download_proxy_mirror"] = mod
    spec.loader.exec_module(mod)
    return mod.THEME_PALETTES


def test_python_mirror_has_same_palette_ids():
    ts = _load_ts_palettes()
    py = _load_python_palettes()
    assert set(py.keys()) == set(ts.keys()), (
        f"Palette id drift — TS has {sorted(ts.keys())}, Python has {sorted(py.keys())}"
    )


@pytest.mark.parametrize(
    "palette_id",
    [
        "darcula",
        "dracula",
        "solarized",
        "nord",
        "monokai",
        "gruvbox",
        "one-dark",
        "tokyo-night",
    ],
)
def test_python_mirror_tokens_match_ts(palette_id):
    ts = _load_ts_palettes()
    py = _load_python_palettes()
    assert palette_id in ts, f"TS catalogue missing {palette_id}"
    assert palette_id in py, f"Python mirror missing {palette_id}"
    for mode in ("light", "dark"):
        assert py[palette_id][mode] == ts[palette_id][mode], (
            f"{palette_id}/{mode} drifted:\n  TS: {ts[palette_id][mode]}\n  Py: {py[palette_id][mode]}"
        )
