/**
 * BatchPage — TrainPlex trainer's 10-task batch view.
 *
 * Phase 1 Step 1.4-E. Per plan: "10-task batch native + sticky earnings ticker."
 *
 * Layout
 * ------
 *   ┌────────────────────────────────────────────────────┐
 *   │ Today's Batch         3/10 done                    │
 *   ├────────────────────────────────────────────────────┤
 *   │ ┌──────┐ ┌──────┐ ┌──────┐                         │
 *   │ │ Task │ │ Task │ │ Task │  ← tile grid (1/2/3 cols)│
 *   │ └──────┘ └──────┘ └──────┘                         │
 *   │ ┌──────┐ ┌──────┐ ┌──────┐                         │
 *   │ │ Task │ │ Task │ │ Task │                         │
 *   │ └──────┘ └──────┘ └──────┘                         │
 *   ├────────────────────────────────────────────────────┤  ← sticky ticker
 *   │ ₹150 / ₹300    ● ● ● ◐ ○ ○ ○ ○ ○ ○    3/10 done    │
 *   └────────────────────────────────────────────────────┘
 *
 * Data
 * ----
 * Fetches `GET /api/v1/trainer/batch?size=10` (trainer-only, backend
 * @require_role(['trainer'])). Mock data in Phase 1; real assignment
 * engine in Phase 2. JSON contract pinned by `test_batch.py`.
 *
 * Completion
 * ----------
 * When all 10 tasks reach `status: done`, the `<BatchCompleteCelebration>`
 * modal pops with total earnings + a "Start Next Batch" CTA which calls
 * `queryClient.invalidateQueries` on the batch key to fetch the next set.
 */

import { Spinner } from "@humansignal/ui";
import { RoleGate } from "@humansignal/ui";
import {
  useTranslation,
  enqueueSubmit,
  flushQueue,
  onQueueChange,
} from "@humansignal/app-common";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { TaskQueueCard } from "./TaskQueueCard";
import { EarningsTicker } from "./EarningsTicker";
import { BatchCompleteCelebration } from "./BatchCompleteCelebration";
import type { BatchTask } from "./types";
import styles from "./Batch.module.css";

const BATCH_QUERY_KEY = "trainer-batch";

function BatchSkeleton({ label }: { label: string }) {
  return (
    <div
      className={styles.loadingBox}
      role="status"
      aria-live="polite"
      data-testid="batch-skeleton"
    >
      <Spinner />
      <span style={{ marginLeft: 10 }}>{label}</span>
    </div>
  );
}

export const BatchPage: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [celebrationDismissed, setCelebrationDismissed] = useState(false);

  // Phase 1 Step 4.3 + 4.4 — Online/offline + offline queue state.
  // `navigator.onLine` is a hint, not a guarantee. The service worker
  // emits `tp-network-status` events (window-level) once the fetch path
  // actually fails too, so the chip never lies even when the OS reports
  // "online" but the upstream is unreachable.
  const [online, setOnline] = useState(
    typeof navigator !== "undefined" ? navigator.onLine : true,
  );
  const [queuedCount, setQueuedCount] = useState(0);

  useEffect(() => {
    const handleStatus = (event: Event) => {
      const detail = (event as CustomEvent<{ online: boolean }>).detail;
      if (detail) setOnline(detail.online);
    };
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener("tp-network-status", handleStatus);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("tp-network-status", handleStatus);
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    // Subscribe to queue-count changes; the queue lib fires once on
    // mount with the current count so we don't need an explicit initial
    // read here.
    return onQueueChange((count) => setQueuedCount(count));
  }, []);

  /**
   * Submit a task answer. Tries network first; on failure (offline or
   * fetch reject) parks the payload in IndexedDB so the SW + the
   * `online` flush both pick it up.
   *
   * Phase 1 wiring: BatchPage's TaskQueueCard `onOpen` only logs today
   * (real annotator lives in Phase 2 / Step 8). This helper is exported
   * via `window.__tpSubmitTask` so the annotator iframe can call it
   * once Step 8 lands. The contract — payload shape, error semantics —
   * is finalised here so Step 8 only swaps the call-site.
   */
  const submitTask = useCallback(
    async (task_id: number, payload: Record<string, unknown>) => {
      try {
        const result = (await api.callApi("trainerBatchSubmit", {
          body: { task_id, ...payload },
        })) as { ok?: boolean } | null;
        return { sent: true, queued: false, result };
      } catch (_err) {
        // Offline / 5xx / timeout — queue + return so the caller can
        // toast "Queued" without surfacing the error.
        await enqueueSubmit(task_id, { task_id, ...payload });
        return { sent: false, queued: true };
      }
    },
    [api],
  );

  // Expose the submit helper on `window` so the annotator iframe (Step 8)
  // can call it without re-implementing the offline-queue branching.
  useEffect(() => {
    (window as unknown as { __tpSubmitTask?: typeof submitTask }).__tpSubmitTask =
      submitTask;
    return () => {
      delete (window as unknown as { __tpSubmitTask?: typeof submitTask }).__tpSubmitTask;
    };
  }, [submitTask]);

  // When the device comes back online with queued submits, attempt a
  // flush. The SW Background Sync covers most cases; this is the iOS
  // Safari + Brave-with-shields fallback.
  useEffect(() => {
    if (online && queuedCount > 0) {
      flushQueue().catch(() => {
        // Already logged + counters tracked inside flushQueue.
      });
    }
  }, [online, queuedCount]);

  const { data, isFetching, isError } = useQuery<BatchTask[]>({
    queryKey: [BATCH_QUERY_KEY],
    queryFn: async () => {
      const res = await api.callApi("trainerBatch", {
        params: { size: 10 },
      });
      return (res as BatchTask[]) ?? [];
    },
    // The batch is the trainer's "today's queue" — stable for the session.
    staleTime: 60_000,
    enabled: user?.role === "trainer",
  });

  // Total / done counters are derived (single source of truth = the data
  // array). useMemo because TaskQueueCard's onOpen handler closures over
  // these counters indirectly.
  const isComplete = useMemo(() => {
    if (!data || data.length === 0) return false;
    return data.every((t) => t.status === "done");
  }, [data]);

  const onOpenTask = (taskId: number) => {
    // Phase 2 wires this to the real LS annotator URL. Phase 1: log only.
    // eslint-disable-next-line no-console
    console.info(`[BatchPage] open task ${taskId}`);
  };

  const onNextBatch = () => {
    setCelebrationDismissed(true);
    queryClient.invalidateQueries({ queryKey: [BATCH_QUERY_KEY] });
  };

  return (
    <main className={`p-6 ${styles.batchRoot}`} data-testid="trainer-batch-page">
      <RoleGate
        allow={["trainer"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="batch-forbidden">
            403 — trainer only
          </div>
        }
      >
        <header className={styles.batchHeader}>
          <h1 className={styles.batchTitle}>{t("trainer.batch.title")}</h1>
          {/* Phase 1 Step 4.3 + 4.4 — Offline / queued chip. Renders
              whenever the device is offline OR there are queued submits
              still waiting to flush. Synced state shows briefly after a
              successful flush. */}
          {(!online || queuedCount > 0) && (
            <div
              className={`${styles.offlineChip} ${online ? styles.online : ""}`}
              data-testid="batch-offline-chip"
              aria-live="polite"
            >
              <span className={styles.offlineDot} aria-hidden="true" />
              <span>
                {online
                  ? t("pwa.online_synced", { count: queuedCount })
                  : t("pwa.offline_banner", { count: queuedCount })}
              </span>
            </div>
          )}
          {data && data.length > 0 && (
            <div className={styles.batchProgress} data-testid="batch-progress-pill">
              {t("trainer.batch.progress", {
                done: data.filter((d) => d.status === "done").length,
                total: data.length,
              })}
            </div>
          )}
        </header>

        {isFetching && !data ? (
          <BatchSkeleton label={t("trainer.batch.loading")} />
        ) : isError || !data ? (
          <div className={styles.errorBox} data-testid="batch-error">
            {t("trainer.batch.load_failed")}
          </div>
        ) : (
          <>
            <div className={styles.tileGrid} data-testid="batch-tile-grid">
              {data.map((task) => (
                <TaskQueueCard key={task.task_id} task={task} onOpen={onOpenTask} />
              ))}
            </div>
            <EarningsTicker batch={data} />
            {isComplete && !celebrationDismissed && (
              <BatchCompleteCelebration
                batch={data}
                onNextBatch={onNextBatch}
                onClose={() => setCelebrationDismissed(true)}
              />
            )}
          </>
        )}
      </RoleGate>
    </main>
  );
};

BatchPage.title = "Today's Batch";
BatchPage.path = "/trainer/batch";
BatchPage.exact = true;

export default BatchPage;
