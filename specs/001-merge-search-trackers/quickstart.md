# Quickstart: Merge Search Results Across Trackers

## Overview

This feature adds merged search capabilities to the qBitTorrent download-proxy. Search once, get results from all trackers deduplicated and validated, with all tracker URLs wired into your download.

## Prerequisites

- Running download-proxy container
- qBitTorrent container running
- At least 3 tracker plugins enabled

## Quick Start

### 1. Search for Content

```bash
# Start a merged search
curl -X POST http://localhost:7186/api/merge/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Ubuntu 24.04 LTS"}' \
  -c cookies.txt -u admin:admin

# Stream results as they arrive
curl -N http://localhost:7186/api/merge/v1/search/stream/search_abc123 \
  -c cookies.txt -u admin:admin
```

### 2. Download a Merged Result

```bash
# Download merged result ID "merge_xyz"
curl -X POST http://localhost:7186/api/merge/v1/download \
  -H "Content-Type: application/json" \
  -d '{"resultId": "merge_xyz"}' \
  -c cookies.txt -u admin:admin
```

### 3. Check Active Downloads

```bash
curl http://localhost:7186/api/merge/v1/downloads/active \
  -c cookies.txt -u admin:admin
```

## Web UI

Open `http://localhost:7186/` in your browser to access the web UI dashboard.

### Features

- **Search Tab**: Enter a query, see merged results with per-tracker breakdown
- **Downloads Tab**: Monitor active downloads with real-time peer counts
- **Hooks Tab**: Configure event hooks to trigger scripts on pipeline events
- **Schedule Tab**: Set up automated searches (e.g., every Monday at 8pm)
- **Logs Tab**: View all hook events

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MERGE_STREAM_UPDATE_MS` | Streaming update interval | 500ms |
| `METADATA_API_KEY_OMDB` | OMDb API key | (from .env) |
| `METADATA_API_KEY_TMDB` | TMDB API key | (from .env) |
| `TRACKER_SCRAPE_TIMEOUT` | Tracker scrape timeout | 10s |
| `MATCH_CONFIDENCE_THRESHOLD` | Min similarity for merge | 70% |

### Hook Configuration

Hooks are configured in `config/merge-service/hooks.yaml`:

```yaml
hooks:
  - eventType: download_completed
    scriptPath: /config/hooks/log_event.sh
    timeout: 30
    enabled: true
```

### Hook Scripts

Hook scripts receive event data as JSON on stdin:

```bash
#!/bin/bash
# log_event.sh
while read -r event; do
  echo "$(date '+%Y-%m-%d %H:%M:%S') $event" >> /var/log/hook_events.log
done
```

## Common Tasks

### Enable/Disable Plugins for Merged Search

By default, all enabled plugins are used. To use specific plugins:

```bash
curl -X POST http://localhost:7186/api/merge/v1/search \
  -d '{"query": "Ubuntu", "plugins": ["rutracker", "limetorrents", "solidtorrents"]}'
```

### Filter by Category

```bash
curl -X POST http://localhost:7186/api/merge/v1/search \
  -d '{"query": "matrix", "category": "movies"}'
```

### Set Up Scheduled Search

```bash
curl -X POST http://localhost:7186/api/merge/v1/schedule \
  -d '{
    "name": "New Ubuntu releases",
    "query": "Ubuntu 24.04",
    "schedule": "0 8 * * 1",
    "action": "search"
  }'
```

## Troubleshooting

### No results merged

- Check that multiple plugins are enabled: `curl /api/v2/search/plugins`
- Verify metadata API keys are configured
- Try a more common search term

### Download failed

- Check private tracker credentials are configured in .env
- Verify at least one tracker source is healthy
- Check qBittorrent is running and accessible

### Hook not firing

- Verify hook script is executable: `chmod +x /config/hooks/script.sh`
- Check hook is enabled in config
- Review hook logs at `/var/log/hook_events.log`

## API Reference

See `contracts/api.md` for complete endpoint documentation.