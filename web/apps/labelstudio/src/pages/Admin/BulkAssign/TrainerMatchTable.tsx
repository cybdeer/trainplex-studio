/**
 * TrainerMatchTable — read-only listing of trainers matching the active
 * filters, with each trainer's current active task count.
 *
 * Phase 1 Step 4.2-3. Per plan: "Manual ek-ek checkbox khatam" — the bulk
 * assign flow does NOT require individual checkboxes. Every matched
 * trainer is implicitly included in the assignment; the table is a
 * visibility aid so the founder can sanity-check the filter result before
 * pressing Assign.
 */

import { useTranslation } from "@humansignal/app-common";
import type { TrainerMatch } from "./types";
import styles from "./BulkAssign.module.css";

export interface TrainerMatchTableProps {
  trainers: TrainerMatch[];
  isLoading?: boolean;
}

export function TrainerMatchTable({ trainers, isLoading }: TrainerMatchTableProps) {
  const { t } = useTranslation();

  return (
    <div data-testid="bulk-match-table-wrap">
      <p className={styles.matchedCount} data-testid="bulk-matched-count">
        {t("admin.bulk.matched_count", { count: trainers.length })}
      </p>
      <table className={styles.matchTable} data-testid="bulk-match-table">
        <thead>
          <tr>
            <th>{t("admin.bulk.col_trainer")}</th>
            <th>{t("admin.wizard.col_state")}</th>
            <th>{t("admin.wizard.col_tier")}</th>
            <th>{t("admin.wizard.col_languages")}</th>
            <th>{t("admin.wizard.col_cert")}</th>
            <th>{t("admin.bulk.col_tasks_now")}</th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            <tr>
              <td colSpan={6} className={styles.emptyRow} data-testid="bulk-table-loading">
                {t("common.loading")}
              </td>
            </tr>
          ) : trainers.length === 0 ? (
            <tr>
              <td colSpan={6} className={styles.emptyRow} data-testid="bulk-table-empty">
                {t("admin.wizard.no_trainers")}
              </td>
            </tr>
          ) : (
            trainers.map((tr) => (
              <tr key={tr.id} data-testid={`bulk-match-row-${tr.id}`}>
                <td>{tr.name}</td>
                <td>{tr.state}</td>
                <td>{tr.tier}</td>
                <td>{tr.languages.join(", ")}</td>
                <td>{tr.cert_passed ? "passed" : "pending"}</td>
                <td data-testid={`bulk-tasks-now-${tr.id}`}>
                  {tr.current_active_tasks_count}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default TrainerMatchTable;
