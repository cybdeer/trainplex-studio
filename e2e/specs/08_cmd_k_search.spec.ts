// Cmd+K / Ctrl+K global search — Week 8 Step 9.3.
//
// Verifies the command palette:
//   1. admin opens any page
//   2. Cmd+K (mac) / Ctrl+K (others) opens the palette
//   3. typing "Geeta" returns trainer results
//   4. picking a result navigates to the trainer profile
//   5. Esc closes the palette

import { test, expect } from '@playwright/test';
import { TEST_USERS, loginUI } from '../fixtures/users';

const ACCEL_KEY = process.platform === 'darwin' ? 'Meta' : 'Control';

test.describe('Cmd+K global search palette', () => {
  test.beforeEach(async ({ page }) => {
    await loginUI(page, TEST_USERS.admin);
    await page.goto('/admin/dashboard');
  });

  test('palette opens on Cmd+K and closes on Esc', async ({ page }) => {
    await page.keyboard.press(`${ACCEL_KEY}+KeyK`);
    await expect(page.getByTestId('cmd-k-palette')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('cmd-k-palette')).not.toBeVisible();
  });

  test('typing "Geeta" returns at least one trainer result', async ({ page }) => {
    await page.keyboard.press(`${ACCEL_KEY}+KeyK`);
    await page.fill('[data-testid="cmd-k-input"]', 'Geeta');

    // Phase 1 mock seeds a trainer named "Geeta" in the search dataset.
    const results = page.getByTestId('cmd-k-result');
    await expect(results.first()).toBeVisible({ timeout: 5_000 });
    const firstText = await results.first().innerText();
    expect(firstText.toLowerCase()).toContain('geeta');
  });

  test('selecting a result navigates to its detail page', async ({ page }) => {
    await page.keyboard.press(`${ACCEL_KEY}+KeyK`);
    await page.fill('[data-testid="cmd-k-input"]', 'Geeta');
    await page.keyboard.press('Enter');

    // Lands on /admin/trainers/<id> or /users/<id> depending on routing.
    await expect(page).toHaveURL(/\/(admin\/trainers|users|admin\/users)\/[a-zA-Z0-9-]+/);
  });

  test('arrow keys move the highlight + Enter selects', async ({ page }) => {
    await page.keyboard.press(`${ACCEL_KEY}+KeyK`);
    await page.fill('[data-testid="cmd-k-input"]', 'project');

    // Arrow down once + enter. The first focused result's testid carries
    // an `aria-selected="true"` attribute we can assert.
    await page.keyboard.press('ArrowDown');
    const highlighted = page.locator('[data-testid="cmd-k-result"][aria-selected="true"]');
    await expect(highlighted).toBeVisible();
    await page.keyboard.press('Enter');
    await expect(page).not.toHaveURL('/admin/dashboard');
  });

  test('multiple categories returned (trainers + projects + audit log)', async ({
    page,
  }) => {
    await page.keyboard.press(`${ACCEL_KEY}+KeyK`);
    await page.fill('[data-testid="cmd-k-input"]', 'a'); // single char → broad match

    // Categories rendered as section headers.
    await expect(page.getByTestId('cmd-k-group-trainers')).toBeVisible();
    await expect(page.getByTestId('cmd-k-group-projects')).toBeVisible();
    await expect(page.getByTestId('cmd-k-group-audit')).toBeVisible();
  });
});
