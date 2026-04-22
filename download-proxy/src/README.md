# download-proxy/src/

Merge Search Service source — FastAPI application, download proxy, and tracker orchestration.

## Entry Points

- **`main.py`** — Container entrypoint. Starts two daemon threads:
  1. Original download proxy (port 7186)
  2. FastAPI merge service (port 7187)
  Handles SIGTERM/SIGINT for graceful shutdown.

## Module Map

| Directory | Purpose |
|-----------|---------|
| `api/` | FastAPI routes, hooks, streaming, auth, scheduler |
| `merge_service/` | Core logic: search orchestration, dedup, enrichment, validation |
| `config/` | `EnvConfig` dataclass, env loading, credential scrubber |
| `ui/` | Jinja2 dashboard templates and static assets |

## Conventions

- **No comments** in source files — project convention per AGENTS.md.
- All config via environment variables (`config/__init__.py`).
- Async throughout (`asyncio`, `aiohttp`). No blocking calls in the event loop.
- Pydantic models for API request/response bodies; dataclasses for internal state.

## How to Test

```bash
# From repo root — tests live in ./tests/, not here
python3 -m pytest tests/unit/ -v --import-mode=importlib
python3 -m pytest tests/unit/merge_service/ -v --import-mode=importlib
```

Lint and typecheck:

```bash
ruff check download-proxy/src/
mypy download-proxy/src/
```
