# DO NOT RE-ENABLE THESE WORKFLOWS

**Owner directive (repeat, permanent):** CI in this repository is
**manual**. Do not rename `.github/workflows-disabled/` back to
`.github/workflows/`. Do not create any new `.github/workflows/*.yml`
with push / pull_request / schedule / merge_group triggers.

The only acceptable trigger anywhere in this repo is
`workflow_dispatch` (manual run from the Actions tab). Even that is
discouraged — the sanctioned path is to run `./ci.sh` locally
before pushing.

## Why

- Tracker access here depends on `.env` credentials that must never
  reach a CI runner's environment.
- The integration suite hits live private trackers — rate limits
  and freeleech rules apply; unattended runs get accounts banned.
- The owner has explicitly asked, every time this comes up, that CI
  stay manual. Respect that.

## Enforcement

`CLAUDE.md` contains the same directive as a hard contributor rule.
An automated contributor (LLM assistant included) proposing to
re-enable workflows is in violation of the project's contract.

Last updated: 2026-04-20.
