// TrainPlex Playwright config — Week 8 Step 9.3 (E2E smoke).
//
// Three browser projects so we catch:
//   * Chrome desktop  — primary admin & reviewer surface (1280×720)
//   * Mobile Safari   — trainer PWA on iPhone 12 viewport (390×844)
//   * Firefox desktop — independent rendering engine sanity
//
// The Mobile Safari emulation runs on top of Chromium-WebKit; it is
// good enough for the layout assertions in `06_pwa_install.spec.ts`.
// A real iOS run lives in BrowserStack and is fired manually pre-cutover.
//
// Why these three and not "all browsers": every additional engine adds
// ~3min to CI and our failure modes show up cross-engine, not single.

import { defineConfig, devices } from '@playwright/test';

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:8090';

export default defineConfig({
  testDir: './specs',
  timeout: 60_000,
  expect: {
    // Web-first assertions retry up to 10s. The trainer batch endpoint
    // can be the slowest path on cold container start; 10s covers it.
    timeout: 10_000,
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['junit', { outputFile: 'reports/junit.xml' }],
    ['line'],
  ],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    // The Django container honours `Accept-Language` for the i18n
    // middleware; default to English so locale-toggle tests are explicit.
    locale: 'en-IN',
    timezoneId: 'Asia/Kolkata',
    // Trust the dev/staging cert; CI host issues a self-signed for the
    // ephemeral env so we'd otherwise need to wire trust stores.
    ignoreHTTPSErrors: true,
  },
  projects: [
    {
      name: 'chromium-desktop',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: 'mobile-safari',
      // Use Mobile Safari device profile (Playwright runs it under WebKit).
      use: { ...devices['iPhone 12'] },
    },
    {
      name: 'firefox-desktop',
      use: {
        ...devices['Desktop Firefox'],
        viewport: { width: 1280, height: 720 },
      },
    },
  ],
  webServer: process.env.E2E_SKIP_WEBSERVER
    ? undefined
    : {
        // Boots the dev container for local runs. CI uses the deployed
        // staging host and sets E2E_SKIP_WEBSERVER=1.
        command: 'docker compose up -d',
        url: BASE_URL,
        timeout: 180_000,
        reuseExistingServer: !process.env.CI,
        stdout: 'pipe',
        stderr: 'pipe',
      },
});
