// Hindi UI smoke — Week 8 Step 9.3.
//
// Verifies the localisation toggle works end-to-end:
//   1. login (lands on the default English UI)
//   2. switch language to Hindi (hi)
//   3. assert Devanagari script renders + nav strings translated
//   4. toggle back to English + assert it sticks
//
// We don't assert *exact* string equality across all keys — the i18n
// catalog is fluid and we'd churn this test on every copy tweak. We
// instead check (a) the lang attribute, (b) at least one Devanagari
// character renders in a known header, (c) round-trip works.

import { test, expect } from '@playwright/test';
import { TEST_USERS, loginUI } from '../fixtures/users';

function containsDevanagari(text: string): boolean {
  // Unicode block U+0900 .. U+097F covers Devanagari.
  return /[ऀ-ॿ]/.test(text);
}

test.describe('Hindi UI toggle', () => {
  test('switch to hi → Devanagari renders → switch back', async ({ page }) => {
    await loginUI(page, TEST_USERS.trainer);

    // Default lang attribute.
    let lang = await page.locator('html').getAttribute('lang');
    expect(lang).toMatch(/^en/);

    // The language toggle lives in the top-right user menu (Phase 1
    // adds a dropdown with `data-testid="lang-toggle"`).
    await page.getByTestId('user-menu').click();
    await page.getByTestId('lang-toggle-hi').click();

    // After click, the page re-renders with `lang="hi"`.
    await expect(page.locator('html')).toHaveAttribute('lang', /^hi/);

    // The trainer batch header is translated. We don't pin the exact
    // string (copy may change); we only verify Devanagari is present.
    const headerText = await page.getByTestId('batch-header').innerText();
    expect(containsDevanagari(headerText)).toBe(true);

    // Round-trip.
    await page.getByTestId('user-menu').click();
    await page.getByTestId('lang-toggle-en').click();
    await expect(page.locator('html')).toHaveAttribute('lang', /^en/);
    const headerTextEn = await page.getByTestId('batch-header').innerText();
    expect(containsDevanagari(headerTextEn)).toBe(false);
  });

  test('logged-out login page also honours hi cookie', async ({ page, context }) => {
    // Pre-set the cookie that the language toggle would have set.
    await context.addCookies([
      {
        name: 'django_language',
        value: 'hi',
        url: process.env.E2E_BASE_URL || 'http://localhost:8090',
      },
    ]);
    await page.goto('/user/login/');
    const labelText = await page.locator('label[for="id_email"], label[for="email"]').first().innerText();
    expect(containsDevanagari(labelText)).toBe(true);
  });
});
