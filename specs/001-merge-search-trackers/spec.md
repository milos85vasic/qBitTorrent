# Feature Specification: Merge Search Results Across Trackers

**Feature Branch**: `001-merge-search-trackers`
**Created**: 2026-04-13
**Status**: Draft
**Input**: User description: "Merge search results from multiple trackers with deduplication, validation, event hooks, and enhanced metadata"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unified Search Results with Merged Trackers (Priority: P1)

As a user searching for content, when I search across multiple tracker
plugins, I want duplicate results from different trackers to be
automatically merged into a single entry so that I see unique content
organized by relevance, not scattered duplicates.

**Why this priority**: This is the core value proposition — without
deduplication, users see the same content 3-5 times from different
trackers, making search results noisy and unmanageable.

**Independent Test**: Can be fully tested by searching for a popular
Linux distribution (e.g., Ubuntu) that exists on many trackers, then
verifying that results are merged into single entries with multiple
tracker sources listed.

**Acceptance Scenarios**:

1. **Given** the user searches for "Ubuntu 24.04", **When** results
   arrive from 5+ trackers (e.g., Rutracker, LimeTorrents,
   SolidTorrents, TorrentProject, TorrentsCSV), **Then** identical
   content is merged into a single result entry showing all tracker
   sources with their combined seeders/peers.
2. **Given** merged results are displayed, **When** the user views a
   merged entry, **Then** the entry shows the total seeders and peers
   aggregated from all tracker sources, plus a breakdown per tracker.
3. **Given** merged results are displayed, **When** the user
   schedules a merged result for download, **Then** all tracker URLs
   from all merged sources are added to the torrent as a multi-tracker
   announce list, initiating download immediately.

---

### User Story 2 - Tracker Validation and Dead Tracker Elimination (Priority: P2)

As a user reviewing merged search results, I want the system to
automatically verify that each tracker source is online and healthy
before presenting results, so I never waste time on dead or broken
tracker links.

**Why this priority**: Dead trackers waste user time and produce
failed downloads. Health validation is essential for trust in merged
results but depends on the merge infrastructure from P1.

**Independent Test**: Can be tested by querying tracker scrape
endpoints for known-dead trackers and verifying they are marked as
invalid, plus testing that offline trackers are eliminated from merged
results.

**Acceptance Scenarios**:

1. **Given** results are being merged from multiple trackers, **When**
   a tracker's scrape endpoint is unreachable or returns zero seeders,
   **Then** that tracker source is marked as unhealthy and excluded from
   the merged entry.
2. **Given** a merged result contains 4 tracker sources, **When** 1
   tracker is offline, **Then** the result still appears with the
   remaining 3 valid sources and their combined seeders/peers.
3. **Given** all tracker sources for a merged result are dead, **When**
   validation completes, **Then** the result is either hidden or
   clearly flagged as "no active sources" with zero seeders.

---

### User Story 3 - Metadata Enrichment for Better Matching (Priority: P3)

As a user searching for content, I want the system to use external
metadata APIs (movie databases, music databases, etc.) to accurately
identify content across trackers, so that "Movie.Name.2024.1080p" on
one tracker and "Movie Name (2024) [Bluray 1080p]" on another are
recognized as the same content and merged.

**Why this priority**: Fuzzy name matching without external metadata
produces false merges (different movies with similar names) and missed
merges (same movie with very different naming). Metadata APIs solve
this but require more integration work.

**Independent Test**: Can be tested by searching for a popular movie
available on multiple trackers under different naming conventions, then
verifying the metadata lookup correctly identifies them as the same
content.

**Acceptance Scenarios**:

1. **Given** the user searches for a movie title, **When** results
   arrive with different naming patterns (e.g., "Inception.2010.BluRay"
   vs "Inception (2010) 1080p"), **Then** the system resolves both to
   the same canonical identity (e.g., IMDB ID) and merges them.
2. **Given** the system identifies content via metadata, **When** the
   user views a merged entry, **Then** enriched metadata is displayed
   (poster, rating, year, genre, description) alongside the search
   result.
3. **Given** the system cannot resolve content via metadata APIs, **When**
   fallback matching is used, **Then** results are still merged using
   name similarity and file size heuristics as a best-effort approach.

---

### User Story 4 - Pipeline Event Hooks System (Priority: P4)

As a developer or advanced user, I want a hooks system that fires
events at every stage of the search-download pipeline so that custom
scripts can be attached to react to, log, or modify pipeline behavior
without changing core code.

**Why this priority**: Hooks enable extensibility and observability.
The initial implementation (logging scripts) is low-risk, and the hook
infrastructure enables future automation. But it depends on the search
and download pipeline existing first.

**Independent Test**: Can be tested by configuring a logging hook,
performing a search and download, and verifying that log entries appear
for each pipeline event with correct event data.

**Acceptance Scenarios**:

1. **Given** hook scripts are configured for pipeline events, **When**
   a search completes and results are merged, **Then** the
   `search_results_merged` event fires with event data containing the
   merged result count and tracker breakdown.
2. **Given** a download is started from a merged result, **When** the
   torrent is added to qBittorrent, **Then** the `download_added`
   event fires with event data containing the torrent name, hash,
   tracker count, and total seeders.
3. **Given** hook scripts are configured, **When** a download
   completes, **Then** the `download_completed` event fires and the
   attached logging script receives event data including the file path
   and total download time.

---

### User Story 5 - Comprehensive Test Suite with Real Downloads (Priority: P5)

As a developer, I want automated end-to-end tests that verify the
entire pipeline works by downloading real content (Linux distributions)
from multiple trackers and confirming that merged multi-tracker
downloads complete successfully.

**Why this priority**: Full confidence requires real downloads, but
this is a validation story that depends on all previous stories being
implemented.

**Independent Test**: Can be tested by running the test suite against a
live qBittorrent instance and verifying that a Linux distribution
torrent (e.g., Ubuntu) downloaded via merged trackers completes
successfully.

**Acceptance Scenarios**:

1. **Given** the test suite runs, **When** it searches for "Ubuntu"
   across all enabled plugins, **Then** results from 3+ trackers are
   found and merged into consolidated entries.
2. **Given** a merged Ubuntu torrent result, **When** the test
   triggers a download, **Then** the torrent is added to qBittorrent
   with trackers from all merged sources, and the download completes
   with data from multiple tracker peers.
3. **Given** the test suite covers unit, integration, and end-to-end
   scenarios, **When** all tests run, **Then** 100% of tests pass,
   covering: merge logic, tracker validation, metadata enrichment,
   hook execution, and real download completion.

---

### Edge Cases

- What happens when two torrents have the same name but different file
  contents (e.g., same movie title but different resolutions)?
  The system MUST keep them as separate results differentiated by
  quality/resolution metadata.
- What happens when a tracker returns rate-limited or CAPTCHA-blocked
  results? The system MUST skip that tracker's results gracefully and
  proceed with results from other trackers.
- What happens when metadata APIs are unreachable or return errors?
  The system MUST fall back to name-based heuristic matching.
- What happens when the user downloads a merged result but only one
  tracker has seeders? The system MUST still download successfully
  from the single available tracker.
- What happens when hook scripts fail or hang? The system MUST
  timeout hook execution (configurable, default 30 seconds) and
  continue the pipeline without blocking.

## Clarifications

### Session 2026-04-13

- Q: Where do users see and interact with merged search results? → A: New API endpoint on the download-proxy that returns merged results, fully integrated and wired end-to-end. Any client (WebUI, CLI, scripts) can consume the endpoint. The proxy automatically triggers qBittorrent's search API, collects results from all plugins, merges and validates them, and returns enriched results. Downloads triggered through the same endpoint automatically wire all merged tracker URLs via qBittorrent's `addTrackers` API.
- Q: What is explicitly out of scope? → A: Nothing is excluded. Everything related to search, merge, download, hooks, metadata, monitoring, scheduling, and UI is in scope. The feature is a complete end-to-end platform enhancement.
- Q: How should merged results be delivered? → A: Streaming — results merge and update incrementally as each plugin reports in. The API returns partial merged results that get updated in real-time as new tracker results arrive.
- Q: What matching confidence threshold? → A: Tiered approach: metadata identity (100% confidence) > info hash (100%) > name+size combined (high confidence) > name-only similarity graded by Levenshtein distance; keep separate if below 70% similarity.
- Q: How should private tracker credentials be handled? → A: Use pre-loaded environment credentials; private trackers are included in merged results only if valid credentials (RUTRACKER_*, KINOZAL_*, NNMCLUB_*, etc.) are configured via environment variables. The download-proxy automatically uses these credentials when downloading merged results that include private tracker sources.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a new API endpoint on the
  download-proxy service that triggers a merged search across all
  enabled tracker plugins, collects results, merges duplicates,
  validates trackers, and returns enriched results. The endpoint
  MUST be fully wired end-to-end: search → merge → validate →
  enrich → respond. Results MUST be delivered via streaming:
  as each plugin reports results, they are immediately merged
  into the existing result set and the updated merged results
  are pushed to the client in real-time.
- **FR-002**: The system MUST identify duplicate content across
  trackers using a tiered matching approach, in order of
  descending confidence: (a) canonical metadata identity
  from external APIs (100% confidence), (b) info hash when
  available (100% confidence), (c) name similarity combined
  with file size and quality attributes (high confidence),
  (d) name-only similarity graded by Levenshtein distance
  (keep separate if below 70% similarity).
- **FR-003**: The system MUST merge identified duplicates into a
  single result entry that preserves all tracker sources, their
  individual seeders/peers counts, and download URLs.
- **FR-004**: The system MUST aggregate seeders and peers from all
  merged tracker sources into combined totals displayed to the user.
- **FR-005**: The system MUST present merged results clearly, showing
  the number of tracker sources, the best-available quality indicators,
  and per-tracker breakdown (seeders, leechers, tracker name).
- **FR-006**: The system MUST validate each tracker source by querying
  its scrape endpoint or checking reported seeders before including it
  in a merged result.
- **FR-007**: The system MUST eliminate tracker sources that are
  offline, unreachable, or report zero seeders from merged results.
- **FR-008**: The download-proxy MUST expose a download endpoint that,
  given a merged result ID, adds the torrent to qBittorrent via the
  Web API (`/api/v2/torrents/add`) and then immediately wires all
  valid tracker URLs from all merged sources using the
  `/api/v2/torrents/addTrackers` endpoint (BEP 12 multi-tracker
  format). The entire flow MUST be a single API call from the
  client's perspective.
- **FR-009**: The system MUST use external metadata APIs to resolve
  torrent names to canonical identities for accurate cross-tracker
  matching. Supported APIs: OMDb/TMDB (movies/TV), TVMaze (TV shows),
  AniList (anime), MusicBrainz (music), OpenLibrary (books).
- **FR-010**: The system MUST fall back to name-similarity and
  file-size heuristics when metadata APIs are unavailable or return no
  match.
- **FR-011**: The system MUST provide a hooks system with events fired
  at these pipeline stages: `search_result_received`,
  `search_results_merged`, `tracker_validated`,
  `tracker_eliminated`, `download_added`, `download_started`,
  `download_paused`, `download_resumed`, `download_error`,
  `download_completed`, `download_moving`, `download_moved`,
  `download_removed`, `download_removed_from_filesystem`.
- **FR-012**: Each hook MUST receive structured event data (JSON)
  containing: event type, timestamp, torrent name, info hash (if
  available), tracker list, seeders/peers counts, file path (if
  applicable), and any error details (if applicable).
- **FR-013**: The system MUST execute configured hook scripts for each
  event, with a configurable timeout (default 30 seconds) per script.
  Hook script failure MUST NOT block the pipeline.
- **FR-014**: The initial hook implementation MUST be a logging bash
  script that prints formatted log lines for every event, including all
  event data fields.
- **FR-015**: The system MUST support configuring hook scripts via a
  configuration file, with the ability to attach multiple scripts to
  the same event and to attach the same script to multiple events.
- **FR-016**: The download-proxy MUST expose a real-time download
  monitoring API endpoint that returns the status of all active
  downloads, including per-tracker peer counts, download/upload speed,
  progress percentage, and estimated time remaining.
- **FR-017**: The system MUST support automated torrent scheduling
  via the download-proxy API, allowing clients to schedule searches
  and downloads at specified times or intervals (e.g., search for new
  episodes every Monday at 8pm).
- **FR-018**: The download-proxy MUST provide a web-accessible UI
  (served on its port) for merged search, download management,
  monitoring active downloads, configuring hooks, and viewing event
  logs. This UI MUST consume the same API endpoints available to
  external clients.
- **FR-019**: The search API MUST support Server-Sent Events (SSE)
  or WebSocket streaming so that clients receive incremental merged
  result updates as each tracker plugin reports in. Each update MUST
  include the current merged result set, the number of plugins that
  have reported so far, and the number still pending.
- **FR-021**: Private trackers MUST be included in merged results
  only if valid credentials are configured via environment variables
  (RUTRACKER_*, KINOZAL_*, NNMCLUB_*, IPTORRENTS_*). The
  download-proxy uses these pre-loaded credentials for authenticated
  downloads. Merged results that require unconfigured credentials
  exclude those tracker sources.

### Key Entities

- **SearchResult**: A single result from one tracker plugin, containing
  name, URL, size, seeders, leechers, engine name, description link,
  and publication date (the existing plugin output format).
- **MergedResult**: A consolidated entry grouping multiple
  SearchResults identified as the same content, containing the
  canonical identity, aggregated seeders/peers, all tracker sources
  with individual stats, and enriched metadata.
- **TrackerSource**: A single tracker's version of a torrent within a
  MergedResult, containing the tracker name, download URL, individual
  seeders/leechers, health status, and last validated timestamp.
- **CanonicalIdentity**: The resolved external identity for a piece of
  content (e.g., IMDB ID, TMDB ID, MusicBrainz Release ID), used for
  cross-tracker matching.
- **HookEvent**: A structured event fired at a pipeline stage,
  containing event type, timestamp, and context-specific data payload.
- **HookScript**: A configured executable (bash script, Python script,
  or other) attached to one or more hook events, with timeout settings.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When searching for content available on 3+ trackers, at
  least 90% of duplicate entries are correctly merged into single
  results.
- **SC-002**: Merged results display accurate aggregated seeder/peer
  counts that match the sum of validated individual tracker stats.
- **SC-003**: Downloads initiated from merged results successfully
  connect to at least one peer within 60 seconds. Connections to
  additional peers from all merged tracker sources complete within
  120 seconds.
- **SC-004**: Dead or offline trackers are identified and excluded
  from merged results within 10 seconds of the scrape validation
  attempt.
- **SC-005**: The end-to-end test suite successfully downloads a Linux
  distribution (e.g., Ubuntu) using merged trackers from 3+ sources and
  verifies data integrity upon completion.
- **SC-006**: All hook events fire correctly with complete event data,
  verifiable by the logging script producing formatted output for every
  event without any pipeline blocking.
- **SC-007**: All tests (unit, integration, end-to-end, automation)
  pass with 100% success rate in the automated test suite.

## Assumptions

- Users have at least 3 tracker plugins enabled to benefit from
  cross-tracker merging.
- External metadata APIs (OMDb, TMDB, TVMaze, etc.) are accessible
  from the container network. API keys for OMDb and TMDB will be
  configured via environment variables (free tier keys are sufficient).
- The qBittorrent Web API v2 is available and accessible from the
  download-proxy container at `localhost:79085`.
- Tracker scrape endpoints follow the standard BEP 48 protocol
  (replacing `/announce` with `/scrape`).
- Hook scripts are stored in a configurable directory and are
  executable by the container process user (PUID/PGID).
- Linux distribution torrents (Ubuntu, Fedora, Debian) are available
  on multiple public trackers simultaneously, making them suitable
  test targets for real download verification.
- The merge service runs as part of the download-proxy container,
  extending its existing Python environment.
