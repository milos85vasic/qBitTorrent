# Security and operations

The operational story: threat model, scanner bundle, credential
hygiene, and the observability stack that ships next to the main
containers.

## Audience

Operators running qBittorrent-Fixed in shared or long-lived
environments. Also useful for contributors landing security-sensitive
changes.

## Prerequisites

- Finished `courses/01-operator/` or equivalent hands-on experience.
- `./scripts/scan.sh` executable in the checkout.
- The optional observability stack (Grafana + Prometheus) starts via
  `docker-compose.quality.yml`; this course walks through reading its
  dashboards, not installing it.

## Runtime

About **9 minutes**. The partial scan (`pip-audit` + `ruff`) runs in
~20 seconds; the full `--all` scan takes longer and is narrated but
not executed in the demo.

## What you will learn

- The in-scope threats: tracker credentials, the hardcoded
  `admin/admin` qBittorrent WebUI login, IPTorrents freeleech-only
  constraint.
- Running `./scripts/scan.sh --all` locally and what each scanner
  catches (ruff, bandit, pip-audit, gitleaks, trivy, semgrep,
  sonar).
- Reading SARIF outputs in `artifacts/scans/` — the canonical
  machine-readable format CI consumes.
- Rotating tracker credentials via `.env` without restarting
  everything.
- Encryption at rest via Fernet (Phase 2.3 — flagged as **pending**).
- Grafana quickstart for the observability stack.

## Files

| File        | What it is                                            |
|-------------|-------------------------------------------------------|
| `script.md` | Narration with scene markers.                         |
| `demo.sh`   | Replays: partial scan + reading artifacts.            |
| `demo.cast` | Asciinema v2 recording (placeholder).                 |

## Next

- For the plugin-author story, see `courses/02-plugin-author/`.
- For contributor hygiene including `./scripts/scan.sh` usage, see
  `courses/03-contributor/`.
