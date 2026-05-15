/**
 * TaskQueueCard — single tile in the trainer's 10-task batch grid.
 *
 * Renders task preview + tier badge + earnings + status pill. Hovering
 * lifts the tile (CSS); clicking the "Open" button drills to the
 * annotator (Phase 2 will wire to the real LS annotator URL — Phase 1
 * just no-ops + emits a console message).
 *
 * Phase 1 Step 1.4-E.
 */

import { useTranslation } from "@humansignal/app-common";
import type { BatchStatus, BatchTask, BatchTier } from "./types";
import styles from "./Batch.module.css";

const STATUS_CLASS: Record<BatchStatus, string> = {
  pending: styles.statusPending,
  in_progress: styles.statusInProgress,
  done: styles.statusDone,
};

const STATUS_I18N: Record<BatchStatus, string> = {
  pending: "trainer.batch.status_pending",
  in_progress: "trainer.batch.status_in_progress",
  done: "trainer.batch.status_done",
};

const TIER_CLASS: Record<BatchTier, string> = {
  bronze: styles.tierBronze,
  silver: styles.tierSilver,
  gold: styles.tierGold,
};

const TIER_I18N: Record<BatchTier, string> = {
  bronze: "trainer.batch.tier_bronze",
  silver: "trainer.batch.tier_silver",
  gold: "trainer.batch.tier_gold",
};

export interface TaskQueueCardProps {
  task: BatchTask;
  /** Click handler — Phase 2 wires this to the real annotator route. */
  onOpen?: (taskId: number) => void;
}

export function TaskQueueCard({ task, onOpen }: TaskQueueCardProps) {
  const { t } = useTranslation();

  const cardClass =
    task.status === "done"
      ? `${styles.taskCard} ${styles.taskCardDone}`
      : task.status === "in_progress"
        ? `${styles.taskCard} ${styles.taskCardInProgress}`
        : styles.taskCard;

  return (
    <article
      className={cardClass}
      data-testid={`task-card-${task.task_id}`}
      data-task-status={task.status}
      data-task-tier={task.tier}
    >
      <header className={styles.taskType}>
        {task.task_type.replace(/_/g, " ")}
      </header>
      <p className={styles.taskPreview}>{task.preview}</p>
      <footer className={styles.taskFooter}>
        <span
          className={`${styles.tierBadge} ${TIER_CLASS[task.tier]}`}
          data-testid={`task-tier-${task.task_id}`}
        >
          {t(TIER_I18N[task.tier])}
        </span>
        <span className={styles.taskEarnings} data-testid={`task-earnings-${task.task_id}`}>
          ₹{task.earnings_inr}
        </span>
        <span
          className={`${styles.statusPill} ${STATUS_CLASS[task.status]}`}
          data-testid={`task-status-${task.task_id}`}
        >
          {t(STATUS_I18N[task.status])}
        </span>
      </footer>
      <button
        type="button"
        className="lsf-button lsf-button_look_filled lsf-button_size_small"
        onClick={() => onOpen?.(task.task_id)}
        data-testid={`task-open-${task.task_id}`}
        aria-label={t("trainer.batch.open_task")}
      >
        {t("trainer.batch.open_task")} →
      </button>
    </article>
  );
}
