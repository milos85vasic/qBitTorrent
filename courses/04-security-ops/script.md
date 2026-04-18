# Security and operations — Narration

~9-minute walkthrough of the threat model, the scanner bundle, and
the observability stack. Matches the scene markers inside
`demo.sh`.

---

## [00:00] Intro

> This course is operational. The merge service runs trusted local
> code against untrusted remote HTML; the attack surface is small
> but real. We will cover the in-scope threats, run the scanner
> bundle locally, rotate credentials safely, and take a short tour
> of the Grafana dashboards.

## [00:20] Threat model in one minute

> Three concrete risks this project mitigates:
>
> 1. **Tracker credentials.** RuTracker and Kinozal require real
>    usernames and passwords; they live in `.env`, which is
>    `.gitignore`d and must never be committed. `tests/unit/
>    test_freeleech.py` plus the IPTorrents freeleech-only guard
>    ensure automated tests never cost ratio.
> 2. **Hardcoded WebUI login.** The qBittorrent WebUI inside the
>    container runs with `admin / admin` by design — the
>    download-proxy injects those credentials so the dashboard never
>    asks the user. `fix-qbit-password.sh` and
>    `init-qbit-password.sh` exist exactly to reset that pair after
>    an image upgrade changes it. Do **not** change the pair; change
>    your firewall instead.
> 3. **Subprocess template injection.** Plugins are imported inside
>    a subprocess via exec'd template strings. Phase 3.1 is
>    tightening the escaping; review `download-proxy/src/
>    merge_service/search.py:378` if you touch this path.

## [01:30] The scanner bundle

> `./scripts/scan.sh` is the single entry point. Flags select which
> scanners run:
>
> - `--ruff` — lint.
> - `--bandit` — Python security smells.
> - `--pip-audit` — PyPI CVE audit.
> - `--gitleaks` — commit-history secret scanner.
> - `--trivy` — container + filesystem CVE scanner.
> - `--semgrep` — rule-based static analysis.
> - `--sonar` — pushes to a local SonarQube instance.
> - `--all` — the CI-equivalent bundle.
>
> Output is SARIF under `artifacts/scans/`, one file per scanner,
> human-readable JSON. CI uploads the same artifacts.

## [02:30] Partial scan demo

> We run just pip-audit and ruff here — fast, deterministic, offline
> once the pip cache is warm.

```bash
./scripts/scan.sh --pip-audit --ruff
ls artifacts/scans/
```

## [03:30] Reading SARIF

> SARIF is JSON. Each finding is a `result` entry with `ruleId`,
> `level` (`error`, `warning`, `note`), a `locations` array with
> file/line, and a `message.text`. Use `jq` to extract triage
> candidates.

```bash
jq '.runs[].results | length' artifacts/scans/pip-audit.sarif
jq '[.runs[].results[] | {rule: .ruleId, msg: .message.text}]' \
   artifacts/scans/ruff.sarif | head -c 600
```

## [04:30] Rotating tracker credentials

> Credentials live in `.env`. The merge service reads them at
> startup via `download-proxy/src/config/config.py`. To rotate:
>
> 1. Edit `.env`, updating `RUTRACKER_PASSWORD` (or others).
> 2. Restart **only** the proxy container, not qBittorrent — the
>    WebUI has no tracker credentials of its own.

```bash
# Rotate and restart just the proxy (data-safe).
./stop.sh
./start.sh
```

> Never commit `.env`. `tests/unit/test_dotenv_guard.py` fails if
> the file lands in `git ls-files`.

## [05:30] Encryption at rest (Phase 2.3 — pending)

> Today, the credential file saved by the dashboard's admin
> endpoints is plaintext JSON under `config/`. Phase 2.3 of the
> completion-initiative plan introduces Fernet symmetric encryption
> with a host-derived key. Until that lands, treat `config/` as
> sensitive and restrict filesystem permissions accordingly:

```bash
chmod 700 config/
```

## [06:30] Observability quickstart

> `docker-compose.quality.yml` layers Prometheus, Grafana, and
> OpenTelemetry Collector alongside the core containers. Start it
> when you need dashboards; leave it down when you do not.

```bash
./start.sh -p
podman compose -f docker-compose.quality.yml up -d
# Grafana at http://localhost:3000, admin/admin by default.
```

> Pre-seeded dashboards: **Merge Search Overview**, **Plugin Health
> Matrix**, **SSE Throughput**, and **Scanner Status**. Adjust the
> time range in the top-right; most default to the last 15 minutes.

## [07:30] Putting it together

> A safe operator loop looks like:
>
> 1. `./scripts/scan.sh --all` weekly, or before any credential
>    rotation.
> 2. Rotate credentials via `.env`, stop-start, not image rebuild.
> 3. Watch the **Merge Search Overview** dashboard for stalled
>    trackers — a tracker whose P95 exceeds 10s is a candidate for
>    temporary removal from `install-plugin.sh`'s curated list.
> 4. Keep `config/` on a filesystem that supports POSIX mode bits
>    until Fernet at rest ships in Phase 2.3.

## [08:30] Recap

> You know the threat model, the scanner bundle, how to rotate
> credentials without a rebuild, where the Fernet-at-rest story
> will land, and how to read the Grafana dashboards. That closes
> the course track.
