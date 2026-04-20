# Merge-Search Diagnostics

This document explains how the merge service reports per-tracker failures
so operators can distinguish "nothing wrong, niche board has no hits for
this query" from "upstream is dead" from "plugin is crashing."

Context: prior to 2026-04-19 a search for `linux` returned 137 total
hits and 37 of 40 trackers returned zero with **no explanation**. The
root cause was a monkeypatch targeting the wrong `novaprinter` module
(see commit `e8b904d`), but the deeper problem was visibility:
`TrackerSearchStat.error` was always `None` on empty trackers, so
operators couldn't tell whether an empty chip meant "nothing to see"
or "broken." This doc describes the diagnostic pipeline that
replaces that opacity.

## Data flow

```
plugin subprocess stderr ──▶ _classify_plugin_stderr()
                              │
                              ▼
                       _last_public_tracker_diag[tracker]
                              │
                              ▼
                       _search_one() pops + writes to
                              │
                              ▼
                  TrackerSearchStat.{error,error_type,notes}
                              │
                              ▼
           API response `tracker_stats[]` + SSE `tracker_completed`
                              │
                              ▼
      dashboard chip badge + tracker-stat-dialog "Error" section
```

Every public-tracker subprocess runs in isolation in a Python 3.12
process spawned by `_search_public_tracker`
(`download-proxy/src/merge_service/search.py`). Whatever the plugin
writes to stderr is captured after the subprocess exits (or is killed
at the deadline) and passed through `_classify_plugin_stderr` to
produce a structured diagnostic.

## Error classes (`error_type`)

| `error_type`             | Meaning                                                    | Operator action              |
|--------------------------|------------------------------------------------------------|------------------------------|
| `upstream_http_403`      | Remote tracker returned 403 Forbidden                      | Likely geoblock or CDN WAF. Try VPN. |
| `upstream_http_404`      | Remote tracker returned 404 Not Found                      | Domain moved — update `PUBLIC_TRACKERS` URL |
| `upstream_timeout`       | Remote gateway timed out                                   | Transient — retry or bump `PUBLIC_TRACKER_DEADLINE_SECONDS` |
| `dns_failure`            | Tracker hostname does not resolve                          | Domain is dead — move to `DEAD_PUBLIC_TRACKERS` |
| `tls_failure`            | TLS handshake with upstream failed                         | Cert issue upstream. No action. |
| `upstream_incomplete`    | Upstream closed connection mid-response                    | Transient — retry |
| `plugin_env_missing`     | Plugin needs a file/dir not present in the container       | Check plugin source; add dir to Dockerfile |
| `plugin_parse_failure`   | Plugin regex/JSON parse failed (upstream HTML rotated)     | Patch plugin regex |
| `plugin_crashed`         | Plugin raised an uncategorised exception                   | Read `notes.stderr_tail` for traceback |
| `deadline_timeout`       | Plugin was still running after per-tracker deadline        | Bump deadline or split the work |
| `auth_failure`           | Private tracker login returned no session cookie           | Check credentials in `.env`; may be transient CAPTCHA |
| `upstream_captcha`       | Private tracker served a CAPTCHA page instead of results   | Wait a few minutes and retry; rotate IP if persistent |

When the plugin runs cleanly but doesn't emit any rows, `error_type` is
`None` and `status` stays at `empty`. This is the "genuinely no hits
for this query on this board" path — e.g. searching `linux` on an
anime-only tracker.

## Environment variables

### `PUBLIC_TRACKER_DEADLINE_SECONDS`

Default: `25`. Clamped to `[5, 120]`.

How long each public-tracker subprocess may run before it is
SIGKILLed. Because `_search_public_tracker` streams results as NDJSON
with `sys.stdout.flush()`, partial results are preserved even if the
deadline fires mid-scrape. When that happens,
`TrackerSearchStat.notes["deadline_hit"] = True` and the dashboard
chip shows a stopwatch icon.

Raise this if you have slow upstreams and are willing to wait — but
remember that the orchestrator runs up to
`MAX_CONCURRENT_TRACKERS` fan-out tasks at a time, so wall-clock
latency grows with `deadline × ceil(trackers / max_concurrent)`.

### `ENABLE_DEAD_TRACKERS`

Default: `0` (dead trackers excluded from fan-out).

Public trackers that are empirically known-dead as of 2026-04-19 live
in `DEAD_PUBLIC_TRACKERS` in `search.py` and are excluded from the
fan-out by default so the dashboard isn't dominated by permanently-red
chips. Set `ENABLE_DEAD_TRACKERS=1` to force them back in — useful
when testing whether an upstream has recovered, or when operating
through a proxy/VPN that bypasses the geoblock.

The known-dead list:

* HTTP 403: `eztv`, `kickass`, `bt4g`, `extratorrent`, `one337x`
* HTTP 404: `bitru`, `megapeer`, `yts`
* Gateway timeout: `nyaa`
* DNS failure: `glotorrents`, `pctorrent`, `yihua`, `torrentgalaxy`
* TLS failure: `xfsub`
* Plugin bugs: `yourbittorrent` (stale regex), `anilibra` (NoneType crash)
* Silently empty (plugin swallows upstream 403): `solidtorrents`,
  `therarbg`, `torrentfunk`, `ali213`, `btsow`, `gamestorrents`,
  `torrentkitty`. These plugins catch the HTTPError internally and
  never print to stderr, so the classifier can't tag them — probing
  each upstream with `curl` confirms they all serve `403 Forbidden`
  to anonymous visitors. Fixing requires either patching every
  plugin to re-raise or changing its User-Agent; shelved until
  someone cares enough to debug each one.

These plugins are still installed and the classifier still reports
their real reasons when `ENABLE_DEAD_TRACKERS=1`, so it's easy to
spot when an upstream starts working again and move the entry out of
the set.

### `MAX_CONCURRENT_TRACKERS`

Default: `5`. Semaphore-bounded fan-out width. Wall-clock latency is
approximately `deadline × (tracker_count / max_concurrent)` in the
worst case. Lower this on constrained hosts to keep memory bounded.

### `MAX_CONCURRENT_SEARCHES`

Default: `8`. Per-orchestrator cap on the number of in-flight
`_run_search` fan-outs. When saturated, both `POST /api/v1/search`
and `POST /api/v1/search/sync` return HTTP 429 with a
`retry shortly` hint so callers back off rather than piling more
subprocess work on a starving event loop.

Stress tests revealed that without this cap, 50 rapid POSTs would
spawn 50 × 24 = 1200 simultaneous subprocess spawns and even
`/health` stopped responding. With the cap in place the service
remains responsive (at most 8 × 24 = ~200 subprocesses mid-flight,
plus the 5-per-fan-out semaphore actually runs closer to 40).

## Dashboard chip legend

| Icon      | Meaning                                                      |
|-----------|--------------------------------------------------------------|
| `✓ N`     | Success — N results                                          |
| `∅`       | Empty — plugin ran cleanly, found nothing for this query     |
| `⚠`       | Error — hover for `error_type`, click for full dialog        |
| `⏱`       | Deadline hit — results are truncated to whatever flushed      |
| `🔒`      | Authenticated session used                                   |

Click any chip to open the **tracker-stat dialog** which shows the
full `TrackerSearchStat` including `notes.stderr_tail` for crashed
plugins.

## Rebuild / restart contract

`docker-compose.yml` bind-mounts `./download-proxy/` into the
container at `/config/download-proxy`. That means:

* **Python source changes in `download-proxy/src/`** → `podman restart
  qbittorrent-proxy` picks them up; no rebuild needed.
* **Plugin changes in `plugins/`** → `./install-plugin.sh` copies them
  into `./config/qBittorrent/nova3/engines/`, which is also
  bind-mounted; restart again picks them up.
* **`docker-compose.yml` / `start-proxy.sh` / env changes** → `podman
  compose down && podman compose up -d`.

Full rebuild (`podman build`) is only necessary when the base image
(`python:3.12-alpine`) itself needs to change.

## Troubleshooting

**All public trackers return 0.** The subprocess capture is broken.
First thing to check: does the script in `_search_public_tracker`
still do `import novaprinter as _np`? If it says `engines.novaprinter`,
you've reintroduced the 37-empty-trackers bug. See commit `e8b904d`.

**One tracker goes to 0 intermittently.** Look at `tracker_stats[].error`.
If it's consistently `upstream_http_403`, the geoblock probably caught
you; if it bounces between `success` and `upstream_timeout`, the
upstream is rate-limiting.

**`results_count` is capped at some suspicious round number.** Check
`notes.deadline_hit`. If true, raise `PUBLIC_TRACKER_DEADLINE_SECONDS`.

**I added a tracker but it never appears in the fan-out.** It's
probably in `DEAD_PUBLIC_TRACKERS`. Move it out, or set
`ENABLE_DEAD_TRACKERS=1` temporarily.
