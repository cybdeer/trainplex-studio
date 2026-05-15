// Reviewer happy path — Week 8 Step 9.3.
//
// Verifies the reviewer journey:
//   1. login as reviewer
//   2. open review queue
//   3. inspect a submission in the split-screen view (original + answer)
//   4. submit a consensus vote
//   5. see the queue length decrement

import { test, expect } from '@playwright/test';
import { TEST_USERS, loginUI } from '../fixtures/users';

test.describe('Reviewer flow — queue through consensus vote', () => {
  test.beforeEach(async ({ page }) => {
    await loginUI(page, TEST_USERS.reviewer);
  });

  test('reviewer queue loads + displays pending items', async ({ page }) => {
    await page.goto('/reviewer/queue');
    await expect(page.getByTestId('queue-header')).toContainText(/review queue/i);
    // Phase 1 mock seeds at least 5 items.
    await expect(
      page.getByTestId('queue-item').first(),
    ).toBeVisible();
  });

  test('split-screen review opens + shows task + answer side by side', async ({
    page,
  }) => {
    await page.goto('/reviewer/queue');
    await page.getByTestId('queue-item').first().click();

    // Split screen has two stable panes.
    await expect(page.getByTestId('review-pane-task')).toBeVisible();
    await expect(page.getByTestId('review-pane-answer')).toBeVisible();

    // Both panes have content.
    await expect(page.getByTestId('review-pane-task')).not.toBeEmpty();
    await expect(page.getByTestId('review-pane-answer')).not.toBeEmpty();
  });

  test('consensus accept submits + dequeues the item', async ({ page }) => {
    await page.goto('/reviewer/queue');

    const startCountText = await page
      .getByTestId('queue-count-badge')
      .innerText();
    const startCount = parseInt(startCountText.replace(/\D/g, ''), 10);

    await page.getByTestId('queue-item').first().click();
    await page.getByRole('button', { name: /accept/i }).click();

    // Toast appears.
    await expect(page.getByRole('status')).toContainText(/accepted|recorded/i);

    // Queue length decremented by exactly 1.
    await page.goto('/reviewer/queue');
    const endCountText = await page.getByTestId('queue-count-badge').innerText();
    const endCount = parseInt(endCountText.replace(/\D/g, ''), 10);
    expect(endCount).toBe(startCount - 1);
  });

  test('consensus reject requires a note', async ({ page }) => {
    await page.goto('/reviewer/queue');
    await page.getByTestId('queue-item').first().click();
    await page.getByRole('button', { name: /reject/i }).click();

    // Validation banner appears because note is empty.
    await expect(page.getByRole('alert')).toContainText(/note|reason/i);

    // Filling the note and re-submitting works.
    await page.fill('textarea[name="note"]', 'Image is blurred — cannot label');
    await page.getByRole('button', { name: /submit reject/i }).click();
    await expect(page.getByRole('status')).toContainText(/rejected|recorded/i);
  });
});
