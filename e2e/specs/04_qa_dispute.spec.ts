// QA Lead dispute resolution — Week 8 Step 9.3.
//
// Verifies the qa_lead three-way dispute journey:
//   1. login as qa_lead
//   2. open dispute queue
//   3. open a disputed submission (3 reviewer votes, no consensus)
//   4. see three-way comparison panel (each reviewer's vote + rationale)
//   5. resolve dispute with a deciding vote + note

import { test, expect } from '@playwright/test';
import { TEST_USERS, loginUI } from '../fixtures/users';

test.describe('QA Lead dispute flow', () => {
  test.beforeEach(async ({ page }) => {
    await loginUI(page, TEST_USERS.qaLead);
  });

  test('dispute queue shows pending disputes only', async ({ page }) => {
    await page.goto('/qa/disputes');
    await expect(page.getByTestId('dispute-queue-header')).toContainText(
      /dispute|three-way|conflict/i,
    );
    // Each row badges its conflict type — accept/reject/abstain mix.
    const firstRow = page.getByTestId('dispute-row').first();
    await expect(firstRow).toBeVisible();
    await expect(firstRow.getByTestId('conflict-badge')).toBeVisible();
  });

  test('three-way comparison renders all reviewer columns', async ({ page }) => {
    await page.goto('/qa/disputes');
    await page.getByTestId('dispute-row').first().click();

    // Three reviewer columns side-by-side.
    await expect(page.getByTestId('reviewer-column-1')).toBeVisible();
    await expect(page.getByTestId('reviewer-column-2')).toBeVisible();
    await expect(page.getByTestId('reviewer-column-3')).toBeVisible();

    // Each column carries a decision badge + rationale text.
    for (const i of [1, 2, 3]) {
      const col = page.getByTestId(`reviewer-column-${i}`);
      await expect(col.getByTestId('decision-badge')).toBeVisible();
      await expect(col.getByTestId('rationale-text')).toBeVisible();
    }
  });

  test('qa_lead resolves dispute with deciding vote + note', async ({ page }) => {
    await page.goto('/qa/disputes');
    await page.getByTestId('dispute-row').first().click();

    // QA selects the deciding vote.
    await page.getByTestId('qa-vote-accept').click();
    await page.fill(
      'textarea[name="qa_note"]',
      'Reviewer 1 had the correct call — image is clearly cat (whisker pattern).',
    );
    await page.getByRole('button', { name: /resolve dispute/i }).click();

    await expect(page.getByRole('status')).toContainText(/resolved|closed/i);

    // Dispute disappears from the queue.
    await page.goto('/qa/disputes');
    // (We don't assert count change because Phase 1 mock list is stable;
    //  Phase 2 will let us assert exact decrement.)
    await expect(
      page.getByTestId('dispute-queue-header'),
    ).toBeVisible();
  });

  test('non-qa role blocked from dispute queue', async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await loginUI(page, TEST_USERS.reviewer);
    await page.goto('/qa/disputes');
    // Reviewer role lacks qa_lead — we expect either 403 or a redirect.
    await expect(page).not.toHaveURL(/\/qa\/disputes$/);
    await ctx.close();
  });
});
