// Admin happy path — Week 8 Step 9.3.
//
// Verifies the founder/admin journey:
//   1. login
//   2. land on the dashboard (with KPI tiles + top trainers + alerts)
//   3. create a project via the wizard
//   4. assign tasks to trainers via bulk-assign
//   5. see the submissions preview drawer

import { test, expect } from '@playwright/test';
import { TEST_USERS, loginUI } from '../fixtures/users';

test.describe('Admin flow — login through assignment', () => {
  test.beforeEach(async ({ page }) => {
    await loginUI(page, TEST_USERS.admin);
  });

  test('dashboard renders KPI tiles + top trainers + alerts', async ({
    page,
  }) => {
    await page.goto('/admin/dashboard');

    // KPI tiles — IDs come from `DashboardWidget` in
    // web/apps/trainplex/src/pages/admin/Dashboard.tsx.
    await expect(page.getByTestId('kpi-submissions-today')).toBeVisible();
    await expect(page.getByTestId('kpi-pay-hold')).toBeVisible();
    await expect(page.getByTestId('kpi-active-trainers')).toBeVisible();
    await expect(page.getByTestId('kpi-alerts-open')).toBeVisible();

    // Top trainers table — Phase 1 mock seeds 5 rows.
    await expect(page.getByTestId('top-trainers-table').locator('tr')).toHaveCount(
      6, // 1 header + 5 rows
    );
  });

  test('wizard creates a project end-to-end', async ({ page }) => {
    await page.goto('/admin/projects/new');

    // Step 1 — pick a template.
    await page.getByTestId('template-card-image-classification').click();
    await page.getByRole('button', { name: /next/i }).click();

    // Step 2 — fill title + dataset URL.
    await page.fill(
      'input[name="title"]',
      `e2e-project-${Date.now()}`,
    );
    await page.fill(
      'input[name="dataset_url"]',
      'https://example.com/dataset.csv',
    );
    await page.getByRole('button', { name: /next/i }).click();

    // Step 3 — pick trainers (single chip click for the e2e path).
    await page.getByTestId('trainer-chip-state-MH').click();
    await page.getByRole('button', { name: /create project|finish/i }).click();

    // Lands on the project detail page; the URL contains `/projects/<id>`.
    await expect(page).toHaveURL(/\/projects\/\d+/);
    await expect(page.getByTestId('project-title')).toContainText('e2e-project-');
  });

  test('bulk-assign filters + submits a plan', async ({ page }) => {
    await page.goto('/admin/trainers/bulk-assign');

    // Filter: Maharashtra, tier=gold, language=hi.
    await page.selectOption('select[name="state"]', 'MH');
    await page.selectOption('select[name="tier"]', 'gold');
    await page.selectOption('select[name="language"]', 'hi');
    await page.getByRole('button', { name: /preview|filter/i }).click();

    // Result table populates.
    await expect(page.getByTestId('matched-trainer-count')).toContainText(/\d+/);

    // Distribute strategy + tasks-per-trainer.
    await page.fill('input[name="tasks_per_trainer"]', '5');
    await page.selectOption('select[name="distribute_strategy"]', 'even');
    await page.getByRole('button', { name: /assign/i }).click();

    await expect(page.getByRole('status')).toContainText(/assigned|planned/i);
  });

  test('submissions preview drawer opens + filters by trainer', async ({
    page,
  }) => {
    await page.goto('/admin/dashboard');
    await page.getByTestId('submissions-preview-open').click();

    // Drawer is mounted as `role="dialog"`.
    const drawer = page.getByRole('dialog');
    await expect(drawer).toBeVisible();
    await expect(drawer.getByTestId('submission-row').first()).toBeVisible();

    // Filter by trainer id 1 — the mock dataset always has rows for id 1.
    await drawer.fill('input[name="trainer_id"]', '1');
    await drawer.getByRole('button', { name: /apply|filter/i }).click();
    await expect(drawer.getByTestId('submission-row').first()).toBeVisible();
  });
});
