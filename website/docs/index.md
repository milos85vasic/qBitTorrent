# qBittorrent-Fixed

Multi-tracker meta-search for qBittorrent — self-hosted, containerised,
private-tracker-aware.

---

## Feature matrix

| Capability                 | Status | Notes                                                                 |
|----------------------------|--------|-----------------------------------------------------------------------|
| Merge search (FastAPI)     | Yes    | Parallel search across 12 default trackers on port `7187`             |
| SSE streaming              | Yes    | Real-time result delivery to the dashboard                            |
| Public trackers            | Yes    | EZTV, Jackett, LimeTorrents, PirateBay, SolidTorrents, Torlock, TP, TCSV |
| Private trackers           | Yes    | RuTracker, Kinozal, NNMClub, Rutor                                    |
| Private-tracker bridge     | Yes    | `webui-bridge.py` auto-start via systemd on port `7188`               |
| Freeleech protection       | Yes    | IPTorrents freeleech-only; non-freeleech never merges                 |
| Download proxy             | Yes    | Authenticated cookie forwarding on port `7186`                        |
| Quality detection          | Yes    | Resolution, codec, HDR enrichment                                     |
| Deduplication              | Yes    | Cross-tracker canonicalisation of identical releases                  |
| Hooks / webhooks           | Yes    | Search/download event fan-out                                         |
| Scheduler                  | Yes    | Recurring searches, download queueing                                 |
| Scanning stack             | Yes    | Ruff, Semgrep, Trivy, Gitleaks, Snyk, SonarQube, OWASP                |
| Observability stack        | Yes    | Structured logging, metrics, tracing hooks                            |
| Container runtime          | Yes    | Podman preferred, Docker supported, auto-detected                     |
| Angular 19 dashboard       | Yes    | Enterprise UX dashboard in `frontend/` (CLI + Vitest)                 |
| Test catalogue             | Yes    | 331 tests across 30 categories (unit, integration, e2e, perf, stress) |
| Manual CI                  | Yes    | `./ci.sh` entry point, per-job workflow files                         |

## Quickstart

```bash
git clone https://github.com/milos85vasic/qBitTorrent.git
cd qBitTorrent
./setup.sh && ./start.sh
```

Open <http://localhost:7187> for the merge-search dashboard and
<http://localhost:7186> for the qBittorrent WebUI proxy.

Default WebUI credentials: `admin` / `admin`.

## What's in the box

- Merge search service — FastAPI app on `:7187`, SSE streaming, dedup, enrichment.
- SSE streaming — incremental results from every tracker as they arrive.
- 12 trackers by default — configurable via `install-plugin.sh`.
- Private-tracker bridge — `webui-bridge.py` forwards cookie-authenticated downloads.
- Scanning stack — static analysis, secret detection, SBOM, CVE audit.
- Observability — structured logs, metrics endpoint, tracing hooks.
- 30-type test catalogue — unit, contract, integration, e2e, performance, stress,
  security, instrumentation, benchmark.

## Screenshots

<!-- placeholder: add PNGs from Playwright captures in Phase 10 under assets/screenshots/ -->
_Screenshots will land here once Phase 10 Playwright captures are committed._

## Learn more

- [Architecture](architecture/container-topology.md)
- [Courses](courses/index.md) — narrated Asciinema tracks for operators, plugin authors, contributors, and security/ops.
- [Constitution](constitution.md)
- [Contributing](developer-guide/contributing.md)
