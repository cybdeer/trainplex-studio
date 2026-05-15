/**
 * TrainPlex PWA Service Worker — Phase 1 Step 4.3 + 4.4.
 *
 * Goal
 * ----
 *  - Trainer installs the PWA on phone (Add to Home Screen).
 *  - Slow 3G / 2G pe pehle se cached shell se app boot ho jaaye.
 *  - Net na ho to bhi `/api/v1/trainer/batch/submit` POST queue ho aur net
 *    aate hi background-sync auto-flush kar de.
 *
 * Caching strategies (3 named)
 * ----------------------------
 *  1. **cache-first** — for the app shell (`/`, `/manifest.webmanifest`,
 *     `/static/*` bundles, `/static/icons/*`). Stored in `tp-shell-v{N}`.
 *  2. **stale-while-revalidate** — for rarely-changing read APIs:
 *     `/api/v1/admin/templates/catalog` etc. Cached response is returned
 *     immediately; a network refresh updates the cache in the background.
 *  3. **network-first** — for everything else under `/api/v1/*` (auth-dependent
 *     reads). Falls back to cache if the network errors / times out (8s),
 *     so the trainer screen always renders something even on a flaky 2G.
 *
 * Offline submit queue
 * --------------------
 *  POST `/api/v1/trainer/batch/submit` is intercepted. When offline the body
 *  is parked in IndexedDB (`tp-offline-queue` / `submits` store). A
 *  Background Sync registration (`tp-flush-submits`) drains the queue once
 *  connectivity returns. If Background Sync API isn't available (iOS Safari,
 *  Brave with shields), the client-side `submit-queue.ts` flush also runs
 *  on the `online` event.
 *
 * Cache versioning
 * ----------------
 *  Bump `SHELL_CACHE_VERSION` on each deploy so stale shell HTML doesn't
 *  pin trainers to the old bundle. The `activate` step deletes every cache
 *  that doesn't match the current version.
 *
 *  IMPORTANT: do NOT use this SW in dev (yarn serve) — webpack HMR + a SW
 *  fighting each other cause stale-state heisenbugs. The `sw-register.ts`
 *  module skips registration when `location.hostname === 'localhost'` and
 *  `process.env.NODE_ENV !== 'production'`.
 */

const SHELL_CACHE_VERSION = "tp-shell-v1";
const RUNTIME_CACHE_VERSION = "tp-runtime-v1";

// The list of caches the activate step is allowed to keep. Everything else
// gets evicted so a fresh deploy doesn't leak old chunks.
const VALID_CACHES = [SHELL_CACHE_VERSION, RUNTIME_CACHE_VERSION];

// Minimum shell needed to render the trainer batch page offline. The
// hashed bundle filenames change each build — main.tsx imports them so the
// runtime fetch caches them as the SPA loads. Pre-cache only the stable
// addresses here.
const PRE_CACHE_URLS = [
  "/",
  "/trainer/batch",
  "/manifest.webmanifest",
  "/static/icons/pwa-192.svg",
  "/static/icons/pwa-512.svg",
];

// API path classifiers — kept here (not regex literal at use-site) so the
// strategies are easy to audit + the same set is referenced by Bg Sync.
const STALE_WHILE_REVALIDATE_PATHS = [
  "/api/v1/admin/templates/catalog",
];

// Auth-dependent reads: network-first with cache fallback.
const NETWORK_FIRST_API_PREFIX = "/api/v1/";

// The submit queue endpoint — when offline, we park the body in IndexedDB
// instead of letting fetch reject. The bulk-submit variant is the same
// flush path (server is forgiving — see views_pwa.py).
const SUBMIT_QUEUE_PATHS = [
  "/api/v1/trainer/batch/submit",
];

const NETWORK_TIMEOUT_MS = 8000;

// ─────────────────────────────────────────────────────────────────────────────
// IndexedDB helpers — kept tiny so we don't need a dep / idb-keyval.
// ─────────────────────────────────────────────────────────────────────────────

const DB_NAME = "tp-offline-queue";
const DB_VERSION = 1;
const STORE_SUBMITS = "submits";

function openQueueDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_SUBMITS)) {
        const store = db.createObjectStore(STORE_SUBMITS, {
          keyPath: "id",
          autoIncrement: true,
        });
        store.createIndex("by_task_id", "task_id", { unique: false });
        store.createIndex("by_created_at", "created_at", { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function queueSubmit(record) {
  const db = await openQueueDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_SUBMITS, "readwrite");
    const store = tx.objectStore(STORE_SUBMITS);
    const req = store.add(record);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function getAllQueued() {
  const db = await openQueueDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_SUBMITS, "readonly");
    const store = tx.objectStore(STORE_SUBMITS);
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

async function removeQueued(id) {
  const db = await openQueueDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_SUBMITS, "readwrite");
    const store = tx.objectStore(STORE_SUBMITS);
    const req = store.delete(id);
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Strategy implementations.
// ─────────────────────────────────────────────────────────────────────────────

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(SHELL_CACHE_VERSION);
    // Clone — the body stream can only be read once.
    cache.put(request, response.clone()).catch(() => {});
  }
  return response;
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(RUNTIME_CACHE_VERSION);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (response.ok) cache.put(request, response.clone()).catch(() => {});
      return response;
    })
    .catch(() => cached);
  // Prefer the cached value for instant render; otherwise wait for net.
  return cached || network;
}

function timeoutFetch(request, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("network-timeout")), ms);
    fetch(request)
      .then((response) => {
        clearTimeout(timer);
        resolve(response);
      })
      .catch((err) => {
        clearTimeout(timer);
        reject(err);
      });
  });
}

async function networkFirst(request) {
  const cache = await caches.open(RUNTIME_CACHE_VERSION);
  try {
    const response = await timeoutFetch(request, NETWORK_TIMEOUT_MS);
    if (response && response.ok) {
      cache.put(request, response.clone()).catch(() => {});
    }
    return response;
  } catch (_err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    // Last resort: a synthetic offline-aware error response so the React
    // layer can show the OfflineBanner instead of a generic fetch reject.
    return new Response(
      JSON.stringify({ error: "offline", queued: false }),
      {
        status: 503,
        statusText: "Offline",
        headers: { "Content-Type": "application/json" },
      },
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Submit-queue logic.
// ─────────────────────────────────────────────────────────────────────────────

async function handleSubmitWhileOffline(request, payload) {
  await queueSubmit({
    task_id: payload?.task_id ?? null,
    payload,
    created_at: Date.now(),
    attempts: 0,
  });
  // Register Background Sync — best-effort. iOS Safari ignores this; the
  // client-side `online` listener still flushes when net returns.
  try {
    if ("sync" in self.registration) {
      await self.registration.sync.register("tp-flush-submits");
    }
  } catch (_err) {
    // Background Sync not supported — fine, the client falls back.
  }
  return new Response(
    JSON.stringify({ queued: true, offline: true }),
    {
      status: 202,
      statusText: "Accepted (offline queue)",
      headers: { "Content-Type": "application/json" },
    },
  );
}

async function flushQueueOnce() {
  const queued = await getAllQueued();
  for (const entry of queued) {
    try {
      const response = await fetch("/api/v1/trainer/batch/submit", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry.payload),
      });
      if (response.ok) {
        await removeQueued(entry.id);
        // Tell every open tab so the BatchPage can flip the task UI.
        const clientsList = await self.clients.matchAll({
          includeUncontrolled: true,
        });
        for (const c of clientsList) {
          c.postMessage({ type: "tp-submit-flushed", task_id: entry.task_id });
        }
      } else if (response.status >= 500) {
        // Server transient — leave queued, retry next sync.
        return;
      } else {
        // 4xx — server rejected the payload; drop to avoid infinite retry.
        await removeQueued(entry.id);
      }
    } catch (_err) {
      // Network failed again — leave queued; the next sync event retries.
      return;
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Event listeners.
// ─────────────────────────────────────────────────────────────────────────────

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE_VERSION)
      .then((cache) => cache.addAll(PRE_CACHE_URLS).catch(() => {}))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => key.startsWith("tp-") && !VALID_CACHES.includes(key))
          .map((key) => caches.delete(key)),
      );
    }).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  // Bail for non-GET/POST early — DELETE/PATCH are admin actions that we
  // never want to cache or queue.
  if (request.method !== "GET" && request.method !== "POST") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // POST submit queue path — when offline, swallow + queue.
  if (request.method === "POST" && SUBMIT_QUEUE_PATHS.includes(url.pathname)) {
    event.respondWith(
      (async () => {
        try {
          // Try network first; if it succeeds, great.
          const response = await timeoutFetch(request.clone(), NETWORK_TIMEOUT_MS);
          if (response && response.ok) return response;
          // Non-OK response: still queue so the trainer never loses work.
          throw new Error("submit-not-ok");
        } catch (_err) {
          let payload = {};
          try {
            payload = await request.clone().json();
          } catch (_jsonErr) {
            // Body wasn't JSON — keep the raw text. Still queueable.
            payload = { raw: await request.clone().text() };
          }
          return handleSubmitWhileOffline(request, payload);
        }
      })(),
    );
    return;
  }

  if (request.method !== "GET") return;

  // SWR for the small set of rarely-changing reads.
  if (STALE_WHILE_REVALIDATE_PATHS.some((p) => url.pathname.startsWith(p))) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  // Auth-dependent reads — network first, cache fallback.
  if (url.pathname.startsWith(NETWORK_FIRST_API_PREFIX)) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Static assets, the app shell, icons, fonts — cache-first.
  if (
    url.pathname.startsWith("/static/") ||
    url.pathname === "/manifest.webmanifest" ||
    url.pathname === "/" ||
    url.pathname.startsWith("/trainer/")
  ) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Default: let the browser handle it normally.
});

self.addEventListener("sync", (event) => {
  if (event.tag === "tp-flush-submits") {
    event.waitUntil(flushQueueOnce());
  }
});

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "tp-skip-waiting") {
    self.skipWaiting();
  } else if (data.type === "tp-flush-submits") {
    // Client-side fallback for browsers without Background Sync.
    event.waitUntil?.(flushQueueOnce());
    flushQueueOnce();
  }
});
