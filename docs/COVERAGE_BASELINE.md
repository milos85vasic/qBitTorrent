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

## Baseline table

Cells are `pending` until someone runs the command above and commits
the results. Do not fabricate numbers — a real measurement against the
current `main` is the only valid way to populate this table.

| Module | Lines | Branches | Notes |
|---|---|---|---|
| `download-proxy/src/main.py` | pending | pending | Entry point; low-value for coverage |
| `download-proxy/src/api/__init__.py` | pending | pending | App factory |
| `download-proxy/src/api/routes.py` | pending | pending | REST endpoints |
| `download-proxy/src/api/streaming.py` | pending | pending | SSE generator |
| `download-proxy/src/api/hooks.py` | pending | pending | Hook CRUD |
| `download-proxy/src/api/auth.py` | pending | pending | CAPTCHA flow |
| `download-proxy/src/api/scheduler.py` | pending | pending | Schedule CRUD |
| `download-proxy/src/merge_service/search.py` | pending | pending | Orchestrator + parsers |
| `download-proxy/src/merge_service/deduplicator.py` | pending | pending | Tiered matcher |
| `download-proxy/src/merge_service/enricher.py` | pending | pending | Metadata enrichment |
| `download-proxy/src/merge_service/validator.py` | pending | pending | BEP 48 / BEP 15 scrape |
| `download-proxy/src/merge_service/hooks.py` | pending | pending | Hook dispatcher |
| `download-proxy/src/merge_service/scheduler.py` | pending | pending | Scheduled searches |
| `plugins/eztv.py` | pending | pending | Canonical |
| `plugins/jackett.py` | pending | pending | Canonical |
| `plugins/limetorrents.py` | pending | pending | Canonical |
| `plugins/piratebay.py` | pending | pending | Canonical |
| `plugins/solidtorrents.py` | pending | pending | Canonical |
| `plugins/torlock.py` | pending | pending | Canonical |
| `plugins/torrentproject.py` | pending | pending | Canonical |
| `plugins/torrentscsv.py` | pending | pending | Canonical |
| `plugins/rutracker.py` | pending | pending | Canonical — private |
| `plugins/rutor.py` | pending | pending | Canonical |
| `plugins/kinozal.py` | pending | pending | Canonical — private |
| `plugins/nnmclub.py` | pending | pending | Canonical — private |
| `plugins/*.py` (36 community plugins) | pending | pending | Phase 4 — out of coverage scope today |

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
