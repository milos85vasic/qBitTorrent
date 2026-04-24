# qBitTorrent Platform — Consolidated Constitution

> This document consolidates ALL constitutional constraints from
> `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md`, and
> `docs/CONSTITUTION_ADDENDUM_QUALITY.md`. It is the canonical
> reference for AI agents and contributors.
>
> For the formal ratified document with amendment history, see
> `.specify/memory/constitution.md`.

---

## Table of Principles

| # | Principle | Violation Severity |
|---|-----------|-------------------|
| I | Container-First Architecture | Blocking |
| II | Plugin Contract Integrity | Blocking |
| III | Credential & Secret Security | Blocking |
| IV | Container Runtime Portability | Blocking |
| V | Private Tracker Bridge Pattern | Blocking |
| VI | Validation-Driven Development | Blocking |
| VII | Operational Simplicity | Warning |
| VIII | IPTorrents Freeleech Policy | Blocking |
| IX | Test-Driven Development | Blocking |
| X | Hermetic Test Discipline | Blocking |
| XI | Minimal Source Commentary | Blocking |

---

## I. Container-First Architecture

- Two containers only: `qbittorrent` + `qbittorrent-proxy`.
- Optional host process: `webui-bridge.py` on port 7188.
- `network_mode: host` for both containers.
- `config/` is the runtime config source of truth; MUST NOT contain secrets.
- Quality stack (`docker-compose.quality.yml`) is additive and opt-in only.

## II. Plugin Contract Integrity

- Plugin class MUST define: `url`, `name`, `supported_categories`, `search()`, `download_torrent()`.
- Output exclusively via `novaprinter.print()`.
- Private trackers use env vars; `try: import novaprinter` pattern for standalone testability.
- Syntax validation with `python3 -m py_compile` before install.
- Source of truth for plugins is `plugins/X.py`, NOT `config/qBittorrent/nova3/engines/X.py`.
- Managed list: `eztv jackett limetorrents piratebay solidtorrents torlock torrentproject torrentscsv rutracker rutor kinozal nnmclub`.

## III. Credential & Secret Security

- `.env` is gitignored and MUST NEVER be committed.
- Env priority: shell → `./.env` → `~/.qbit.env` → container env.
- WebUI credentials `admin`/`admin` are hardcoded — do NOT change.
- No secrets in logs, test reports, or commit messages.
- `.env` permissions MUST be `600`.

## IV. Container Runtime Portability

- Auto-detect: `podman` preferred, `docker` fallback.
- Compose command: `podman-compose` → `docker compose` → `docker-compose`.
- Use `detect_container_runtime()` pattern in all scripts.
- `podman unshare cp` for rootless volume copies.

## V. Private Tracker Bridge Pattern

- `webui-bridge.py` on port 7188 bridges private tracker auth.
- Direct WebUI downloads WILL fail for private trackers.
- `PRIVATE_TRACKERS` dict in `webui-bridge.py` MUST stay in sync with plugins.
- `plugins/webui_compatible/` are fallback variants.

## VI. Validation-Driven Development

- Bash scripts: `bash -n` syntax check.
- Python files: `python3 -m py_compile` syntax check.
- `./test.sh --quick` before every commit.
- `./run-all-tests.sh` before every release.
- `./install-plugin.sh --verify` before every release.

## VII. Operational Simplicity

- `setup.sh` — one-time onboarding.
- `start.sh` / `stop.sh` — lifecycle with flags.
- All scripts use shared color-print helpers and `-h/--help`.
- Data dirs (`Incomplete/`, `Torrents/All/`, `Torrents/Completed/`) auto-created.

## VIII. IPTorrents Freeleech Policy

- Automated tests MUST ONLY download freeleech torrents from IPTorrents.
- Freeleech results tagged `IPTorrents [free]` in `tracker_display`.
- Non-freeleech downloads cost ratio and MUST NEVER be automated.
- `freeleech` boolean field MUST be present and accurate.

## IX. Test-Driven Development

**TDD is MANDATORY for all bug fixes and features.**

1. Write failing test first (RED).
2. Watch it fail.
3. Write minimal code to pass (GREEN).
4. Verify full suite passes.
5. Then commit.

This is the primary defence against "green tests, broken product".

## X. Hermetic Test Discipline

- Tests live in `./tests/`, NEVER in `download-proxy/tests/`.
- Unit tests are heavily mocked and require NO running containers.
- Integration/E2E tests fail loudly (not skip) when services are down.
- Coverage gate: **49%** — maintained or raised with `docs/COVERAGE_BASELINE.md` update.
- `sys.modules` isolation MUST NOT leak from unit tests into integration/E2E.
- Event loop state MUST NOT leak between tests.
- pytest config: `asyncio_mode = "auto"`, `asyncio_default_test_loop_scope = "function"`.

## XI. Minimal Source Commentary

- **NO comments or docstrings** in `download-proxy/src/` merge service source.
- Code must be self-explanatory.
- "Why" belongs in commit messages or `docs/`, not source.
- Type hints on public methods are encouraged.
- Test files, plugins, scripts, and docs are exempt.

---

## Critical Operational Constraints

### Restart Levels (verified 2026-04-19)

| What changed | Restart action | Verification |
|-------------|----------------|-------------|
| `download-proxy/src/` or `merge_service/*.py` | `podman exec qbittorrent-proxy find /config/download-proxy -name __pycache__ -type d -exec rm -rf {} + && podman restart qbittorrent-proxy` | `curl` endpoint or `podman exec ... cat /config/...` |
| `plugins/*.py` | `./install-plugin.sh <name> && podman restart qbittorrent-proxy` | Same as above |
| `docker-compose.yml`, env vars, base image | `podman compose down && podman compose up -d` | Full recreate |

### CI Is Manual — Permanent

- `./ci.sh` is the ONLY canonical CI path.
- `.github/workflows/*.yml` MUST use `workflow_dispatch` ONLY.
- NEVER add push/PR/schedule triggers.
- This rule overrides anything an automated contributor might propose.

### Port Map

| Port | Service |
|------|---------|
| 7185 | qBittorrent WebUI (container-internal) |
| 7186 | Download proxy → qBittorrent |
| 7187 | Merge Search Service (FastAPI / Go/Gin) + Angular SPA |
| 7188 | webui-bridge (host process) |

### Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Python | CPython | >=3.12 (target 3.12, CI tests 3.13) |
| Python web | FastAPI + uvicorn | Async handlers, SSE |
| Go | Go | 1.26.2 |
| Go web | Gin | v1.12.0 |
| Frontend | Angular | 21.x (signals, standalone) |
| Frontend tests | Vitest | Via `@angular/build` |
| Container | Podman (preferred) / Docker | Auto-detected |

---

## Enforcement Checklist for Agents

Before modifying code, verify:

- [ ] Does this change follow TDD (failing test first)?
- [ ] Are tests added or updated in `./tests/` (not `download-proxy/tests/`)?
- [ ] Do modified Python files pass `python3 -m py_compile`?
- [ ] Do modified Bash files pass `bash -n`?
- [ ] Is `.env` untouched and still gitignored?
- [ ] Are WebUI credentials still `admin`/`admin`?
- [ ] If modifying IPTorrents code, is freeleech-only policy preserved?
- [ ] Are there NO new comments in `download-proxy/src/`?
- [ ] If raising coverage, is `docs/COVERAGE_BASELINE.md` updated?
- [ ] If modifying `docker-compose.yml`, are `start.sh`/`stop.sh` updated?
- [ ] If modifying plugins, is `install-plugin.sh --verify` run?
- [ ] Does `./ci.sh --quick` pass?

---

**Version**: 1.2.0 | **Ratified**: 2026-04-13 | **Last Amended**: 2026-04-24
