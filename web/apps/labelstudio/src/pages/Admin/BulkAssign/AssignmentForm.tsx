/**
 * AssignmentForm — bottom panel of the Bulk Assign page.
 *
 * Phase 1 Step 4.2-3.
 *
 * Fields:
 *   * Project picker — free-text Project ID input. (Phase 2 swaps for a
 *     real project dropdown once the admin projects list endpoint exists.)
 *   * Tasks-per-trainer slider — 1..100, default 10.
 *   * Distribution strategy radio — even / tier-weighted.
 *   * Submit button (Saffron Orange CTA) — disabled until project_id set
 *     AND at least one trainer matched.
 *
 * On submit, the parent fires POST /api/v1/admin/tasks/bulk-assign and
 * opens the result drawer with the per-trainer plan.
 */

import { Button } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import type { DistributeStrategy } from "./types";
import styles from "./BulkAssign.module.css";

export interface AssignmentFormProps {
  projectId: string;
  onProjectIdChange: (value: string) => void;
  tasksPerTrainer: number;
  onTasksPerTrainerChange: (value: number) => void;
  strategy: DistributeStrategy;
  onStrategyChange: (value: DistributeStrategy) => void;
  matchedCount: number;
  onSubmit: () => void;
  isSubmitting: boolean;
  /** True iff submit is allowed (project_id set + at least one match). */
  canSubmit: boolean;
}

export function AssignmentForm({
  projectId,
  onProjectIdChange,
  tasksPerTrainer,
  onTasksPerTrainerChange,
  strategy,
  onStrategyChange,
  matchedCount,
  onSubmit,
  isSubmitting,
  canSubmit,
}: AssignmentFormProps) {
  const { t } = useTranslation();

  return (
    <div data-testid="bulk-assignment-form">
      <div className={styles.formRow}>
        <label className={styles.formField}>
          <span className={styles.formLabel}>{t("admin.bulk.choose_project")}</span>
          <input
            type="number"
            min={1}
            inputMode="numeric"
            placeholder="42"
            className={styles.formInput}
            value={projectId}
            data-testid="bulk-project-id-input"
            onChange={(e) => onProjectIdChange(e.target.value)}
          />
        </label>

        <label className={styles.formField}>
          <span className={styles.formLabel}>{t("admin.bulk.tasks_per_trainer")}</span>
          <input
            type="range"
            min={1}
            max={100}
            step={1}
            value={tasksPerTrainer}
            className={styles.formInput}
            data-testid="bulk-tasks-per-trainer-slider"
            onChange={(e) => onTasksPerTrainerChange(Number(e.target.value))}
          />
          <span
            className={styles.sliderValue}
            data-testid="bulk-tasks-per-trainer-value"
          >
            {tasksPerTrainer}
          </span>
        </label>

        <fieldset className={styles.formField} data-testid="bulk-strategy-group">
          <legend className={styles.formLabel}>
            {strategy === "tier-weighted"
              ? t("admin.bulk.distribute_tier")
              : t("admin.bulk.distribute_even")}
          </legend>
          <label>
            <input
              type="radio"
              name="distribute_strategy"
              value="even"
              checked={strategy === "even"}
              data-testid="bulk-strategy-even"
              onChange={() => onStrategyChange("even")}
            />
            {" "}
            {t("admin.bulk.distribute_even")}
          </label>
          <label>
            <input
              type="radio"
              name="distribute_strategy"
              value="tier-weighted"
              checked={strategy === "tier-weighted"}
              data-testid="bulk-strategy-tier"
              onChange={() => onStrategyChange("tier-weighted")}
            />
            {" "}
            {t("admin.bulk.distribute_tier")}
          </label>
        </fieldset>
      </div>

      <div className={styles.formRow}>
        <Button
          look="filled"
          size="medium"
          className={styles.assignBtn}
          data-testid="bulk-assign-submit"
          disabled={!canSubmit || isSubmitting}
          onClick={onSubmit}
        >
          {t("admin.bulk.assign_button", { count: matchedCount })}
        </Button>
      </div>
    </div>
  );
}

export default AssignmentForm;
