# download-proxy/ — FastAPI Merge Service + Download Proxy

This directory contains the source code and Python requirements for the
`qbittorrent-proxy` container (image: `python:3.12-alpine`). The
container runs **two co-hosted services** inside one Python process,
each bound to a different port on the host network.

## Services

| Service | Port | Role |
|---|---|---|
| Download proxy | **7186** | HTTP shim that forwards qBittorrent WebUI API calls and intercepts tracker URLs that need authenticated cookies |
| Merge Search Service | **7187** | FastAPI + Uvicorn app that fans searches across every configured tracker, deduplicates results, enriches metadata, streams results over SSE, and serves the Angular dashboard + OpenAPI spec |

The third port referenced throughout the repo — **7188** — belongs to
`webui-bridge.py` on the host (not in this container). See
[`../webui-bridge.py`](../webui-bridge.py) and the constitution's
Private Tracker Bridge Pattern (Principle V).

## Entry point

`src/main.py` launches both services under the same Python process:

- `start_original_proxy()` — spawns a daemon thread that imports the
  legacy `download_proxy.run_server()` from
  `/config/qBittorrent/nova3/engines/download_proxy.py`.
- `start_fastapi_server()` — spawns a daemon thread that boots Uvicorn
  with `from api import app` on `MERGE_SERVICE_PORT` (default `7187`).
- The main thread sleeps in a `while True: time.sleep(60)` keep-alive;
  `KeyboardInterrupt` logs a shutdown and exits. **Graceful shutdown
  is tracked for Phase 3** — see [`../docs/CONCURRENCY.md`](../docs/CONCURRENCY.md).

## Directory layout

```
download-proxy/
├── README.md            # this file
├── requirements.txt     # runtime Python deps (installed by start-proxy.sh)
├── config/              # per-deployment config stubs, bind-mounted
└── src/
    ├── main.py          # dual-server entry point
    ├── api/             # FastAPI app (__init__.py), routes, auth, hooks,
    │                    #   streaming, scheduler
    ├── merge_service/   # search orchestrator, deduplicator, enricher,
    │                    #   validator, hook dispatcher, scheduler
    ├── ui/              # compiled Angular dashboard static assets
    └── config/          # env / credential loaders
```

Top-level counterparts:

- **`../plugins/`** — nova3 engines that the download proxy and merge
  service execute out-of-process via `asyncio.create_subprocess_exec`.
  The merge service interpolates the tracker name into a one-liner
  script and runs `python3 -c` inside the container (see
  `src/merge_service/search.py::_search_public_tracker`). In Phase 2
  this path converts to an in-process `ProcessPoolExecutor`.
- **`../webui-bridge.py`** — host process on port 7188 that handles
  authenticated downloads for the four private trackers
  (rutracker / kinozal / nnmclub / iptorrents).
- **`../docs/MAGNET_LINKS.md`** — how magnet URLs are generated.
- **`../docs/PLUGINS.md`** — canonical 12-plugin roster.

## Requirements

`requirements.txt` is intentionally tight:

```
requests>=2.31.0
urllib3>=2.0.0
fastapi>=0.110.0
uvicorn>=0.29.0
aiohttp>=3.9.0
pydantic>=2.0.0
Levenshtein>=0.21.0
```

`start-proxy.sh` (bind-mounted into the container at `/start-proxy.sh`)
installs these at container start. No `pip install -r` happens at build
time — the `python:3.12-alpine` image is used raw.

## Containerisation

There is **no `Dockerfile` in this directory**. The container is
described entirely in `../docker-compose.yml`:

- `image: python:3.12-alpine`
- `container_name: qbittorrent-proxy`
- `network_mode: host` (all ports on the host interface)
- Volumes:
  - `./config:/config` — shared with the qbittorrent container
  - `./download-proxy:/config/download-proxy` — bind-mount of this dir
  - `./tmp:/shared-tmp` — inter-container scratch (constitution I)
  - `./start-proxy.sh:/start-proxy.sh:ro` — entrypoint
- `depends_on: qbittorrent { condition: service_healthy }`
- Healthcheck: `curl -sf http://localhost:7186/`

Because the container bind-mounts `download-proxy/` instead of baking
it into an image, edits to `src/` are picked up on restart without a
rebuild. The CLAUDE.md REBUILD-REBOOT constraint still applies —
`__pycache__` must be deleted or stale bytecode will shadow new code.

## Relationship to plugins/

The merge service does **not** `import` plugins directly. It shells out
per-tracker via a generated Python one-liner that:

1. Prepends `/config/qBittorrent/nova3` to `sys.path`.
2. Replaces `novaprinter.prettyPrinter` with a capture closure.
3. Imports `engines.<tracker>` and calls `<tracker>().search(query, cat)`.
4. Serialises captured dicts as JSON on stdout.

This isolation lets a broken plugin crash its subprocess without killing
the merge service. See
[`../docs/architecture/plugin-execution.mmd`](../docs/architecture/plugin-execution.mmd)
for both the current and post-Phase-2 paths.

## Conventions

- **Python 3.12**, PEP 8, type hints on public methods.
- Keep `try: import novaprinter` optional-dependency blocks in every
  module that might be executed standalone for testing.
- `src/` is the only directory that gets loaded by `main.py`; do not
  put runtime code under `config/`.
- Configuration lives in environment variables, loaded with the layered
  priority defined in `CLAUDE.md`
  (shell → `.env` → `~/.qbit.env` → container env).

## Tests

- Unit tests — `../tests/unit/` (`test_routes.py`, `test_auth.py`,
  `test_streaming.py`, `test_merge_trackers.py`, and the full
  `merge_service/` subtree).
- Integration tests — `../tests/integration/` drive the container via
  the `merge_service_live` fixture.
- Benchmark — `../tests/benchmark/test_search_benchmark.py`,
  `test_deduplication_benchmark.py`.
- The merge service is **never** installed as a package; tests import
  using `importlib` mode. See `../tests/conftest.py`.

## Gotchas

- `MERGE_SERVICE_PORT` / `PROXY_PORT` are read from the environment;
  the compose file pins them to `7187` / `7186`. If you override the
  compose file, check that both ports are bound on the same interface
  (the code assumes host networking).
- Subprocess search has a hard 10-second timeout (`search.py:407`).
  Slow trackers simply return `[]` — the search result surfaces the
  error in `SearchMetadata.errors`.
- `CORSMiddleware` currently uses `allow_origins=["*"]`; this is tight
  down to a configurable allowlist in Phase 3. See
  [`../docs/SECURITY.md`](../docs/SECURITY.md).
- The FastAPI app pushes Angular static assets from `src/ui/dist/`.
  Rebuild the frontend (`cd ../frontend && ng build`) and restart the
  container to see UI changes.
