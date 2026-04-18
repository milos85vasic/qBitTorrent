# tools/ — Developer Tooling

Standalone developer scripts that do **not** run inside a container
and are not invoked by the normal start/stop flow. Each script here
is independently runnable from a host Python 3.12.

## Scripts

| Script | What it does |
|---|---|
| `plugin_update_automation.py` | Checks upstream repositories for newer versions of each plugin in `plugins/`, optionally downloads + validates + backs up + installs them, and produces an update report. Supports `--check`, `--update`, and `--dry-run`. |

### `plugin_update_automation.py`

Usage:

```bash
# Check without mutating anything
python3 tools/plugin_update_automation.py --check

# Update plugins in place (creates backups under plugins/.backups/)
python3 tools/plugin_update_automation.py --update

# Preview updates without writing anything
python3 tools/plugin_update_automation.py --update --dry-run
```

The script validates each downloaded plugin with `python3 -m py_compile`
before installing it (constitution Principle II). If validation fails
the backup is restored. Reports are written to stdout in JSON so the
tool can be chained into CI later.

## Adding a new tool

1. Drop a standalone Python 3.12 script in this directory.
2. Shebang (`#!/usr/bin/env python3`) and a docstring describing the
   intended invocation at the top.
3. No external dependencies beyond `requirements.txt` — any extra
   library must be added to `download-proxy/requirements.txt` so the
   container can share it.
4. Add a row to the table above.
5. If the tool is worth running in CI, wire it into the appropriate
   workflow under `.github/workflows/`.

## Conventions

- Pure Python 3.12 — no shell wrappers in this directory (those live
  at the repo root: `start.sh`, `stop.sh`, `setup.sh`, `ci.sh`).
- No network calls during import; network only happens inside `main()`
  so the script is safe to import for unit testing.
- Logging uses the standard `logging` module; scripts write to stderr,
  reports to stdout.

## Tests

- `tools/` has no dedicated test suite. If a tool becomes load-bearing,
  add tests under `tests/unit/` that import it directly.

## Gotchas

- Scripts here run on the **host**, so they see the host's Python,
  not the container's. Beware version drift.
- `plugin_update_automation.py` hits upstream URLs; run with care on
  metered connections and respect the retry budget inside the script.
- `__pycache__` in this directory is gitignored but will be recreated
  on every run — delete it manually if a stale import surfaces.
