# Coverage Baseline

This is the **zero point** for coverage across the project. Phase 5 of
the completion-initiative plan raises `fail_under` module-by-module
from the numbers below to 100 %. The baseline captures the state of
coverage at the start of that work.

## How to regenerate

```bash
# Full suite with coverage
pytest -v --import-mode=importlib \
       --cov=download-proxy/src --cov=plugins \
       --cov-report=term-missing \
       --cov-report=xml \
       --cov-report=html

# Report lives at coverage.xml (for SonarQube) + htmlcov/index.html
```

Configuration is in `pyproject.toml` under `[tool.coverage.run]` and
`[tool.coverage.report]`. Branch coverage is on.

Update this document by running the command above against the live
stack (all three services up via fixtures — see `tests/fixtures/services.py`)
and copying the module rows from the coverage report into the table
below.

## Baseline table (measured 2026-04-19 against commit 1adb91b)

Numbers from `python3 -m pytest tests/unit tests/e2e tests/contract --cov=...`
running against the live stack after Phase-3 deployment. Integration /
benchmark / security / stress suites contribute further coverage but
are not part of the default gate (they need live network access).

| Package | Lines | Branches | Notes |
|---|---:|---:|---|
| `download-proxy/src/config/` | **100 %** | **100 %** | Tiny config loader |
| `download-proxy/src/merge_service/` | **77 %** | **63 %** | Orchestrator + parsers + validator |
| `download-proxy/src/api/` | **51 %** | **37 %** | Routes + auth + streaming + hooks + scheduler |
| `plugins/*.py` (root) | **1 %** | **0 %** | Only tested indirectly via merge_service |
| **TOTAL** (incl. plugins) | **23 %** | **~4 %** | Pulled down by 44 plugin files |

Per-file rows are in the HTML report (`htmlcov/index.html`) — the
package-level numbers above are the ones the gate is raised against.

## Per-phase coverage gates

The completion-initiative plan raises `fail_under` in the sequence:

1. **Phase 0** (now) — `fail_under = 0`, baseline captured.
2. **Phase 2** — `fail_under = 60` for `download-proxy/src/api/`.
3. **Phase 3** — `fail_under = 80` for `download-proxy/src/merge_service/`.
4. **Phase 4** — `fail_under = 80` for canonical plugins.
5. **Phase 5** — `fail_under = 100` everywhere except the 36
   community plugins (which stay at `0` until a user opts in to them
   via `install-plugin.sh`).

The gate is enforced by `pytest-cov`; a regression below the current
gate fails CI (`.github/workflows/unit.yml`).

## Gotchas

- `plugins/socks.py` has an intentional `NotImplementedError` in the
  UDP-fragmentation branch. That line will never be covered and is
  excluded via a `# pragma: no cover` comment (or will be once Phase 4
  cleans up plugin coverage).
- `plugins/nova2.py` is an abstract base — the `NotImplementedError`
  stubs are intentional. Exclude with `# pragma: no cover`.
- `download-proxy/src/ui/__init__.py` is empty; coverage will show
  100 % trivially.
- The orchestrator's private-tracker `_search_*` methods hit live
  endpoints; coverage for them requires either recorded fixtures
  (vcrpy, Phase 4) or the `@pytest.mark.requires_credentials` gate
  with real credentials.
- Community plugins are excluded from the default coverage target
  because they have no tests yet. Including them would dilute the
  score without reflecting real test work. They will be graded
  separately once Phase 4 scaffolds their tests.

## Related documents

- [`TESTING.md`](TESTING.md) — where each test type lives.
- [`../pyproject.toml`](../pyproject.toml) — coverage config.
- [`superpowers/plans/2026-04-19-completion-initiative.md`](superpowers/plans/2026-04-19-completion-initiative.md)
  — Phase 5 is the authoritative source for the gate progression.
