"""Regression guards for the anilibra + yourbittorrent plugin crashes.

* anilibra: upstream occasionally returns ``{"data": null}`` which made
  ``for item in data['data']`` raise ``TypeError: 'NoneType' object is
  not iterable``. The plugin now short-circuits to 0 results instead.

* yourbittorrent: the plugin's first regex was
  ``re.findall(...)[1]`` — when the site HTML rotated (current state
  of 2026-04-19 serves an auth wall to anonymous visitors), the
  findall came back with fewer than 2 matches and raised
  IndexError. Now returns [] quietly.

Both are plugins we pull from ``plugins/`` and install into the nova3
engines dir, so the guard lives in the source of truth here.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGINS = REPO / "plugins"


def _load_plugin(name: str):
    """Import a plugin file outside the nova3 harness.

    Plugins do `from novaprinter import prettyPrinter` and
    `from helpers import retrieve_url`. We install lightweight stub
    modules before import so the plugin loads cleanly.
    """
    # Stub novaprinter
    captured: list[dict] = []

    np_mod = types.ModuleType("novaprinter")
    np_mod.prettyPrinter = lambda d: captured.append(d)  # type: ignore[attr-defined]

    class _SR:
        pass

    np_mod.SearchResults = _SR  # type: ignore[attr-defined]

    sys.modules["novaprinter"] = np_mod

    # Stub helpers.retrieve_url (plugins import it at module load time
    # so we have to provide something, even if we intercept it later).
    helpers_mod = types.ModuleType("helpers")
    helpers_mod.retrieve_url = lambda url: ""  # type: ignore[attr-defined]
    helpers_mod.download_file = lambda url: url  # type: ignore[attr-defined]
    sys.modules["helpers"] = helpers_mod

    spec = importlib.util.spec_from_file_location(f"plugin_{name}", PLUGINS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod, captured


def test_anilibra_handles_data_null_upstream_response() -> None:
    """Upstream returning ``{"data": null}`` must NOT crash."""
    mod, captured = _load_plugin("anilibra")
    cls = getattr(mod, "anilibra")
    instance = cls()

    with patch.object(
        sys.modules["helpers"], "retrieve_url", return_value='{"data": null}'
    ):
        instance.search("linux")
    assert captured == [], "no rows should be captured for a null data response"


def test_anilibra_handles_completely_missing_data_key() -> None:
    mod, captured = _load_plugin("anilibra")
    cls = getattr(mod, "anilibra")
    instance = cls()
    with patch.object(
        sys.modules["helpers"], "retrieve_url", return_value='{"meta": "no data here"}'
    ):
        instance.search("linux")
    assert captured == []


def test_anilibra_handles_non_dict_upstream_response() -> None:
    mod, captured = _load_plugin("anilibra")
    cls = getattr(mod, "anilibra")
    instance = cls()
    with patch.object(
        sys.modules["helpers"], "retrieve_url", return_value='["unexpected", "array"]'
    ):
        instance.search("linux")
    assert captured == []


def test_yourbittorrent_handles_missing_results_table() -> None:
    """When the site's `<div class="table-responsive">` wrapper is
    missing (auth wall, rotated HTML), the plugin used to raise
    IndexError. Now it must return [] cleanly.
    """
    mod, captured = _load_plugin("yourbittorrent")
    cls = getattr(mod, "yourbittorrent")
    instance = cls()
    # The auth-wall response: only ONE table-responsive wrapper on the
    # login page, never a second one for the results.
    auth_wall_html = (
        "<html><body>"
        '<div class="table-responsive">'
        "<table><tr><td>Please log in</td></tr></table>"
        "</div>"
        "</body></html>"
    )
    with patch.object(
        sys.modules["helpers"], "retrieve_url", return_value=auth_wall_html
    ):
        instance.search("linux")
    assert captured == [], "auth-wall HTML should yield 0 rows without crashing"


def test_yourbittorrent_handles_html_with_no_tables_at_all() -> None:
    """Complete garbage / empty response — no IndexError."""
    mod, captured = _load_plugin("yourbittorrent")
    cls = getattr(mod, "yourbittorrent")
    instance = cls()
    with patch.object(sys.modules["helpers"], "retrieve_url", return_value=""):
        instance.search("linux")
    assert captured == []
