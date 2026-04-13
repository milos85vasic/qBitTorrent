# API Contracts: Merge Search Results Across Trackers

## Overview

The merge search feature exposes a new API endpoint on the download-proxy service. All endpoints return JSON unless otherwise specified.

**Base URL**: `http://localhost:8085/api/merge/v1`

## Authentication

Uses existing qBittorrent WebUI authentication. Include `SID` cookie or set `Authorization: Basic base64(admin:admin)` header.

---

## Endpoints

### 1. Start Merged Search

**POST** `/search`

Starts a new merged search across all enabled tracker plugins.

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Search query string |
| `category` | string | No | Category filter: `all`, `movies`, `tv`, `anime`, `books`, `music`, `games`, `software` |
| `plugins` | list[string] | No | Specific plugins to use (default: all enabled) |

**Response** (202 Accepted):

```json
{
  "searchId": "search_abc123",
  "status": "started",
  "pluginsCount": 12,
  "streamingEndpoint": "/search/stream/search_abc123"
}
```

**Streaming Endpoint** (SSE):

**GET** `/search/stream/{searchId}`

Returns Server-Sent Events with incremental merged results.

**Event Format**:

```json
event: update
data: {
  "searchId": "search_abc123",
  "status": "running",
  "pluginsCompleted": 5,
  "pluginsTotal": 12,
  "results": [
    {
      "id": "merge_xyz789",
      "canonicalName": "Ubuntu 24.04 LTS",
      "totalSeeders": 1500,
      "totalLeechers": 200,
      "sources": [
        {"trackerName": "LimeTorrents", "seeders": 500, "healthStatus": "healthy"},
        {"trackerName": "SolidTorrents", "seeders": 1000, "healthStatus": "healthy"}
      ],
      "sourceCount": 2
    }
  ]
}
```

**Final Event**:

```json
event: done
data: {
  "searchId": "search_abc123",
  "status": "complete",
  "totalResults": 45,
  "mergedResults": 12,
  "duration": "3.2s"
}
```

---

### 2. Download Merged Result

**POST** `/download`

Adds a merged result to qBittorrent and wires all tracker URLs.

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `resultId` | string | Yes | MergedResult ID to download |
| `savePath` | string | No | Custom save path |
| `category` | string | No | Torrent category |

**Response** (200 OK):

```json
{
  "torrentHash": "abc123def456...",
  "name": "Ubuntu 24.04 LTS",
  "trackersAdded": 3,
  "status": "downloading"
}
```

---

### 3. Get Active Downloads

**GET** `/downloads/active`

Returns real-time status of all active downloads.

**Response** (200 OK):

```json
{
  "downloads": [
    {
      "torrentHash": "abc123...",
      "name": "Ubuntu 24.04 LTS",
      "progress": 45.5,
      "downSpeed": 5000000,
      "upSpeed": 0,
      "seeders": 1500,
      "peers": 200,
      "trackers": [
        {"url": "http://tracker1/announce", "status": "working"},
        {"url": "http://tracker2/announce", "status": "working"}
      ]
    }
  ]
}
```

---

### 4. Configure Hooks

**GET** `/hooks`

List all configured hooks.

**POST** `/hooks`

Create a new hook configuration.

**Request Body**:

```json
{
  "eventType": "download_completed",
  "scriptPath": "/config/hooks/my_script.sh",
  "timeout": 30,
  "enabled": true
}
```

**DELETE** `/hooks/{hookId}`

Remove a hook.

---

### 5. Get Hook Events

**GET** `/hooks/events`

List recent hook events with payloads.

**Query Parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `limit` | int | Max events to return (default: 50) |
| `eventType` | string | Filter by event type |

---

### 6. Schedule Tasks

**GET** `/schedule`

List all scheduled tasks.

**POST** `/schedule`

Create a scheduled task.

**Request Body**:

```json
{
  "name": "Weekly Ubuntu check",
  "query": "Ubuntu 24.04 LTS",
  "schedule": "0 8 * * 1",
  "action": "search"
}
```

**DELETE** `/schedule/{taskId}`

Remove a scheduled task.

---

### 7. Health Check

**GET** `/health`

Returns service health and metadata API connectivity.

**Response** (200 OK):

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "plugins": {
    "enabled": 12,
    "working": 11
  },
  "metadataApis": {
    "omdb": "connected",
    "tmdb": "connected",
    "tvmaze": "connected"
  }
}
```

---

## Web UI Endpoints

The service also serves a web UI at the base URL (no `/api` prefix):

- `/` — Main dashboard
- `/search` — Merged search interface
- `/downloads` — Active downloads
- `/hooks` — Hook management
- `/schedule` — Scheduled tasks
- `/logs` — Event logs

---

## Error Responses

All endpoints may return these errors:

| Status | Code | Description |
|--------|------|-------------|
| 400 | `bad_request` | Invalid parameters |
| 401 | `unauthorized` | Authentication required |
| 404 | `not_found` | Resource not found |
| 408 | `timeout` | Operation timed out |
| 500 | `internal_error` | Server error |

**Example Error**:

```json
{
  "error": "bad_request",
  "message": "Invalid query: query is required"
}
```