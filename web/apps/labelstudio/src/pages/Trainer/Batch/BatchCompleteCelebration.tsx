/**
 * BatchCompleteCelebration — modal shown when all 10 tasks are done.
 *
 * Per plan: "10/10 complete" celebration. Shows total earnings, task
 * count, and a CTA to start the next batch (which calls into the
 * refresh endpoint or simply re-fetches the batch list).
 *
 * Phase 1 Step 1.4-E.
 */

import { useTranslation } from "@humansignal/app-common";
import type { BatchTask } from "./types";
import styles from "./Batch.module.css";

export interface BatchCompleteCelebrationProps {
  batch: BatchTask[];
  /** Click on the CTA — parent triggers next-batch fetch / nav. */
  onNextBatch: () => void;
  /** Close without starting a new batch. */
  onClose?: () => void;
}

export function BatchCompleteCelebration({
  batch,
  onNextBatch,
  onClose,
}: BatchCompleteCelebrationProps) {
  const { t } = useTranslation();

  const totalEarnings = batch.reduce((sum, b) => sum + b.earnings_inr, 0);
  const totalCount = batch.length;

  return (
    <div
      className={styles.modalOverlay}
      role="dialog"
      aria-modal="true"
      aria-labelledby="batch-celebration-title"
      data-testid="batch-celebration"
      onClick={onClose}
    >
      <div
        className={styles.modalCard}
        onClick={(e) => e.stopPropagation()}
        data-testid="batch-celebration-card"
      >
        <div className={styles.celebrationEmoji} aria-hidden="true">
          🎉
        </div>
        <h2 id="batch-celebration-title" className={styles.celebrationTitle}>
          {t("trainer.batch.complete")}
        </h2>
        <div className={styles.celebrationStats}>
          <div className={styles.celebrationStat}>
            <span className={styles.celebrationStatValue} data-testid="celebration-earnings">
              ₹{totalEarnings}
            </span>
            <span className={styles.celebrationStatLabel}>
              {t("trainer.batch.earnings_so_far")}
            </span>
          </div>
          <div className={styles.celebrationStat}>
            <span className={styles.celebrationStatValue} data-testid="celebration-task-count">
              {totalCount}
            </span>
            <span className={styles.celebrationStatLabel}>
              {t("trainer.tasks_done")}
            </span>
          </div>
        </div>
        <button
          type="button"
          className={`lsf-button lsf-button_look_filled lsf-button_size_medium ${styles.celebrationCTA}`}
          onClick={onNextBatch}
          data-testid="celebration-next-batch"
        >
          {t("trainer.batch.next_batch")} →
        </button>
      </div>
    </div>
  );
}
