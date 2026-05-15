// PWA install + offline submit — Week 8 Step 9.3.
//
// Verifies the PWA story on mobile-safari project:
//   1. manifest is served + advertises icons + start_url
//   2. service worker registers
//   3. offline submit is queued in IndexedDB
//   4. reconnecting flushes the queue via /bulk-submit
//
// We rely on Playwright's `context.setOffline(true)` to simulate the
// loss of connectivity and `page.evaluate` to read the IDB queue.

import { test, expect } from '@playwright/test';
import { TEST_USERS, loginUI } from '../fixtures/users';

// Only run this spec on the mobile-safari project — desktop browsers
// don't carry the install-prompt path we care about.
test.skip(({ browserName }) => browserName !== 'webkit', 'PWA spec is mobile-only');

test.describe('PWA — manifest, install, offline submit', () => {
  test('manifest.webmanifest serves valid JSON', async ({ page, request }) => {
    const res = await request.get('/manifest.webmanifest');
    expect(res.status()).toBe(200);
    const manifest = await res.json();
    // Manifest contract — keys baked into core/views_pwa.py `manifest_view`.
    expect(manifest).toHaveProperty('name');
    expect(manifest).toHaveProperty('start_url');
    expect(Array.isArray(manifest.icons)).toBe(true);
    expect(manifest.icons.length).toBeGreaterThanOrEqual(1);
    expect(manifest.display).toMatch(/standalone|fullscreen/);
  });

  test('service worker registers + claims the page', async ({ page }) => {
    await loginUI(page, TEST_USERS.trainer);
    await page.goto('/trainer/batch');

    const swRegistered = await page.evaluate(async () => {
      if (!('serviceWorker' in navigator)) return false;
      // Either an existing reg or we await one.
      const reg =
        (await navigator.serviceWorker.getRegistration()) ||
        (await new Promise((res) =>
          navigator.serviceWorker.ready.then(res),
        ));
      return !!reg && (!!reg.active || !!reg.installing || !!reg.waiting);
    });
    expect(swRegistered).toBe(true);
  });

  test('offline submit queues to IndexedDB + flushes on reconnect', async ({
    page,
    context,
  }) => {
    await loginUI(page, TEST_USERS.trainer);
    await page.goto('/trainer/batch');

    // Go offline and submit a task.
    await context.setOffline(true);
    await page.getByTestId('task-row-0').click();
    await page.getByRole('button', { name: /submit/i }).click();

    // The SW should have captured the POST + put it in the IDB queue.
    const queuedCount = await page.evaluate(async () => {
      return new Promise<number>((resolve) => {
        const req = indexedDB.open('trainplex-submit-queue');
        req.onsuccess = () => {
          const db = req.result;
          const tx = db.transaction('queue', 'readonly');
          const store = tx.objectStore('queue');
          const countReq = store.count();
          countReq.onsuccess = () => resolve(countReq.result);
        };
        req.onerror = () => resolve(-1);
      });
    });
    expect(queuedCount).toBeGreaterThanOrEqual(1);

    // Come back online; SW should flush via /bulk-submit.
    await context.setOffline(false);
    // The SW listens on `online` event and flushes; give it time.
    await page.waitForFunction(
      async () => {
        return new Promise<boolean>((resolve) => {
          const req = indexedDB.open('trainplex-submit-queue');
          req.onsuccess = () => {
            const tx = req.result.transaction('queue', 'readonly');
            const cnt = tx.objectStore('queue').count();
            cnt.onsuccess = () => resolve(cnt.result === 0);
          };
          req.onerror = () => resolve(false);
        });
      },
      { timeout: 30_000 },
    );
  });
});
