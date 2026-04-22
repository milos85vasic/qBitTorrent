# Coverage Baseline

Captured at commit `0d2b86d` on 2026-04-22.

## Summary

| Metric | Value |
|--------|-------|
| **Total line coverage** | **27%** |
| **Total statements** | 7,645 |
| **Missing lines** | 5,523 |
| **Unit tests passing** | 823 |

## By Module — Core (download-proxy/src)

| Module | Stmts | Miss | Branch | Cover |
|--------|-------|------|--------|-------|
| `api/__init__.py` | 119 | 40 | 24 | 60% |
| `api/auth.py` | 203 | 154 | 50 | 21% |
| `api/hooks.py` | 107 | 59 | 14 | 40% |
| `api/routes.py` | 446 | 235 | 126 | 44% |
| `api/scheduler.py` | 59 | 2 | 14 | 92% |
| `api/streaming.py` | 115 | 9 | 40 | 93% |
| `api/theme_state.py` | 100 | 19 | 12 | 81% |
| `config/__init__.py` | 49 | 1 | 2 | 96% |
| `main.py` | 48 | 24 | 4 | 46% |
| `merge_service/deduplicator.py` | 240 | 23 | 118 | 89% |
| `merge_service/enricher.py` | 166 | 10 | 62 | 91% |
| `merge_service/hooks.py` | 106 | 42 | 26 | 53% |
| `merge_service/scheduler.py` | 125 | 27 | 20 | 74% |
| `merge_service/search.py` | 773 | 189 | 228 | 72% |
| `merge_service/validator.py` | 202 | 73 | 58 | 61% |

## By Module — Plugins (plugins/)

Most plugins have **0% coverage**. Only a few have test coverage:

| Plugin | Stmts | Miss | Cover |
|--------|-------|------|-------|
| `download_proxy.py` | 278 | 163 | 40% |
| `anilibra.py` | 56 | 32 | 35% |
| `yourbittorrent.py` | 47 | 15 | 58% |
| All others (42 plugins) | — | — | **0%** |

## Coverage Target Roadmap

Per the completion initiative plan, `fail_under` starts at 1% and is raised each phase:

- Phase 0: 1% (baseline)
- Phase 1: 15%
- Phase 2: 30%
- Phase 3: 45%
- Phase 4: 60%
- Phase 5: 75%
- Phase 6: 90%
- Phase 7: 95%
- Phase 8: 100%

## Measurement Method

```bash
python3 -m pytest tests/unit/ --import-mode=importlib \
  --cov=download-proxy/src --cov=plugins \
  --cov-report=term-missing --cov-report=xml
```

Unit tests only (integration/e2e tests require running containers and are not included in baseline).
