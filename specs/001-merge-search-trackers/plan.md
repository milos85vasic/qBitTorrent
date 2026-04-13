# Implementation Plan: Merge Search Results Across Trackers

**Branch**: `001-merge-search-trackers` | **Date**: 2026-04-13 | **Spec**: `specs/001-merge-search-trackers/spec.md`
**Input**: Feature specification from `/specs/001-merge-search-trackers/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Extends the download-proxy service with a new streaming API endpoint that performs merged searches across all enabled qBittorrent tracker plugins, deduplicates results using tiered matching (metadata > hash > name+size > name similarity), validates tracker health via scrape endpoints, enriches results with external metadata APIs (OMDb, TMDB, TVMaze, AniList, MusicBrainz, OpenLibrary), and wires all merged tracker URLs into downloads via the qBittorrent Web API. Also adds a hooks system with event logging, real-time download monitoring, automated scheduling, and a web UI dashboard.

## Technical Context

**Language/Version**: Python 3.12 (Alpine)  
**Primary Dependencies**: FastAPI, uvicorn (for streaming SSE/WebSocket), python-Levenshtein (fuzzy matching), aiohttp (async HTTP), requests (sync HTTP), the existing download-proxy Python environment  
**Storage**: In-memory for runtime state; config files in `config/merge-service/` for hooks/scheduling config  
**Testing**: pytest, pytest-asyncio for async tests, integration tests against live qBittorrent  
**Target Platform**: Linux server running download-proxy container (Docker/Podman)  
**Project Type**: web-service / API (FastAPI async) + background service  
**Performance Goals**: <2 seconds for search initiation response, streaming updates every 500ms, tracker scrape timeout 10s max, merge operation <5s for 500 results  
**Constraints**: Must run inside existing download-proxy container; cannot add new container services without docker-compose.yml update; must use existing env var loading pattern for credentials  
**Scale/Scope**: Handles 35+ plugins, up to 1000 results per search, 100 concurrent searches, streaming via SSE/WebSocket to 10 simultaneous clients

## Phase 0: Research

### Research Tasks

1. **Streaming Protocol Selection** — SSE vs WebSocket for real-time merged results
2. **Metadata API Integration Patterns** — OMDb, TMDB, TVMaze, AniList, MusicBrainz integration
3. **Tracker Scrape Protocols** — BEP 48 HTTP scrape, BEP 15 UDP scrape implementation

### Findings

#### 1. Streaming Protocol: SSE (Selected)

**Decision**: Use Server-Sent Events (SSE) instead of WebSocket for streaming merged search results.

**Rationale**: 
- Simpler to implement in FastAPI (`StreamingResponse` with SSE format)
- Works over standard HTTP (no extra port/connection setup)
- Natural fit for request-response with streaming updates
- WebSocket adds complexity (separate connection, more setup) for this use case
- Can be consumed by any HTTP client, browser EventSource, or our web UI

**Alternatives considered**: WebSocket — rejected because SSE is simpler and sufficient for this use case.

#### 2. Metadata API Integration

**Decision**: Each metadata API wrapped in a thin async client class with shared interface.

**Rationale**:
- OMDb: Simple REST API, free key, 1000/day quota
- TMDB: Rich data, free key, 50/sec rate limit
- TVMaze: No auth required, excellent TV show data
- AniList: GraphQL, no auth for public queries
- MusicBrainz: No key required, 1/sec rate limit
- OpenLibrary: No auth, free

All use simple HTTP GET with JSON response. Common interface: `resolve(torrent_name) -> canonical_identity`.

#### 3. Tracker Scrape Implementation

**Decision**: HTTP scrape (BEP 48) as primary, DHT as fallback.

**Rationale**:
- BEP 48 HTTP scrape: Standard, replace `/announce` with `/scrape`
- Most public trackers support it
- UDP scrape (BEP 15) for trackers that only support UDP
- DHT get_peers as final fallback for trackerless verification

**Implementation**: Use `aiohttp` for async HTTP scrape requests. Parse bencoded response.

---

## Phase 1: Design

### Data Model

See `data-model.md` for detailed entity definitions.

### Interface Contracts

See `contracts/api.md` for API endpoint definitions.

### Quickstart

See `quickstart.md` for usage guide.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| **Container-First Architecture** | ✅ PASS | Download-proxy container already defined in docker-compose.yml; new endpoints extend existing service |
| **Plugin Contract Integrity** | ✅ PASS | Uses existing plugin architecture; extends not replaces |
| **Credential & Secret Security** | ✅ PASS | Uses existing env var pattern for private tracker credentials |
| **Container Runtime Portability** | ✅ PASS | Runs in existing download-proxy; no new container runtime required |
| **Private Tracker Bridge Pattern** | ✅ PASS | Leverages existing webui-bridge.py for authenticated downloads; our API wires trackers post-add |
| **Validation-Driven Development** | ✅ PASS | All changes tested via python -m py_compile and existing test suite |
| **Operational Simplicity** | ✅ PASS | Single API endpoint for all operations; web UI for management |

**Gates determined based on constitution file** — All gates pass. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-merge-search-trackers/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── api.md           # API endpoint contracts
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

The feature extends the existing download-proxy service:

```text
# New code: extends existing download-proxy (runs in download-proxy container)
download-proxy/
├── src/
│   ├── merge_service/      # NEW: Core merge logic
│   │   ├── __init__.py
│   │   ├── search.py        # Search orchestration, plugin invocation
│   │   ├── deduplicator.py # Tiered matching logic
│   │   ├── validator.py     # Tracker health validation via scrape
│   │   ├── enricher.py      # Metadata API integration
│   │   └── hooks.py         # Event hooks system
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py        # NEW: FastAPI routes for merged search
│   │   ├── streaming.py     # SSE/WebSocket streaming
│   │   └── hooks.py         # Hook execution API
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── static/         # Web UI assets
│   │   └── templates/       # Web UI templates
│   └── config/
│       ├── __init__.py
│       └── hooks.yaml        # Hook configuration
│
├── config/
│   ├── merge-service/      # NEW: Runtime config
│   │   ├── hooks.yaml     # Hook scripts configuration
│   │   └── scheduling.yaml # Scheduled tasks config
│   └── hooks/            # Hook scripts (executable bash scripts)
│       └── log_event.sh  # Default logging hook
│
tests/
├── unit/
│   └── merge_service/   # Unit tests
├── integration/
│   └── test_merge_api.py # Integration tests
└── e2e/
    └── test_full_pipeline.py # End-to-end tests with real downloads
```

**Structure Decision**: Feature code lives in `download-proxy/` extending existing Python service. New directories created within existing structure per Constitution Principle I (no new containers without compose update).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *No violations* | All gates pass | - |
