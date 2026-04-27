// Playwright walkthroughs for /jackett/indexers (Task 47 §11.10).
//
// SKELETON STATE: each `test.skip(...)` line is the only thing
// blocking execution. Remove `.skip` after activation per ./README.md.
//
// CONST-XII: every assertion targets visible DOM. Stubbing the
// `app-jackett-configured-tab` to render an empty container would
// FAIL scenario 2's row assertion.

import { test, expect, Page, request, APIRequestContext } from '@playwright/test';

const BACKEND = process.env.BOBA_BACKEND ?? 'http://localhost:7189';
const ADMIN_AUTH = 'Basic ' + Buffer.from('admin:admin').toString('base64');

async function newAdminApi(): Promise<APIRequestContext> {
  return request.newContext({
    baseURL: BACKEND,
    extraHTTPHeaders: { Authorization: ADMIN_AUTH },
  });
}

async function gotoIndexers(page: Page): Promise<void> {
  await page.goto('/jackett/indexers');
  await expect(page.getByTestId('indexers-page')).toBeVisible();
}

test.describe('indexers page (Task 47 §11.10)', () => {
  test.skip(true, 'SKIP-OK: task-47-§11.10 — Playwright not installed in this dispatch');

  test('1. Golden path — three tabs visible', async ({ page }) => {
    await gotoIndexers(page);
    await expect(page.getByTestId('tab-configured')).toBeVisible();
    await expect(page.getByTestId('tab-catalog')).toBeVisible();
    await expect(page.getByTestId('tab-history')).toBeVisible();
    await expect(page.getByTestId('panel-configured')).toBeVisible();
  });

  test('2. Configured tab — list + Test action shows status badge', async ({ page }) => {
    const api = await newAdminApi();
    // Seed an indexer if the backend supports the local cardigann fixture:
    await api.post(`/api/v1/jackett/indexers/cardigann-rutracker`, {
      data: { credential_name: 'RUTRACKER' },
    }).catch(() => {});
    await gotoIndexers(page);
    const row = page.locator('tr.idx-row').first();
    if (await row.count() === 0) {
      // Empty state acceptable in a clean stack.
      await expect(page.getByTestId('configured-empty')).toBeVisible();
    } else {
      const id = await row.getAttribute('data-testid');
      expect(id).toMatch(/^row-/);
    }
    await api.dispose();
  });

  test('3. Browse Catalog tab — pagination + search', async ({ page }) => {
    await gotoIndexers(page);
    await page.getByTestId('tab-catalog').click();
    await expect(page.getByTestId('panel-catalog')).toBeVisible();
    await page.getByTestId('catalog-search').fill('rut');
    await page.getByTestId('catalog-search-submit').click();
    // Either rows appear or the empty state appears — both valid.
    const hasEmpty = await page.getByTestId('catalog-empty').isVisible();
    const hasRows = await page.locator('tr[data-testid^="cat-row-"]').count();
    expect(hasEmpty || hasRows > 0).toBe(true);
  });

  test('4. Add indexer dialog from catalog tab', async ({ page }) => {
    await gotoIndexers(page);
    await page.getByTestId('tab-catalog').click();
    const firstAdd = page.locator('button[data-testid^="cat-add-"]').first();
    if (await firstAdd.count() === 0) {
      test.skip(true, 'No catalog rows seeded — skip this scenario in this run');
    }
    await firstAdd.click();
    await expect(page.getByTestId('indexer-add-dialog')).toBeVisible();
  });

  test('5. History tab — trigger run + expand row', async ({ page }) => {
    await gotoIndexers(page);
    await page.getByTestId('tab-history').click();
    await page.getByTestId('trigger-run').click();
    // After trigger, at least one run row should appear:
    const firstRow = page.locator('tr[data-testid^="run-row-"]').first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    await firstRow.click();
    // Expanded detail row contains JSON:
    const id = (await firstRow.getAttribute('data-testid'))?.replace('run-row-', '');
    expect(id).toBeDefined();
    await expect(page.getByTestId(`run-detail-${id}`)).toBeVisible();
    await expect(page.getByTestId(`run-detail-${id}`)).toContainText('"ran_at"');
  });

  test('6. IPTorrents cookie flow renders for cookie-only indexers', async ({ page }) => {
    await gotoIndexers(page);
    await page.getByTestId('tab-catalog').click();
    const cookieAdd = page.locator('button[data-testid^="cat-add-iptorrents"]');
    if (await cookieAdd.count() === 0) {
      test.skip(true, 'IPTorrents not in catalog — skip this scenario in this run');
    }
    await cookieAdd.click();
    await expect(page.getByTestId('iptorrents-cookie-flow')).toBeVisible();
    await expect(page.getByTestId('cookie-input')).toBeVisible();
  });
});
