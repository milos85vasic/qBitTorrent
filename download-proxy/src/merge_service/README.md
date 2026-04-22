# download-proxy/src/merge_service/

Core search orchestration, deduplication, enrichment, validation, hooks, and scheduling.

## Entry Points

- **`search.py`** — `SearchOrchestrator`: fan-out tracker searches, collect results, drive dedup pipeline.
- **`deduplicator.py`** — `Deduplicator`: tiered matching (infohash → name+size → fuzzy title).
- **`enricher.py`** — `MetadataEnricher`: OMDb/TMDB/TVMaze/AniList/MusicBrainz/OpenLibrary lookups + quality detection.
- **`validator.py`** — Tracker health validation via HTTP and UDP scrape.
- **`hooks.py`** — Hook engine: event dispatch, script execution, JSON persistence.
- **`scheduler.py`** — Periodic search scheduler with JSON persistence.
- **`retry.py`** — Tenacity-based retry policy for outbound HTTP calls.

## Data Model

See `docs/DATA_MODEL.md` for full field-level documentation. Key types:

| Class | File | Purpose |
|-------|------|---------|
| `SearchMetadata` | `search.py` | Per-search lifecycle state |
| `SearchResult` | `search.py` | Single tracker result row |
| `MergedResult` | `search.py` | Deduplicated aggregate |
| `CanonicalIdentity` | `search.py` | Normalised fingerprint for dedup |
| `MatchResult` | `deduplicator.py` | Pairwise match outcome |
| `MetadataResult` | `enricher.py` | External metadata lookup result |
| `ScrapeResult` | `validator.py` | Tracker health probe |
| `HookEvent` / `HookConfig` | `hooks.py` | Hook lifecycle |
| `ScheduledSearch` | `scheduler.py` | Recurring search job |

## Conventions

- Dataclasses for internal state, Pydantic only in the `api/` layer.
- `asyncio.Semaphore` caps concurrent tracker searches.
- `TTLCache` for bounded in-memory stores (sessions, pending CAPTCHAs, cached results).
- `asyncio.Lock` guards all shared mutable state.
- All datetimes are UTC; serialisers call `.isoformat()`.

## How to Test

```bash
python3 -m pytest tests/unit/merge_service/ -v --import-mode=importlib
python3 -m pytest tests/unit/ -k "dedup" -v --import-mode=importlib
```
