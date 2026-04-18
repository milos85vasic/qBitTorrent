# Contributor deep-dive: TDD + rebuild-reboot

Work the way this repository enforces work: a failing test first, a
minimal GREEN implementation, a mandatory rebuild-and-reboot cycle,
then the commit. Every CLAUDE.md contributor has lived this loop;
this course makes it explicit.

## Audience

Contributors opening PRs against `main`. You should already be
comfortable with Python, pytest, and basic git flows.

## Prerequisites

- A local checkout with `ruff`, `pytest`, and `podman` or `docker`
  on PATH.
- `python3 -m pytest --version` returns a version.
- You have read `CLAUDE.md` and `AGENTS.md` at least once.

## Runtime

About **10 minutes**. The rebuild-reboot step adds ~90 seconds of
container restart time on a warm host.

## What you will learn

- The TDD cadence mandated by `CLAUDE.md`:
  RED → watch fail → GREEN → **rebuild-reboot** → commit.
- The new `tests/fixtures/services.py` fixtures that replace the
  runtime `pytest.skip()` guards removed in Phase 0.3.
- Why the coverage floor in `pyproject.toml` (`fail_under`) only
  ratchets upward.
- Running the scanner bundle locally with `./scripts/scan.sh`
  before pushing, so CI does not surprise you.
- Opening a PR that the new per-job workflows can exercise
  (see `.github/workflows/`).

## Files

| File        | What it is                                      |
|-------------|--------------------------------------------------|
| `script.md` | Narration with scene markers.                    |
| `demo.sh`   | Replays: fake failing test → GREEN → reboot.     |
| `demo.cast` | Asciinema v2 recording (placeholder).            |

## Next

- Ready for security + ops? See `courses/04-security-ops/`.
- Curious about the merge service internals? `docs/architecture/`
  has the Mermaid diagrams.
