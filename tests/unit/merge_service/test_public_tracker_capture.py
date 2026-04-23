"""Regression guards for the public-tracker subprocess capture
and the stderr classifier that surfaces failure reasons in
TrackerSearchStat.

Context
-------
Prior to 2026-04-19, `_search_public_tracker` in
`download-proxy/src/merge_service/search.py` monkeypatched
`engines.novaprinter.prettyPrinter` but every nova3 plugin does
`from novaprinter import prettyPrinter` against the TOP-LEVEL module at
`/config/qBittorrent/nova3/novaprinter.py`. Python's `from X import Y`
binds `Y` at import time to whatever `X.Y` is then; patching a different
module object leaves the plugin's binding untouched. Plugins therefore
printed pipe-delimited text to stdout while the orchestrator tried to
`json.loads` it, silently dropping every result from 37 of 40 trackers.

Second bug (same file): subprocess results were only flushed to stdout
by a final `print(_json.dumps(_results))` at the end of the script.
Long-running plugins hit the 10 s wait_for timeout and every captured
row was discarded, because `asyncio.wait_for(proc.communicate())`
throws away accumulated stdout on cancellation.

This file guards BOTH regressions:

1.  `test_script_patches_top_level_novaprinter` — the generated script
    targets the top-level `novaprinter` module, not `engines.novaprinter`.
2.  `test_script_streams_ndjson_not_batched` — capture writes each row
    as a JSON line with `sys.stdout.flush()`, so a timeout preserves
    partial results.
3.  `test_subprocess_captures_from_fake_plugin` — end-to-end exercise of
    the same script pattern against a fake nova3 tree in a tmpdir,
    asserting every `prettyPrinter(...)` call appears in the parent's
    streamed stdout.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SEARCH_PY = REPO / "download-proxy" / "src" / "merge_service" / "search.py"


@pytest.fixture(scope="module")
def search_source() -> str:
    return SEARCH_PY.read_text(encoding="utf-8")


def _extract_subprocess_script(source: str) -> str:
    """Pull the subprocess script string out of `_search_public_tracker`."""
    m = re.search(
        r"async def _search_public_tracker\b.*?(?=\n    async def |\nclass |\Z)",
        source,
        re.DOTALL,
    )
    assert m, "Could not locate _search_public_tracker in search.py"
    return m.group(0)


def test_script_patches_top_level_novaprinter(search_source: str) -> None:
    body = _extract_subprocess_script(search_source)
    assert "import novaprinter as _np" in body, (
        "Public-tracker subprocess must patch the TOP-LEVEL `novaprinter` "
        "module — plugins use `from novaprinter import prettyPrinter` and "
        "patching `engines.novaprinter` is the 37-empty-trackers bug."
    )
    assert "import engines.novaprinter as _np" not in body, (
        "Regression: the subprocess is patching `engines.novaprinter` again. "
        "Plugins import from the top-level `novaprinter` module — patching "
        "the wrong one leaves their `prettyPrinter` binding untouched and "
        "results print to stdout as pipe-delimited text, breaking JSON "
        "capture."
    )


def test_script_streams_ndjson_not_batched(search_source: str) -> None:
    body = _extract_subprocess_script(search_source)
    assert "sys.stdout.flush()" in body, (
        "Capture must flush after each row so a subprocess kill at timeout preserves partial results."
    )
    assert "_json.dumps(d)" in body, "Capture should emit NDJSON per row"
    assert "print(_json.dumps(_results))" not in body, (
        "Regression: batched-at-end dump is back. Earlier runs dropped EVERY "
        "row when the subprocess hit `asyncio.wait_for` cancellation because "
        "`communicate()` discards buffered stdout when the awaitable is "
        "cancelled. Stream each row with a flush instead."
    )


def test_subprocess_captures_from_fake_plugin(tmp_path: Path) -> None:
    """Reconstruct the production subprocess pattern against a fake nova3.

    This proves the monkeypatch+NDJSON contract end-to-end without
    needing the real container: a fake top-level `novaprinter` module, a
    fake plugin that does `from novaprinter import prettyPrinter`, and a
    sequence of calls that should all appear on the parent's stdout.
    """
    nova3 = tmp_path / "nova3"
    engines = nova3 / "engines"
    engines.mkdir(parents=True)

    (nova3 / "novaprinter.py").write_text(
        textwrap.dedent(
            """
            def prettyPrinter(d):
                import sys
                sys.stdout.write('|'.join(f'{k}={v}' for k, v in d.items()) + '\\n')
            """
        ),
        encoding="utf-8",
    )
    (engines / "__init__.py").write_text("", encoding="utf-8")
    (engines / "fakeplug.py").write_text(
        textwrap.dedent(
            """
            from novaprinter import prettyPrinter


            class fakeplug:
                url = "https://example.invalid"
                name = "FakePlug"
                supported_categories = {"all": "all"}

                def search(self, query, cat="all"):
                    for i in range(3):
                        prettyPrinter({
                            "name": f"{query}-{i}",
                            "size": "1 GB",
                            "seeds": i,
                            "leech": i,
                            "link": f"magnet:?xt=urn:btih:fake{i}",
                            "desc_link": f"https://example.invalid/{i}",
                            "engine_url": self.url,
                        })
            """
        ),
        encoding="utf-8",
    )

    tracker_name = "fakeplug"
    query = "linux"
    category = "all"
    nova3_str = str(nova3)
    script = (
        "import sys, os, json as _json\n"
        f"sys.path.insert(0, {nova3_str!r})\n"
        f"os.chdir({nova3_str!r})\n"
        "import importlib\n"
        "try:\n"
        "    import novaprinter as _np\n"
        "    def _capture(d):\n"
        "        sys.stdout.write(_json.dumps(d) + '\\n')\n"
        "        sys.stdout.flush()\n"
        "    _np.prettyPrinter = _capture\n"
        f"    _mod = importlib.import_module('engines.{tracker_name}')\n"
        f"    _cls = getattr(_mod, '{tracker_name}')\n"
        "    _engine = _cls()\n"
        f"    _engine.search({query!r}, {category!r})\n"
        "except Exception as _e:\n"
        "    print(_json.dumps({'__error__': str(_e)}), file=sys.stderr)\n"
    )

    async def _run() -> tuple[list[dict], str]:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        rows = []
        for line in stdout.decode().splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows, stderr.decode()

    rows, stderr = asyncio.run(_run())
    assert rows, (
        f"No NDJSON rows captured — the monkeypatch failed to route "
        f"`prettyPrinter` through `_capture`. stderr={stderr!r}"
    )
    assert len(rows) == 3, f"expected 3 rows, got {len(rows)}: {rows}"
    names = [r["name"] for r in rows]
    assert names == ["linux-0", "linux-1", "linux-2"], names


# --- classifier tests -------------------------------------------------------
# `_classify_plugin_stderr` takes raw subprocess stderr and maps it to the
# structured `{error_type, error, stderr_tail}` triple that the orchestrator
# writes into TrackerSearchStat. Before this helper, every empty tracker
# showed `error: None`, hiding upstream 403s/404s/DNS failures/plugin
# crashes behind a generic `[empty]` chip. These tests pin each class of
# failure so a future refactor can't silently drop the signal.

import importlib.util as _importlib_util

_MS_PATH = str(REPO / "download-proxy" / "src" / "merge_service")
sys.modules.setdefault("merge_service", type(sys)("merge_service"))
sys.modules["merge_service"].__path__ = [_MS_PATH]  # type: ignore[attr-defined]
_search_spec = _importlib_util.spec_from_file_location("merge_service.search", str(Path(_MS_PATH) / "search.py"))
_search_mod = _importlib_util.module_from_spec(_search_spec)
sys.modules["merge_service.search"] = _search_mod
_search_spec.loader.exec_module(_search_mod)  # type: ignore[union-attr]
_classify_plugin_stderr = _search_mod._classify_plugin_stderr


@pytest.mark.parametrize(
    "stderr,killed,had_results,expected_type",
    [
        ("", False, False, None),
        ("", True, False, "deadline_timeout"),
        ("", True, True, None),  # deadline fired but we already have rows
        ("Connection error: Forbidden\n", False, False, "upstream_http_403"),
        ("HTTP Error 403: Forbidden\n", False, False, "upstream_http_403"),
        ("Connection error: Not Found\n", False, False, "upstream_http_404"),
        ("Connection error: Gateway Timeout\n", False, False, "upstream_timeout"),
        ("Connection error: [Errno -2] Name does not resolve\n", False, False, "dns_failure"),
        ("Connection error: [Errno -5] Name has no usable address\n", False, False, "dns_failure"),
        ("SSL: TLSV1_ALERT_INTERNAL_ERROR\n", False, False, "tls_failure"),
        ("FileNotFoundError: [Errno 2]\n", False, False, "plugin_env_missing"),
        ("IndexError: list index out of range\n", False, False, "plugin_parse_failure"),
        ("'NoneType' object is not iterable\n", False, False, "plugin_crashed"),
        ("json.decoder.JSONDecodeError: ...\n", False, False, "plugin_parse_failure"),
        ("IncompleteRead(56503 bytes read)\n", False, False, "upstream_incomplete"),
        ('{"__done__": 0}\n', False, False, None),
    ],
)
def test_classifier_cases(stderr, killed, had_results, expected_type) -> None:
    got = _classify_plugin_stderr(stderr, killed_by_deadline=killed, had_results=had_results)
    assert got["error_type"] == expected_type, (
        f"stderr={stderr!r} killed={killed} had_results={had_results} "
        f"→ expected {expected_type!r}, got {got['error_type']!r}"
    )
    if expected_type is None:
        assert got["error"] is None
    else:
        assert isinstance(got["error"], str) and got["error"]


def test_classifier_truncates_long_stderr() -> None:
    """Long stderr must be truncated so a misbehaving plugin can't
    explode TrackerSearchStat.notes into the database/SSE feed."""
    huge = "Connection error: Forbidden\n" + "x" * 5000
    got = _classify_plugin_stderr(huge, killed_by_deadline=False, had_results=False)
    assert len(got["stderr_tail"]) <= 400
    # Still classified correctly despite the long tail.
    assert got["error_type"] == "upstream_http_403"
