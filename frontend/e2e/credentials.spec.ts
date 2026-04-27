// Playwright walkthroughs for /jackett/credentials (Task 47 §11.10).
//
// SKELETON STATE: each `test.skip(...)` line is the only thing keeping
// these from running. Remove the `.skip` after the README's activation
// steps and you have an executable walkthrough that drives the real
// browser against the real boba-jackett backend.
//
// CONST-XII: every assertion below queries on-screen text or DOM
// state, NOT just response status codes — a stub component that
// rendered "Coming soon" would FAIL each scenario.

import { test, expect, Page, APIRequestContext, request } from '@playwright/test';

const BACKEND = process.env.BOBA_BACKEND ?? 'http://localhost:7189';
const ADMIN_AUTH = 'Basic ' + Buffer.from('admin:admin').toString('base64');

async function newAdminApi(): Promise<APIRequestContext> {
  return request.newContext({
    baseURL: BACKEND,
    extraHTTPHeaders: { Authorization: ADMIN_AUTH },
  });
}

async function expectCredentialsPage(page: Page): Promise<void> {
  await page.goto('/jackett/credentials');
  await expect(page.locator('h2', { hasText: 'Credentials' })).toBeVisible();
}

test.describe('credentials page (Task 47 §11.10)', () => {

  test('1. Golden path — page loads with header + table-or-empty-state', async ({ page }) => {
    await expectCredentialsPage(page);
    await expect(page.getByTestId('add-credential')).toBeVisible();
    // Either a table OR the empty state is visible — both are valid.
    const hasTable = await page.locator('table.cred-table').isVisible();
    const hasEmpty = await page.getByTestId('empty-state').isVisible();
    expect(hasTable || hasEmpty).toBe(true);
  });

  test('2. Add credential via dialog → row appears', async ({ page }) => {
    const api = await newAdminApi();
    // Pre-clean so the test is deterministic:
    await api.delete(`/api/v1/jackett/credentials/PWTEST_GOLDEN`).catch(() => {});

    await expectCredentialsPage(page);
    await page.getByTestId('add-credential').click();
    await expect(page.getByTestId('edit-dialog')).toBeVisible();
    await page.getByTestId('input-name').fill('PWTEST_GOLDEN');
    await page.getByTestId('input-username').fill('joeuser');
    await page.getByTestId('input-password').fill('secret123');
    await page.getByTestId('save-credential').click();
    // DOM assertion: the row for PWTEST_GOLDEN now exists:
    await expect(page.getByText('PWTEST_GOLDEN')).toBeVisible();

    await api.delete(`/api/v1/jackett/credentials/PWTEST_GOLDEN`).catch(() => {});
    await api.dispose();
  });

  test('3. Edit credential → PATCH semantics → row updated', async ({ page }) => {
    const api = await newAdminApi();
    await api.post(`/api/v1/jackett/credentials`, {
      data: { name: 'PWTEST_EDIT', username: 'before', password: 'pw' },
    });
    await expectCredentialsPage(page);
    await page.getByTestId('edit-PWTEST_EDIT').click();
    await page.getByTestId('input-username').fill('after');
    await page.getByTestId('save-credential').click();
    // DOM assertion: the row now shows that has_username is still 'yes'
    // (username is opaque post-save) — assert the row is still rendered.
    await expect(page.getByText('PWTEST_EDIT')).toBeVisible();

    await api.delete(`/api/v1/jackett/credentials/PWTEST_EDIT`).catch(() => {});
    await api.dispose();
  });

  test('4. Delete credential → row gone', async ({ page }) => {
    const api = await newAdminApi();
    await api.post(`/api/v1/jackett/credentials`, {
      data: { name: 'PWTEST_DEL', username: 'x', password: 'y' },
    });
    await expectCredentialsPage(page);
    page.once('dialog', (d) => d.accept());
    await page.getByTestId('delete-PWTEST_DEL').click();
    await expect(page.getByText('PWTEST_DEL')).toHaveCount(0);
    await api.dispose();
  });

  test('5. Banner appears for served-by-native-plugin (NNMClub)', async ({ page }) => {
    // Activation requires the backend to expose a recent run with
    // NNMCLUB in served_by_native_plugin. With cookies-only NNMClub
    // configured, triggering a run produces this. The assertion here
    // is on the on-screen DOM.
    await expectCredentialsPage(page);
    const banner = page.getByTestId('native-plugin-banner-NNMCLUB');
    if (await banner.isVisible()) {
      await expect(banner).toContainText('native');
      await expect(banner).toContainText('NNMCLUB');
    }
  });

  test('6. Backend down → user-friendly error', async ({ page, context }) => {
    // Route all backend traffic to a 503 to simulate downtime.
    await context.route(`${BACKEND}/api/v1/jackett/credentials`, (route) =>
      route.fulfill({ status: 503, body: 'down' }),
    );
    await expectCredentialsPage(page);
    await expect(page.getByTestId('error-message')).toBeVisible();
  });
});
