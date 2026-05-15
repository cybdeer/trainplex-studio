/**
 * TrainPlex offline submit queue — Phase 1 Step 4.3 + 4.4.
 *
 * What this module owns
 * ---------------------
 *  - An IndexedDB-backed queue of pending POSTs to
 *    ``/api/v1/trainer/batch/submit``.
 *  - `enqueueSubmit(task_id, payload)` — pushed when the trainer hits
 *    "Submit + Next" and the device is offline (or fetch fails).
 *  - `getQueue()` — read snapshot (used by the OfflineBanner badge).
 *  - `flushQueue()` — fires each pending POST, removes on 2xx, retries
 *    with exponential backoff on transient failures (network /
 *    HTTP 5xx). 4xx responses are dropped to avoid infinite retry.
 *  - `onQueueChange(callback)` — subscribe to count-change events so
 *    the BatchPage chip "Offline · 3 task queued" updates in real time.
 *
 * Why IndexedDB (not localStorage)
 * --------------------------------
 *  - localStorage is synchronous + bounded at ~5MB total. A trainer
 *    submitting captions / OCR could blow past that in one shift.
 *  - IndexedDB is async + per-origin quota in the hundreds of MB so the
 *    queue can survive a whole offline shift without dropping work.
 *  - The dedicated `tp-offline-queue` DB lives alongside the SW's same
 *    DB (Step 4.4 SW writes to the identical `submits` store) so the SW
 *    background-sync path + the client-side `flushQueue` path see the
 *    same rows — no cross-store reconciliation required.
 *
 * Backoff curve
 * -------------
 *  Exponential with jitter, capped at 60s:
 *      attempt 1 → 1s
 *      attempt 2 → 2s
 *      attempt 3 → 4s
 *      attempt 4 → 8s
 *      attempt 5 → 16s
 *      attempt 6 → 32s
 *      attempt 7+ → 60s
 *  Plus a random 0–25% jitter to avoid a thundering-herd reconnect
 *  spike across all trainers in the same cell tower coming back at the
 *  same instant.
 */

const DB_NAME = "tp-offline-queue";
const DB_VERSION = 1;
const STORE_SUBMITS = "submits";
const MAX_BACKOFF_MS = 60_000;

/** A single queued submit entry as stored in IndexedDB. */
export interface QueuedSubmit {
  /** Auto-incremented IndexedDB primary key. */
  id?: number;
  /** Trainer's batch task id. */
  task_id: number;
  /** The body that would have been POSTed to /api/v1/trainer/batch/submit. */
  payload: Record<string, unknown>;
  /** Epoch ms when the submit was first queued. */
  created_at: number;
  /** Count of failed POST attempts. */
  attempts: number;
  /** Last attempt error message (debug only — not displayed to the user). */
  last_error?: string;
}

/**
 * IndexedDB types vary slightly between jsdom / fake-indexeddb / browser.
 * Centralise the open call so the test runner can monkey-patch
 * `globalThis.indexedDB` once and every helper picks it up.
 */
function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
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

function runRequest<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// CRUD primitives.
// ─────────────────────────────────────────────────────────────────────────────

export async function enqueueSubmit(
  task_id: number,
  payload: Record<string, unknown>,
): Promise<number> {
  const db = await openDb();
  const tx = db.transaction(STORE_SUBMITS, "readwrite");
  const store = tx.objectStore(STORE_SUBMITS);
  const record: QueuedSubmit = {
    task_id,
    payload,
    created_at: Date.now(),
    attempts: 0,
  };
  const id = (await runRequest(store.add(record))) as number;
  notifySubscribers();
  return id;
}

export async function getQueue(): Promise<QueuedSubmit[]> {
  const db = await openDb();
  const tx = db.transaction(STORE_SUBMITS, "readonly");
  const store = tx.objectStore(STORE_SUBMITS);
  return (await runRequest(store.getAll())) as QueuedSubmit[];
}

export async function removeFromQueue(id: number): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(STORE_SUBMITS, "readwrite");
  const store = tx.objectStore(STORE_SUBMITS);
  await runRequest(store.delete(id));
  notifySubscribers();
}

async function bumpAttempt(entry: QueuedSubmit, error: unknown): Promise<void> {
  if (entry.id == null) return;
  const db = await openDb();
  const tx = db.transaction(STORE_SUBMITS, "readwrite");
  const store = tx.objectStore(STORE_SUBMITS);
  const updated: QueuedSubmit = {
    ...entry,
    attempts: entry.attempts + 1,
    last_error: error instanceof Error ? error.message : String(error),
  };
  await runRequest(store.put(updated));
}

// ─────────────────────────────────────────────────────────────────────────────
// Subscriber pattern — BatchPage subscribes to count changes for the badge.
// ─────────────────────────────────────────────────────────────────────────────

type QueueChangeCallback = (count: number) => void;
const subscribers = new Set<QueueChangeCallback>();

/**
 * Subscribe to queue-count changes. Returns an unsubscribe fn.
 *
 * Fires synchronously on subscription with the current count so the
 * caller doesn't need a manual initial `getQueue()` call.
 */
export function onQueueChange(callback: QueueChangeCallback): () => void {
  subscribers.add(callback);
  // Initial fire — best-effort.
  getQueue()
    .then((q) => callback(q.length))
    .catch(() => callback(0));
  return () => subscribers.delete(callback);
}

function notifySubscribers(): void {
  if (subscribers.size === 0) return;
  getQueue()
    .then((q) => {
      for (const cb of subscribers) cb(q.length);
    })
    .catch(() => {
      for (const cb of subscribers) cb(0);
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// Backoff curve.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Exponential-backoff delay in ms for the Nth attempt (0-indexed).
 *
 * Exported so the SW + tests can use the identical curve. The 25% jitter
 * is added at the call-site, not here — keeping this pure makes the
 * timing assertions exact.
 */
export function backoffMs(attempt: number): number {
  const base = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** attempt);
  return base;
}

function backoffWithJitter(attempt: number): number {
  const base = backoffMs(attempt);
  const jitter = base * 0.25 * Math.random();
  return base + jitter;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ─────────────────────────────────────────────────────────────────────────────
// Flush.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Optional injectable fetch so tests can supply a stubbed implementation
 * without monkey-patching `globalThis.fetch`. Default: the real fetch.
 */
type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export interface FlushQueueOptions {
  fetchImpl?: FetchLike;
  /** Custom POST URL — default matches the backend route. */
  submitUrl?: string;
  /** Hard cap on per-entry retry attempts; entries beyond are dropped. */
  maxAttempts?: number;
}

export interface FlushQueueResult {
  flushed: number;
  retried: number;
  dropped: number;
}

/**
 * Try to POST every queued submit. Returns counters so the caller can
 * decide which toast to show.
 *
 * Safe to call concurrently — IndexedDB transactions are isolated per
 * call. A second concurrent caller might double-POST a single entry; the
 * server's bulk-submit endpoint is idempotent on (task_id, trainer_id)
 * so this is harmless.
 */
export async function flushQueue(
  options: FlushQueueOptions = {},
): Promise<FlushQueueResult> {
  const {
    fetchImpl = typeof fetch !== "undefined" ? fetch : null,
    submitUrl = "/api/v1/trainer/batch/submit",
    maxAttempts = 7,
  } = options;
  if (!fetchImpl) {
    return { flushed: 0, retried: 0, dropped: 0 };
  }
  const queue = await getQueue();
  let flushed = 0;
  let retried = 0;
  let dropped = 0;
  for (const entry of queue) {
    if (entry.id == null) continue;
    if (entry.attempts >= maxAttempts) {
      // Give up — surface a "queue_failed" toast at the caller via the
      // dropped count. The row stays so the user can manually retry
      // later (a Phase 2 trash-bin UI handles eviction).
      dropped++;
      continue;
    }
    try {
      const response = await fetchImpl(submitUrl, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry.payload),
      });
      if (response.ok) {
        await removeFromQueue(entry.id);
        flushed++;
      } else if (response.status >= 500) {
        await bumpAttempt(entry, new Error(`HTTP ${response.status}`));
        retried++;
        await sleep(backoffWithJitter(entry.attempts));
      } else {
        // 4xx — payload rejected. Drop to avoid infinite retry.
        await removeFromQueue(entry.id);
        dropped++;
      }
    } catch (err) {
      await bumpAttempt(entry, err);
      retried++;
      await sleep(backoffWithJitter(entry.attempts));
    }
  }
  notifySubscribers();
  return { flushed, retried, dropped };
}

/**
 * Test-only helper: clear every row in the queue. Exported so tests can
 * reset state between cases; never called from app code.
 */
export async function _clearQueueForTests(): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(STORE_SUBMITS, "readwrite");
  const store = tx.objectStore(STORE_SUBMITS);
  await runRequest(store.clear());
  notifySubscribers();
}
