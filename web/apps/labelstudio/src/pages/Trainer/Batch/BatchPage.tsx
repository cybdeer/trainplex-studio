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
import { useTranslation } from "@humansignal/app-common";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
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
