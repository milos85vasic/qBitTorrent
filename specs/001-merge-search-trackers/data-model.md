# Data Model: Merge Search Results Across Trackers

## Entities

### SearchResult

A single result from one tracker plugin (existing, from nova3 engine).

| Field | Type | Description |
|-------|------|-------------|
| `fileName` | str | Name of the torrent |
| `fileUrl` | str | Download URL (.torrent or magnet) |
| `fileSize` | int | Size in bytes |
| `nbSeeders` | int | Number of seeders |
| `nbLeechers` | int | Number of leechers |
| `engineName` | str | Tracker/plugin name |
| `descrLink` | str | Description/detail page URL |
| `pubDate` | str | Publication date (ISO format) |

### MergedResult

A consolidated entry grouping multiple SearchResults as the same content.

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Unique merge ID (hash of canonical identity) |
| `canonicalName` | str | Resolved canonical name |
| `canonicalIdentity` | CanonicalIdentity | External metadata identity |
| `totalSeeders` | int | Sum of all valid tracker seeders |
| `totalLeechers` | int | Sum of all valid tracker leechers |
| `sources` | list[TrackerSource] | All tracker sources |
| `enrichedMetadata` | EnrichedMetadata | From external APIs |
| `bestQuality` | Quality | Highest quality available |
| `createdAt` | datetime | When first source arrived |
| `updatedAt` | datetime | Last update time |

### TrackerSource

A single tracker's version of a torrent within a MergedResult.

| Field | Type | Description |
|-------|------|-------------|
| `trackerName` | str | Tracker's display name |
| `downloadUrl` | str | Direct download URL |
| `magnetUrl` | str | Magnet link (if available) |
| `seeders` | int | Current seeders from scrape |
| `leechers` | int | Current leechers from scrape |
| `healthStatus` | enum | `healthy`, `unhealthy`, `untested` |
| `lastValidated` | datetime | Last scrape check |
| `requiresAuth` | bool | Needs private tracker credentials |
| `quality` | Quality | Detected quality (720p, 1080p, etc.) |

### CanonicalIdentity

External metadata identity for cross-tracker matching.

| Field | Type | Description |
|-------|------|-------------|
| `source` | enum | `omdb`, `tmdb`, `tvmaze`, `anilist`, `musicbrainz`, `openlibrary` |
| `externalId` | str | External service ID |
| `title` | str | Canonical title |
| `year` | int | Release year |
| `type` | enum | `movie`, `tv`, `anime`, `music`, `book` |

### EnrichedMetadata

Enriched data from external metadata APIs.

| Field | Type | Description |
|-------|------|-------------|
| `posterUrl` | str | Poster image URL |
| `rating` | float | Average rating (0-10) |
| `genres` | list[str] | Genre tags |
| `description` | str | Plot/synopsis |
| `releaseDate` | str | Release date |
| `duration` | int | Runtime in minutes |

### Quality

Detected video quality from torrent name.

| Field | Type | Description |
|-------|------|-------------|
| `resolution` | str | `480p`, `720p`, `1080p`, `1440p`, `4k` |
| `codec` | str | `x264`, `x265`, `hevc`, `av1` |
| `source` | str | `BluRay`, `WEB-DL`, `HDRip`, `DVD` |
| `audio` | str | `AAC`, `AC3`, `FLAC` |

### HookEvent

A structured event fired at pipeline stages.

| Field | Type | Description |
|-------|------|-------------|
| `eventType` | enum | Event type (see spec FR-011) |
| `timestamp` | datetime | When event fired |
| `torrentName` | str | Torrent name |
| `infoHash` | str | Info hash (if available) |
| `trackers` | list[str] | Tracker URLs |
| `seeders` | int | Total seeders |
| `leechers` | int | Total leechers |
| `filePath` | str | Download file path (if applicable) |
| `error` | str | Error message (if applicable) |

### HookConfig

Configuration for hook scripts.

| Field | Type | Description |
|-------|------|-------------|
| `eventType` | enum | Event to trigger on |
| `scriptPath` | str | Path to executable script |
| `timeout` | int | Timeout in seconds (default 30) |
| `enabled` | bool | Whether active |

### ScheduledTask

Automated scheduled search or download task.

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Task ID |
| `name` | str | Display name |
| `query` | str | Search query |
| `schedule` | str | Cron expression |
| `action` | enum | `search`, `download` |
| `targetId` | str | MergedResult ID to download |
| `enabled` | bool | Active |

## Validation Rules

- **MergedResult.sources**: Must have at least 1 valid source
- **TrackerSource.healthStatus**: Only `healthy` sources included in totals
- **CanonicalIdentity.source**: Must be one of the supported enum values
- **HookConfig.timeout**: Must be between 1 and 300 seconds
- **ScheduledTask.schedule**: Must be valid cron expression

## State Transitions

### MergedResult States

```
UNTESTED → VALIDATING → MERGED → VALIDATED
              ↓
           FAILED (all trackers dead)
```

### TrackerSource States

```
UNTESTED → VALIDATING → HEALTHY
           ↓           ↓
        UNHEALTHY → (can be re-tested)
```

## Relationships

```
SearchResult (many) → (is merged into) → MergedResult (one)
MergedResult (one) → has sources → TrackerSource (many)
MergedResult (one) → resolves to → CanonicalIdentity (one)
MergedResult (one) → enriches to → EnrichedMetadata (one)
TrackerSource (many) → has → Quality (one)
HookConfig (many) → fires on → HookEvent (one per occurrence)
ScheduledTask (many) → triggers → Action (search/download)
```