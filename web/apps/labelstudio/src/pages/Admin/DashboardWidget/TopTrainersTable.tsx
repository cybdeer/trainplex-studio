/**
 * TopTrainersTable — top-5 trainers state-wise list.
 *
 * Phase 1 Step 4.2-1. Renders the `top_trainers` block from the admin
 * dashboard snapshot. Static table for now — no sort / no pagination.
 *
 * Pulls all labels via `t(...)` so Hindi mode renders Devanagari headers.
 */

import { useTranslation } from "@humansignal/app-common";
import type { DashboardTopTrainer } from "./types";
import styles from "./DashboardWidget.module.css";

const formatINR = (locale: string, value: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);

export interface TopTrainersTableProps {
  trainers: DashboardTopTrainer[];
}

export function TopTrainersTable({ trainers }: TopTrainersTableProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";

  return (
    <div className={styles.topTrainersBlock} data-testid="top-trainers-table">
      <h3 className={styles.sectionHeading}>{t("admin.dashboard.top_trainers")}</h3>
      <table className={styles.trainerTable}>
        <thead>
          <tr>
            <th>{t("admin.dashboard.trainer_name")}</th>
            <th>{t("admin.dashboard.state")}</th>
            <th className={styles.colNum}>{t("admin.dashboard.tasks_today")}</th>
            <th className={styles.colNum}>{t("admin.dashboard.earnings_today")}</th>
          </tr>
        </thead>
        <tbody>
          {trainers.map((tr) => (
            <tr key={tr.id} data-testid={`trainer-row-${tr.id}`}>
              <td>{tr.name}</td>
              <td>{tr.state}</td>
              <td className={styles.colNum}>{tr.tasks_today}</td>
              <td className={styles.colNum}>{formatINR(locale, tr.earnings_today_inr)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default TopTrainersTable;
