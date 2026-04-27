// Playwright config skeleton — see ./README.md for activation steps.
//
// CONST-XII: every test in this directory MUST assert on user-visible
// DOM (page.locator(...).toContainText / toBeVisible / count). A green
// run with assertions only on `page.url()` or response.status() would
// be a bluff — the test must inspect what the operator's eyes see.
import { defineConfig, devices } from '@playwright/test';

const APP_URL = process.env.BOBA_FRONTEND_URL ?? 'http://localhost:4200';
const BACKEND_URL = process.env.BOBA_BACKEND ?? 'http://localhost:7189';

export default defineConfig({
  testDir: '.',
  testMatch: /.*\.spec\.ts$/,
  fullyParallel: false, // backend state is shared (autoconfig runs, etc.)
  workers: 1,
  retries: 0,
  reporter: [['list']],
  timeout: 30_000,
  use: {
    baseURL: APP_URL,
    extraHTTPHeaders: {
      // Surface backend in the env so spec files can construct API URLs.
      'X-Boba-Backend': BACKEND_URL,
    },
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
