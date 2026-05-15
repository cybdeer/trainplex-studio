/**
 * AlertListPanel — sticky-header table for the quality alert center.
 *
 * Phase 1 Step 4.2-8. Pure presentational: receives rows + click handler,
 * renders the table. Pagination + filtering live in the parent.
 *
 * Columns (left → right):
 *   When  | Severity (chip) | Trigger | Trainer | Submission | Status
 *
 * Severity badge is the visual anchor — admin scans the column at a glance
 * and reds/oranges jump out first. The Trigger column shows the i18n-resolved
 * label, not the raw enum, so the table reads as English/Hindi prose.
 */

import { useTranslation } from "@humansignal/app-common";
import { SeverityBadge } from "./SeverityBadge";
import type { AlertRow, AlertStatus, AlertTriggerType } from "./types";
import styles from "./QualityAlerts.module.css";

export interface AlertListPanelProps {
  rows: AlertRow[];
  onRowClick: (row: AlertRow) => void;
  emptyMessage?: string;
}

/** Map enum → i18n key for the trigger column. */
const TRIGGER_LABEL_KEY: Record<AlertTriggerType, string> = {
  reviewer_disagree: "admin.alerts.trigger_disagree",
  reviewer_conflict: "admin.alerts.trigger_disagree",
  time_anomaly: "admin.alerts.trigger_time",
  duplicate_pattern: "admin.alerts.trigger_duplicate",
  cert_failed: "admin.alerts.trigger_duplicate",
};

/** Map enum → i18n key for the status column. */
const STATUS_LABEL_KEY: Record<AlertStatus, string> = {
  open: "admin.alerts.status_open",
  reviewed: "admin.alerts.status_reviewed",
  dismissed: "admin.alerts.status_dismissed",
  action_taken: "admin.alerts.status_action",
};

/**
 * Format an ISO timestamp into a locale-aware short display string.
 * Falls back to the raw string if `Date` parsing fails.
 */
function formatWhen(locale: string, isoTimestamp: string): string {
  try {
    const d = new Date(isoTimestamp);
    if (Number.isNaN(d.getTime())) return isoTimestamp;
    return d.toLocaleString(locale === "hi" ? "hi-IN" : "en-IN", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoTimestamp;
  }
}

export function AlertListPanel({ rows, onRowClick, emptyMessage }: AlertListPanelProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";

  return (
    <div className={styles.tableWrap} data-testid="alerts-table">
      <table className={styles.alertsTable}>
        <thead>
          <tr>
            <th className={styles.colWhen}>{t("admin.alerts.col_when")}</th>
            <th className={styles.colSeverity}>{t("admin.alerts.col_severity")}</th>
            <th className={styles.colTrigger}>{t("admin.alerts.col_trigger")}</th>
            <th className={styles.colTrainer}>{t("admin.alerts.col_trainer")}</th>
            <th className={styles.colSubmission}>{t("admin.alerts.col_submission")}</th>
            <th className={styles.colStatus}>{t("admin.alerts.col_status")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={6} className={styles.emptyRow} data-testid="alerts-empty">
                {emptyMessage ?? t("admin.alerts.no_alerts")}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={row.id}
                data-testid={`alert-row-${row.id}`}
                className={
                  row.severity === "critical"
                    ? styles.criticalRow
                    : row.severity === "high"
                      ? styles.highRow
                      : undefined
                }
                onClick={() => onRowClick(row)}
                tabIndex={0}
                role="button"
                aria-label={`${row.trigger_type} ${row.trainer?.email ?? "—"}`}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onRowClick(row);
                  }
                }}
              >
                <td className={styles.colWhen} data-testid={`alert-row-${row.id}-when`}>
                  {formatWhen(locale, row.created_at)}
                </td>
                <td className={styles.colSeverity}>
                  <SeverityBadge severity={row.severity} testIdSuffix={String(row.id)} />
                </td>
                <td className={styles.colTrigger} data-testid={`alert-row-${row.id}-trigger`}>
                  {t(TRIGGER_LABEL_KEY[row.trigger_type] ?? "admin.alerts.trigger_disagree")}
                </td>
                <td className={styles.colTrainer}>
                  {row.trainer ? (
                    <>
                      <div>{row.trainer.email || `#${row.trainer.id ?? "?"}`}</div>
                      {row.trainer.role ? (
                        <div className={styles.metaLine}>{row.trainer.role}</div>
                      ) : null}
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td className={styles.colSubmission}>
                  {row.submission_id != null ? `#${row.submission_id}` : "—"}
                </td>
                <td className={styles.colStatus} data-testid={`alert-row-${row.id}-status`}>
                  <span
                    className={
                      row.status === "open" ? styles.statusOpen : styles.statusResolved
                    }
                  >
                    {t(STATUS_LABEL_KEY[row.status] ?? "admin.alerts.status_open")}
                  </span>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default AlertListPanel;
