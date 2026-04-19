"""Regression guards for the public-tracker subprocess capture.

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
        "Capture must flush after each row so a subprocess kill at timeout "
        "preserves partial results."
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
