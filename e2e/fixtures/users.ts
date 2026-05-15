// Synthetic e2e user fixtures — Week 8.
//
// Real trainer emails NEVER live in the e2e suite; staging is reseeded
// from this file before each run via `e2e/scripts/seed_users.sh`
// (out of scope for this commit — Phase 2 ships the seeder).
//
// Founder rule honoured: no personal mobile in any test data.

export const TEST_USERS = {
  admin: {
    email: 'e2e-admin@loadtest.trainplex.in',
    password: 'E2E2026Admin!',
    role: 'admin',
  },
  trainer: {
    email: 'e2e-trainer@loadtest.trainplex.in',
    password: 'E2E2026Trainer!',
    role: 'trainer',
  },
  reviewer: {
    email: 'e2e-reviewer@loadtest.trainplex.in',
    password: 'E2E2026Reviewer!',
    role: 'reviewer',
  },
  qaLead: {
    email: 'e2e-qa@loadtest.trainplex.in',
    password: 'E2E2026QA!',
    role: 'qa_lead',
  },
};

/**
 * Helper: log a user in via the Django login form and return when the
 * UI has settled to the post-login route.
 */
import type { Page } from '@playwright/test';

export async function loginUI(
  page: Page,
  user: { email: string; password: string },
): Promise<void> {
  await page.goto('/user/login/');
  await page.fill('input[name="email"]', user.email);
  await page.fill('input[name="password"]', user.password);
  await page.click('button[type="submit"], input[type="submit"]');
  // Post-login lands either on the projects index (admin) or the trainer
  // batch view; we just wait for the login form to disappear.
  await page.waitForURL((url) => !url.pathname.endsWith('/user/login/'));
}
