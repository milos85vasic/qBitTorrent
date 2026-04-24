<!--
Sync Impact Report:
- Version change: 1.1.0 → 1.2.0
- Principles defined:
  9. Test-Driven Development (NEW)
  10. Hermetic Test Discipline (NEW)
  11. Minimal Source Commentary (NEW)
- Added sections: Core Principles (3 new)
- Removed sections: (none)
- Templates requiring updates:
  ✅ plan-template.md — Constitution Check section aligns; no changes needed
  ✅ spec-template.md — Requirements structure compatible; no changes needed
  ✅ tasks-template.md — Task phases compatible; no changes needed
  ✅ checklist-template.md — Generic template; no changes needed
  ✅ agent-file-template.md — Generic template; no changes needed
- Follow-up TODOs: (none)
-->

# qBitTorrent Platform Constitution

## Core Principles

### I. Container-First Architecture

All services MUST run as containerized workloads orchestrated via
`docker-compose.yml`. The platform comprises exactly two container
services — `qbittorrent` (the BitTorrent client) and `download-proxy`
(the download proxy) — plus one optional host process (`webui-bridge.py`).

- Every service MUST be defined in `docker-compose.yml` with explicit
  image tags, port mappings, volume mounts, and restart policies.
- New services MUST NOT be added without updating `docker-compose.yml`
  and all lifecycle scripts (`start.sh`, `stop.sh`).
- Volume mounts MUST use the shared `tmp/` directory for inter-container
  file exchange (torrent files, temporary downloads).
- Network mode MUST be `host` for both containers to enable seamless
  localhost communication.
- The `config/` directory tree is the single source of truth for runtime
  configuration and MUST NOT contain secrets.

**Rationale**: Container-first ensures reproducible deployments,
environmental consistency, and clean service isolation. Podman/Docker
duality demands a single compose definition as the contract.

### II. Plugin Contract Integrity

Every search plugin MUST conform to the qBittorrent nova3 engine
contract. Plugins are Python classes deployed to
`config/qBittorrent/nova3/engines/`.

- Each plugin MUST define class attributes: `url`, `name`,
  `supported_categories` (dict mapping category name to ID string).
- Each plugin MUST implement `search(self, what, cat='all')` producing
  output exclusively through `novaprinter.print()`.
- Each plugin MUST implement `download_torrent(self, url)` returning
  a magnet link or file path.
- Private-tracker plugins MUST read credentials from environment
  variables using the `try: import novaprinter` optional-dependency
  pattern for standalone testability.
- Plugins MUST be validated with `python3 -m py_compile` before
  installation. Syntax-invalid plugins MUST NOT be deployed.
- The `install-plugin.sh` managed list (12 plugins) is the canonical
  set. Additional plugins in `plugins/` are community contributions
  and MUST be explicitly installed.

**Rationale**: The plugin contract is the extensibility backbone.
Violations cause silent search failures or broken downloads that are
hard to diagnose in a containerized environment.

### III. Credential & Secret Security

Credentials MUST NEVER appear in version control. The project uses a
layered environment-variable loading system with strict priority rules.

- `.env` is in `.gitignore` and MUST NEVER be committed. `.env.example`
  is the template with placeholder values only.
- Environment loading priority (first wins): shell environment →
  `./.env` → `~/.qbit.env` → container env from compose.
- Private-tracker credentials (`RUTRACKER_*`, `KINOZAL_*`,
  `NNMCLUB_*`, `IPTORRENTS_*`) MUST be loaded from environment
  variables, never hardcoded.
- WebUI credentials `admin`/`admin` are hardcoded by design in
  `start.sh`, `docker-compose.yml`, and scripts — do NOT change them.
- `.ruff_cache/` MUST be added to `.gitignore`.
- No secret values MAY appear in log output, test reports, or
  commit messages.

**Rationale**: Tracker credentials are user-specific and sensitive.
Hardcoded admin credentials are an intentional development default
documented in AGENTS.md.

### IV. Container Runtime Portability

All shell scripts MUST auto-detect the container runtime, preferring
Podman over Docker. The detection pattern is consistent across all
lifecycle scripts.

- Runtime detection order: `podman` (preferred) → `docker`.
- Compose command detection: `podman-compose` → `docker compose` →
  `docker-compose`.
- All scripts MUST use the shared pattern: `detect_container_runtime()`
  setting `CONTAINER_RUNTIME` and `COMPOSE_CMD` variables.
- File operations inside container volumes MUST account for Podman
  rootless ownership: use `podman unshare cp` when copying plugins.
- `run-all-tests.sh` currently hardcodes Podman commands — this is a
  known limitation documented in AGENTS.md.

**Rationale**: Podman is the primary target on Linux, but Docker
compatibility MUST be maintained. Consistent auto-detection prevents
user-facing errors.

### V. Private Tracker Bridge Pattern

Private-tracker downloads through the WebUI MUST be proxied through
the `webui-bridge.py` host process (port 7188), which routes requests
to `nova2dl.py` with proper authentication.

- `webui-bridge.py` is a separate host process, NOT a container.
  It MUST be started manually: `python3 webui-bridge.py`.
- The bridge intercepts download URLs matching known private tracker
domains and delegates to `nova2dl.py` for authenticated downloads.
- Direct WebUI downloads bypass `nova2dl.py` and WILL fail for
  private trackers — this is the fundamental problem the bridge solves.
- Private-tracker URL patterns are defined in `PRIVATE_TRACKERS` dict
  within `webui-bridge.py` and MUST be kept in sync with plugin
  capabilities.
- WebUI-compatible plugin variants in `plugins/webui_compatible/` are
  alternatives for environments where the bridge cannot run.

**Rationale**: qBittorrent WebUI does not natively support
authenticated torrent downloads. The bridge pattern is an architectural
necessity, not an optional enhancement.

### VI. Validation-Driven Development

All code changes MUST pass syntax validation and the test suite before
being considered complete. There is no CI pipeline — manual validation
is the only gate.

- Bash scripts MUST pass `bash -n` syntax check.
- Python files MUST pass `python3 -m py_compile` syntax check.
- The test suite (`./test.sh`, `./run-all-tests.sh`) MUST be run
  after any change to plugins, scripts, or configuration.
- Plugin installation MUST be verified with `install-plugin.sh --verify`.
- `ruff` is used informally (`.ruff_cache/` exists) but has no
  configuration file and no formal enforcement.
- There is no linter config, no type-checking pipeline, and no CI
  automation. These MAY be added but are not currently required.

**Rationale**: In a containerized multi-service platform, a broken
plugin or script causes cascading failures. Syntax validation is the
minimum gate; full test runs catch integration issues.

### VII. Operational Simplicity

The platform MUST be operable with minimal commands. Setup, start,
stop, and testing each have dedicated scripts with consistent UX.

- `setup.sh` is the one-command onboarding: creates directories,
  installs plugins, generates config, starts containers.
- `start.sh` / `stop.sh` are the lifecycle commands with documented
  flags (`-p` pull, `-s` status, `-r` remove, `--purge` clean images).
- All scripts MUST use the shared color-print helpers (`print_info`,
  `print_success`, `print_warning`, `print_error`) for consistent
  user feedback.
- All scripts MUST implement `-h, --help` with usage examples.
- Directory structure under the data directory (`Incomplete/`,
  `Torrents/All/`, `Torrents/Completed/`) is auto-created on start.
- The `config/qBittorrent/config/qBittorrent.conf` configuration file
  is auto-generated on first start. Stale configs at the wrong path
  are detected and cleaned up.

**Rationale**: The target audience is users deploying a torrent
platform, not Kubernetes operators. One-command operations reduce
support burden and onboarding friction.

### VIII. IPTorrents Freeleech Policy

IPTorrents is a ratio-sensitive private tracker. Automated downloads
MUST be freeleech-only to protect the user's ratio.

- All automated tests and download automation MUST ONLY download
  freeleech torrents from IPTorrents.
- Freeleech detection is performed by checking the `<span class="free">`
  HTML element in search results, and via the `&free=on` URL parameter
  for freeleech-only filtering.
- Freeleech results MUST be tagged with `IPTorrents [free]` in the
  `tracker_display` field of search results.
- Non-freeleech IPTorrents downloads cost upload ratio and MUST NEVER
  be triggered by automation, tests, or scheduled tasks.
- The `freeleech` boolean field on `SearchResult` MUST be present and
  accurate for all IPTorrents results.

**Rationale**: Downloading non-freeleech torrents from IPTorrents
without seeding back degrades the user's ratio and risks account
suspension. Automation must be ratio-safe by default.

### IX. Test-Driven Development

Every bug fix and feature MUST follow the TDD cycle.

- Write a failing test first (RED).
- Observe the failure to confirm the test exercises the right code path.
- Write the minimal code to make the test pass (GREEN).
- Verify the full suite still passes.
- Only then commit.

This discipline applies to Python source, plugins, shell scripts, and
frontend TypeScript. A commit that changes production code without a
corresponding test change MUST be rejected in review.

**Rationale**: TDD is the primary defence against the "green tests,
broken product" anti-pattern. Tests written after the fact validate
what the author thinks the code does, not what it actually does.

### X. Hermetic Test Discipline

The test suite is the source of truth for correctness. Tests MUST be
hermetic, well-isolated, and located in the canonical directory.

- All tests MUST live in `./tests/`, NEVER in `download-proxy/tests/`.
- Unit tests MUST be heavily mocked and MUST NOT require running
  containers.
- Integration and E2E tests MAY require running containers but MUST
  fail loudly (not skip silently) when services are unavailable.
- Coverage gate is 49% and MUST be maintained or raised. Raising the
gate requires updating `docs/COVERAGE_BASELINE.md` simultaneously.
- `sys.modules` isolation for unit tests MUST NOT leak into
  integration or E2E tests.
- Event loop state MUST NOT leak between tests; async tests MUST use
  function-scoped loops.

**Rationale**: Hermetic tests give fast feedback during development.
Leaky isolation produces flaky failures that erode trust in the suite
and hide real regressions.

### XI. Minimal Source Commentary

The merge service Python source (`download-proxy/src/`) MUST contain
NO comments or docstrings. This is an intentional project convention.

- Comments explaining "what" the code does are forbidden; the code
  must be self-explanatory.
- Comments explaining "why" a non-obvious decision was made belong in
  the commit message or in `docs/`, not in source.
- Type hints on public methods are encouraged; they serve as
  machine-readable documentation.
- Test files, plugin files, scripts, and documentation are exempt from
  this rule.

**Rationale**: Comments rot. Commit messages and living docs are the
single source of truth for design rationale. Minimal commentary forces
clarity through naming and structure.

## Security Requirements

- `.env` file MUST have `600` permissions: `chmod 600 .env`.
- All inter-container communication uses `localhost` via `network_mode:
  host`. No inter-container TLS is required.
- WebUI is exposed on port 7186 (proxy) and 7185 (direct) — both
  MUST be firewalled from public access in production deployments.
- The bridge port (7188) MUST NOT be exposed outside localhost.
- No root escalation: containers run with `PUID=1000`/`PGID=1000`.
- Empty root files (`CONFIG`, `SCRIPT`, `EOF`) MUST NOT be removed —
  they may be referenced by existing tooling.
- The `tools/` and `Upstreams/` directories contain auxiliary scripts
  and upstream references that MUST NOT be modified without explicit
  justification.

## Development Workflow & Quality Gates

### Before Every Commit

1. Run `bash -n` on all modified shell scripts.
2. Run `python3 -m py_compile` on all modified Python files.
3. Run `./test.sh --quick` to validate basic setup integrity.
4. Verify no secrets appear in `git diff` output.

### Before Every Release

1. Run `./run-all-tests.sh` — the full suite MUST pass.
2. Run `./install-plugin.sh --verify` — all 12 managed plugins MUST
   be installed and syntactically valid.
3. Verify `docker-compose.yml` passes `$COMPOSE_CMD config`.
4. Update `README.md`, `PLUGIN_STATUS.md`, and `CHANGELOG.md`.

### Code Conventions

- **Bash**: `set -euo pipefail`, `[[ ]]` conditionals, quoted
  variables, `snake_case` functions, `UPPER_CASE` constants,
  4-space indent. Shared color-print helpers for all output.
- **Python**: PEP 8, type hints on public methods, `try: import
  novaprinter` pattern (optional dependency), no project-level
  `requirements.txt` — only `tests/requirements.txt`.
- **YAML/Compose**: 2-space indent, inline comments, descriptive
  service names, documented environment variables.
- **Commit messages**: Conventional commits (`feat:`, `fix:`, `docs:`,
  `test:`, `chore:`, `refactor:`).

## Governance

This constitution is the supreme governing document for the qBitTorrent
Platform project. It supersedes all other practices, conventions, and
ad-hoc decisions.

- All PRs and code reviews MUST verify compliance with these
  principles.
- Amendments require: (1) a written proposal documenting the change
  and rationale, (2) approval from the project maintainer, and
  (3) a migration plan if the change affects existing deployments.
- Complexity beyond what is described here MUST be justified in the
  PR description with reference to the specific principle it serves.
- Use `AGENTS.md` for runtime development guidance that supplements
  (but does not contradict) this constitution.
- The `CONTRIBUTING.md` file governs external contribution workflow and
  MUST remain consistent with the principles herein.

**Version**: 1.2.0 | **Ratified**: 2026-04-13 | **Last Amended**: 2026-04-24
