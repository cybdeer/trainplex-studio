// Trainer happy path — Week 8 Step 9.3.
//
// Verifies the most-used trainer journey:
//   1. login
//   2. open the batch view
//   3. open a task in the editor
//   4. submit an answer
//   5. see the batch progress increment
//
// This spec MUST keep passing across every cutover and every release.
// If it ever flakes on the cutover branch, the cutover is aborted.

import { test, expect } from '@playwright/test';
import { TEST_USERS, loginUI } from '../fixtures/users';

test.describe('Trainer flow — login through batch completion', () => {
  test('logs in, opens batch, submits one task, sees count update', async ({
    page,
  }) => {
    await loginUI(page, TEST_USERS.trainer);

    // Batch view shows "10 tasks" headline. Phase 1 mock returns 10
    // deterministically; Phase 2 wires real assignment but the count
    // header stays the contract.
    await page.goto('/trainer/batch');
    await expect(page.getByTestId('batch-task-count')).toContainText('10');

    // Open the first task. The list uses a stable testid `task-row-<idx>`.
    await page.getByTestId('task-row-0').click();

    // The editor renders inside an iframe (label-studio-frontend bundle).
    // We assert the iframe loaded — the per-task answer UI is exercised
    // by the unit tests, not E2E.
    const editorFrame = page.frameLocator('iframe[name="lsf"]');
    await expect(
      editorFrame.locator('[data-testid="lsf-root"]'),
    ).toBeVisible({ timeout: 15_000 });

    // Submit using the visible "Submit" button.
    await page.getByRole('button', { name: /submit/i }).click();

    // Network call goes to /api/v1/trainer/batch/submit. We assert the
    // success toast — anything else (silent error, 500) would fail here.
    await expect(page.getByRole('status')).toContainText(/accepted|submitted/i);

    // Batch progress chip moves from 0/10 to 1/10.
    await expect(page.getByTestId('batch-progress')).toContainText(/1\s*\/\s*10/);
  });

  test('batch-complete banner appears at 10/10', async ({ page }) => {
    await loginUI(page, TEST_USERS.trainer);
    await page.goto('/trainer/batch');

    // We don't actually submit 10 times in CI (would lock the rate
    // limiter); instead we drive a `?dev_force_complete=1` query the
    // batch view honours in staging only — wired in `views_pwa.py`.
    await page.goto('/trainer/batch?dev_force_complete=1');
    await expect(page.getByTestId('batch-complete-banner')).toBeVisible();
    await expect(page.getByTestId('batch-complete-banner')).toContainText(
      /payout|earnings|next batch/i,
    );
  });
});
