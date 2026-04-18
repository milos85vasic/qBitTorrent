# Authoring a new nova3 search plugin

Build a fresh search plugin from scratch and wire it into the merge
service — without touching the constitution's canonical 12-plugin
roster.

## Audience

Python developers comfortable with basic HTTP parsing. You do **not**
need to know FastAPI or asyncio — nova3 plugins are synchronous and
isolated.

## Prerequisites

- Python 3.12+.
- A public tracker or test fixture you can query without auth. This
  course uses a synthetic `httpbin`-style endpoint so the demo runs
  offline-friendly.
- qBittorrent-Fixed already running (see `courses/01-operator/`).

## Runtime

Roughly **8 minutes**, including the py_compile sanity check and the
smoke test against the merge service.

## What you will learn

- The nova3 plugin contract: `url`, `name`,
  `supported_categories`, `search(query, category)`,
  `download_torrent(url)`.
- The `novaprinter.prettyPrinter.print()` interface and how the merge
  service parses its output.
- Why plugins live in a subprocess — isolation, timeouts, and why
  `sys.path` tricks are required.
- How to smoke-test your plugin with the merge service without
  promoting it to the canonical 12 (that needs a constitution
  amendment and a test round).

## Files

| File        | What it is                                          |
|-------------|-----------------------------------------------------|
| `script.md` | Narration with scene markers for voice-over.        |
| `demo.sh`   | Replayable scaffold + compile + install + smoke.    |
| `demo.cast` | Asciinema v2 recording (placeholder).               |

## Next

Once your plugin works, hand it to the contributor track
(`courses/03-contributor/`) to learn the TDD cadence for landing a
constitution amendment.
