# Playwright E2E walkthroughs (Task 47 §11.10)

This directory ships a **skeleton** for the Playwright walkthroughs the
boba-jackett DoD asks for. The skeleton currently uses `test.skip` for
each scenario; the spec bodies are filled in but blocked behind the
skip until Playwright is actually installed and the dev server +
boba-jackett backend are running.

## Why skeleton instead of a live run in this dispatch

`@playwright/test` + the chromium download is ~150 MB of disk and
adds 20-30 s to `npm ci`. Per CONST-XII this is acceptable as long
as the placeholder tests cannot silently bluff a green CI: every
`test.skip(...)` carries an inline `SKIP-OK: task-47-§11.10` comment
the project's lint/grep can flag, and once Playwright is installed,
removing each `test.skip(...)` line is the only step needed to turn
the placeholder into a real assertion run.

## To activate (one-time)

```bash
cd frontend
npm install -D @playwright/test
npx playwright install chromium
# Make sure the dev server is up:
npm run start &           # http://localhost:4200
# Make sure boba-jackett is up:
make boba-jackett-up      # or whatever the orchestrator script is
# Then run:
npx playwright test
```

The `playwright.config.ts` already points `webServer` at
`http://localhost:4200` and `use.baseURL` at the same. `BOBA_BACKEND`
defaults to `http://localhost:7189`. Each spec asserts on
`page.locator(...)` against on-screen DOM — no `expect(true).toBe(true)`
or status-code-only checks (CONST-XII).

## DoD remaining

Treat this as **DONE_WITH_CONCERNS**: skeleton + setup instructions
are present, but the actual live walkthrough run is deferred to a
follow-up patch that installs Playwright in the npm workspace and
removes each `test.skip(...)`. The plan's §11.10 acceptance criteria
("manually verified in browser via Playwright walkthroughs") cannot
be claimed PASS until that run is paste-attached to the PR.
