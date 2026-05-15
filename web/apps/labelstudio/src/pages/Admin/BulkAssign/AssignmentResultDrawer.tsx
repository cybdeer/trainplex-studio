/**
 * AssignmentResultDrawer — slide-out summary of a completed bulk assign.
 *
 * Phase 1 Step 4.2-3. Shows:
 *   * Top stats row: trainer count, total tasks, strategy used.
 *   * Per-trainer plan: trainer name + tier + will_assign count.
 *   * Unknown rows (trainer id not in roster) are flagged in red so the
 *     admin can see exactly which ids were ignored.
 *
 * Closes on backdrop click or the X button. Phase 2: a "Re-run with same
 * filter" button + an undo path.
 */

import { useTranslation } from "@humansignal/app-common";
import type { BulkAssignResponse } from "./types";
import styles from "./BulkAssign.module.css";

export interface AssignmentResultDrawerProps {
  open: boolean;
  result: BulkAssignResponse | null;
  onClose: () => void;
}

export function AssignmentResultDrawer({
  open,
  result,
  onClose,
}: AssignmentResultDrawerProps) {
  const { t } = useTranslation();

  if (!open || !result) return null;

  return (
    <div data-testid="bulk-result-drawer">
      <div className={styles.drawerBackdrop} onClick={onClose} />
      <aside className={styles.drawer} role="dialog" aria-label={t("admin.bulk.result_summary")}>
        <header className={styles.drawerHeader}>
          <h3 className={styles.drawerHeading}>{t("admin.bulk.result_summary")}</h3>
          <button
            type="button"
            className={styles.drawerClose}
            data-testid="bulk-result-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </header>

        <div className={styles.drawerBody}>
          <div className={styles.summaryStats}>
            <div className={styles.summaryStatItem}>
              <span className={styles.summaryStatLabel}>
                {t("admin.dashboard.active_trainers")}
              </span>
              <span
                className={styles.summaryStatValue}
                data-testid="bulk-result-trainer-count"
              >
                {result.summary.trainer_count}
              </span>
            </div>
            <div className={styles.summaryStatItem}>
              <span className={styles.summaryStatLabel}>
                {t("admin.bulk.col_will_assign")}
              </span>
              <span
                className={styles.summaryStatValue}
                data-testid="bulk-result-task-count"
              >
                {result.summary.total_tasks}
              </span>
            </div>
            <div className={styles.summaryStatItem}>
              <span className={styles.summaryStatLabel}>
                {result.summary.strategy === "tier-weighted"
                  ? t("admin.bulk.distribute_tier")
                  : t("admin.bulk.distribute_even")}
              </span>
              <span
                className={styles.summaryStatValue}
                data-testid="bulk-result-strategy"
                style={{ fontSize: "0.875rem", fontWeight: 500 }}
              >
                {result.summary.strategy}
              </span>
            </div>
          </div>

          <div data-testid="bulk-result-plan">
            {result.plan.map((row) => (
              <div
                key={row.trainer_id}
                className={`${styles.planRow} ${row.unknown ? styles.planRowUnknown : ""}`}
                data-testid={`bulk-plan-row-${row.trainer_id}`}
              >
                <span>
                  {row.unknown
                    ? `#${row.trainer_id} (unknown)`
                    : `${row.name} · ${row.tier}`}
                </span>
                <span className={styles.planTaskCount}>{row.will_assign}</span>
              </div>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

export default AssignmentResultDrawer;
