/**
 * TrainPlex PWA service-worker registration — Phase 1 Step 4.3 + 4.4.
 *
 * Responsibilities
 * ----------------
 *  1. Register `/sw.js` on app boot (skipping localhost dev where HMR
 *     fights the SW state machine).
 *  2. Poll for an SW update every 5 minutes. When a new version installs,
 *     fire a `tp-pwa-update-available` window event so the React layer
 *     can render the "नया update आ गया → रीलोड" toast.
 *  3. Bind `online` / `offline` listeners. Emits `tp-network-status` window
 *     events so the OfflineBanner + the submit-queue auto-flush hook react
 *     without each owning their own listener.
 *  4. On `online` (or first activation), client-side flush the offline
 *     submit queue (covers iOS Safari + browsers without Background Sync).
 *  5. Listen for `tp-submit-flushed` SW → client messages so the BatchPage
 *     can pop a toast like "Synced N pending tasks".
 *
 * Why a separate module
 * ---------------------
 * `main.tsx` is the boot path and is already heavy with i18n + analytics +
 * the command-palette mount. Keeping PWA registration in its own module
 * keeps tree-shaking honest: a dev build that imports this file with the
 * `enabled: false` guard still costs ~2KB instead of pulling the entire
 * SW codepath onto the critical path.
 */

import { flushQueue } from "@humansignal/app-common/offline/submit-queue";

const UPDATE_POLL_MS = 5 * 60 * 1000; // 5 minutes
const SW_URL = "/sw.js";

/** Detect dev mode: skip SW so webpack-dev-server HMR works cleanly. */
function shouldRegister(): boolean {
  if (typeof window === "undefined") return false;
  if (!("serviceWorker" in navigator)) return false;
  // Dev / Storybook host — never register.
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1" || host.endsWith(".local")) {
    return false;
  }
  return true;
}

type NetworkStatusDetail = { online: boolean };

function emit<T>(name: string, detail: T) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

function onOnline() {
  emit<NetworkStatusDetail>("tp-network-status", { online: true });
  // Client-side flush — runs alongside Background Sync. Idempotent: the
  // SW + the client both call /submit; the server's idempotency key (the
  // task_id) on the bulk-submit endpoint ensures at-most-once delivery.
  flushQueue().catch(() => {
    // The submit-queue module already handles retries + backoff.
  });
}

function onOffline() {
  emit<NetworkStatusDetail>("tp-network-status", { online: false });
}

function bindNetworkListeners() {
  if (typeof window === "undefined") return;
  window.addEventListener("online", onOnline);
  window.addEventListener("offline", onOffline);
}

function bindSwMessageListener() {
  if (typeof navigator === "undefined" || !navigator.serviceWorker) return;
  navigator.serviceWorker.addEventListener("message", (event) => {
    const data = event.data || {};
    if (data.type === "tp-submit-flushed") {
      emit<{ task_id: number | null }>("tp-submit-flushed", {
        task_id: data.task_id ?? null,
      });
    }
  });
}

function bindUpdateLifecycle(registration: ServiceWorkerRegistration) {
  registration.addEventListener("updatefound", () => {
    const installing = registration.installing;
    if (!installing) return;
    installing.addEventListener("statechange", () => {
      if (installing.state === "installed" && navigator.serviceWorker.controller) {
        // A new SW has installed alongside the old controller — alert React.
        emit("tp-pwa-update-available", {
          activate: () => {
            installing.postMessage({ type: "tp-skip-waiting" });
            // The new SW will fire `controllerchange`; the listener below
            // reloads the page so the new shell takes over.
          },
        });
      }
    });
  });

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    // Hard-reload exactly once. A flag guards against an infinite reload
    // loop if the user has multiple tabs open and the SW swaps mid-flight.
    if ((window as unknown as { __tpSwReloaded?: boolean }).__tpSwReloaded) {
      return;
    }
    (window as unknown as { __tpSwReloaded?: boolean }).__tpSwReloaded = true;
    window.location.reload();
  });
}

export async function registerPwaServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!shouldRegister()) return null;
  try {
    const registration = await navigator.serviceWorker.register(SW_URL, {
      scope: "/",
    });
    bindUpdateLifecycle(registration);
    // Poll for updates so we don't strand trainers on a stale bundle when
    // they keep the tab open all day. The browser also runs its own 24h
    // update check; the 5-min cadence is a deliberate floor for ops.
    setInterval(() => {
      registration.update().catch(() => {});
    }, UPDATE_POLL_MS);
    return registration;
  } catch (_err) {
    // Registration failure shouldn't crash the app — we degrade to a
    // network-only SPA. The error is logged on the browser console only.
    // eslint-disable-next-line no-console
    console.warn("[TrainPlex PWA] SW registration failed", _err);
    return null;
  }
}

/**
 * Wire up the full PWA lifecycle. Call once from `main.tsx`. Idempotent —
 * a second call is a no-op because the SW registration itself is keyed by
 * URL + scope.
 */
export function initTrainPlexPwa(): void {
  bindNetworkListeners();
  bindSwMessageListener();
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    // App booted offline — let the OfflineBanner render on first paint.
    onOffline();
  }
  registerPwaServiceWorker().catch(() => {
    // Already logged inside registerPwaServiceWorker.
  });
}
