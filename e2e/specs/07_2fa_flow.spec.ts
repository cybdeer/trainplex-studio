// 2FA enrollment + challenge — Week 8 Step 9.3.
//
// Verifies the admin TOTP path:
//   1. login as admin (no 2FA yet)
//   2. enroll TOTP — server returns secret + QR
//   3. derive TOTP from secret (using a deterministic time)
//   4. confirm enrollment
//   5. logout
//   6. login again — gets the OTP challenge page
//   7. enter computed code → success
//   8. logout + login + use one backup code → success
//
// We use the `otplib` HOTP/TOTP routine built into the standard
// library (`crypto`) instead of pulling a dependency — the algorithm
// is RFC 6238 with SHA-1 / 30s window.

import { test, expect } from '@playwright/test';
import { createHmac } from 'node:crypto';
import { TEST_USERS, loginUI } from '../fixtures/users';

/**
 * Compute the TOTP value for the given base32 secret + unix-second time.
 * Re-implements RFC 6238 to avoid bringing in `otplib` for one test.
 */
function totp(base32Secret: string, atSec: number = Math.floor(Date.now() / 1000)): string {
  // Decode base32.
  const cleaned = base32Secret.replace(/=+$/, '').toUpperCase();
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const ch of cleaned) {
    const idx = alphabet.indexOf(ch);
    if (idx < 0) continue;
    bits += idx.toString(2).padStart(5, '0');
  }
  const bytes = Buffer.alloc(Math.floor(bits.length / 8));
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(bits.slice(i * 8, i * 8 + 8), 2);
  }
  // HOTP counter = floor(atSec / 30).
  const counter = Math.floor(atSec / 30);
  const counterBuf = Buffer.alloc(8);
  counterBuf.writeBigUInt64BE(BigInt(counter));
  const hmac = createHmac('sha1', bytes).update(counterBuf).digest();
  const offset = hmac[hmac.length - 1] & 0xf;
  const codeInt =
    ((hmac[offset] & 0x7f) << 24) |
    ((hmac[offset + 1] & 0xff) << 16) |
    ((hmac[offset + 2] & 0xff) << 8) |
    (hmac[offset + 3] & 0xff);
  return (codeInt % 10 ** 6).toString().padStart(6, '0');
}

test.describe('2FA enrollment + challenge', () => {
  test('admin enrolls TOTP, then logs in with code', async ({ page, context }) => {
    await loginUI(page, TEST_USERS.admin);
    await page.goto('/users/me/security');

    // Click "Enroll 2FA".
    await page.getByTestId('enroll-totp').click();

    // The setup page exposes the raw base32 secret in a `data-secret`
    // attribute for easier copy/paste (also useful for tests).
    const secret = await page
      .getByTestId('totp-secret')
      .getAttribute('data-secret');
    expect(secret).toBeTruthy();

    // Enter the current code.
    await page.fill('input[name="totp_code"]', totp(secret!));
    await page.getByRole('button', { name: /confirm enrollment/i }).click();
    await expect(page.getByRole('status')).toContainText(/enrolled|enabled/i);

    // Grab the backup codes so we can use one later.
    const backupCodes = await page
      .getByTestId('backup-codes')
      .locator('li')
      .allInnerTexts();
    expect(backupCodes.length).toBeGreaterThanOrEqual(8);

    // Sign out + sign back in. Expect challenge.
    await page.getByRole('button', { name: /logout/i }).click();
    await page.goto('/user/login/');
    await page.fill('input[name="email"]', TEST_USERS.admin.email);
    await page.fill('input[name="password"]', TEST_USERS.admin.password);
    await page.click('button[type="submit"]');

    // OTP challenge page.
    await expect(page).toHaveURL(/\/auth\/2fa/);
    await page.fill('input[name="totp_code"]', totp(secret!));
    await page.click('button[type="submit"]');

    // Now in.
    await expect(page).not.toHaveURL(/\/auth\/2fa/);

    // Logout + log in again with a backup code.
    await page.getByRole('button', { name: /logout/i }).click();
    await page.goto('/user/login/');
    await page.fill('input[name="email"]', TEST_USERS.admin.email);
    await page.fill('input[name="password"]', TEST_USERS.admin.password);
    await page.click('button[type="submit"]');
    await page.click('text=/use a backup code/i');
    await page.fill('input[name="backup_code"]', backupCodes[0].trim());
    await page.click('button[type="submit"]');
    await expect(page).not.toHaveURL(/\/auth\/2fa/);
  });
});
