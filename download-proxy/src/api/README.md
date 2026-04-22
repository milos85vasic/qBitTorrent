# download-proxy/src/api/

FastAPI application layer — routes, hooks, SSE streaming, auth, and scheduler endpoints.

## Entry Points

- **`__init__.py`** — Creates the FastAPI `app` instance, mounts CORS middleware, includes all routers.
- **`routes.py`** — Primary search/download/magnet/stats endpoints under `/api/v1/`.
- **`streaming.py`** — SSE endpoint `GET /api/v1/search/stream/{id}` for live result streaming.
- **`hooks.py`** — CRUD endpoints for webhook-style hooks (`/api/v1/hooks`).
- **`auth.py`** — Tracker login (username/password, cookie, CAPTCHA) and credential management.
- **`scheduler.py`** — Scheduled search CRUD (`/api/v1/schedules`).
- **`theme_state.py`** — Shared theme injection state for cross-app dark mode.

## API Endpoints

| Method | Path | Handler |
|--------|------|---------|
| POST | `/api/v1/search` | `routes.py` — multi-tracker search |
| GET | `/api/v1/search/stream/{id}` | `streaming.py` — SSE results |
| POST | `/api/v1/download` | `routes.py` — proxied download |
| POST | `/api/v1/magnet` | `routes.py` — magnet generation |
| GET | `/api/v1/downloads/active` | `routes.py` — active torrents |
| GET/POST/DELETE | `/api/v1/hooks` | `hooks.py` |
| POST | `/api/v1/tracker/login` | `auth.py` |
| GET/POST/PUT/DELETE | `/api/v1/schedules` | `scheduler.py` |
| GET | `/health` | `routes.py` |
| GET | `/api/v1/stats` | `routes.py` |

## Conventions

- Pydantic `BaseModel` for all request/response bodies.
- Auth via qBittorrent session cookie (forwarded to `:7185`).
- `ALLOWED_ORIGINS` env var drives CORS — no wildcards in production.
- No source code comments (project convention).

## How to Test

```bash
python3 -m pytest tests/unit/api_layer/ -v --import-mode=importlib
python3 -m pytest tests/contract/ -v --import-mode=importlib
python3 -m pytest tests/unit/ -k "api" -v --import-mode=importlib
```
