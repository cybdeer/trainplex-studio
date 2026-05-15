/**
 * AuditTable — sticky-header table for the audit-log viewer.
 *
 * Phase 1 Step 4.2-4. Pure presentational: receives rows + click handler,
 * renders the table. Pagination + filtering live in the parent.
 *
 * Columns (left → right):
 *   When   | Who           | Did what    | On         | From IP | Status
 *   2026…  | user@x.com    | login_fail  | User       | 1.2.3.4 | Failed
 *
 * Failed rows get a subtle red tint so the founder spots them at a glance.
 */

import { useTranslation } from "@humansignal/app-common";
import type { AuditRow } from "./types";
import styles from "./AuditLog.module.css";

export interface AuditTableProps {
  rows: AuditRow[];
  onRowClick: (row: AuditRow) => void;
  emptyMessage?: string;
}

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

export function AuditTable({ rows, onRowClick, emptyMessage }: AuditTableProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";

  return (
    <div className={styles.tableWrap} data-testid="audit-table">
      <table className={styles.auditTable}>
        <thead>
          <tr>
            <th className={styles.colWhen}>{t("admin.audit.col_when")}</th>
            <th className={styles.colActor}>{t("admin.audit.col_actor")}</th>
            <th className={styles.colAction}>{t("admin.audit.col_action")}</th>
            <th className={styles.colTarget}>{t("admin.audit.col_target")}</th>
            <th className={styles.colIp}>{t("admin.audit.col_ip")}</th>
            <th className={styles.colStatus}>{t("admin.audit.col_success")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={6} className={styles.emptyRow} data-testid="audit-empty">
                {emptyMessage ?? t("admin.audit.no_results")}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={row.id}
                data-testid={`audit-row-${row.id}`}
                className={!row.success ? styles.failedRow : undefined}
                onClick={() => onRowClick(row)}
                tabIndex={0}
                role="button"
                aria-label={`${row.action} ${row.actor?.email ?? "anonymous"}`}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onRowClick(row);
                  }
                }}
              >
                <td className={styles.colWhen} data-testid={`audit-row-${row.id}-when`}>
                  {formatWhen(locale, row.created_at)}
                </td>
                <td className={styles.colActor} data-testid={`audit-row-${row.id}-actor`}>
                  {row.actor ? (
                    <>
                      <div>{row.actor.email || "—"}</div>
                      {row.actor.role ? (
                        <div className={styles.drawerLabel}>{row.actor.role}</div>
                      ) : null}
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td className={styles.colAction}>
                  <span className={styles.actionChip}>{row.action}</span>
                </td>
                <td className={styles.colTarget}>
                  {row.target_type || "—"}
                  {row.target_id ? <span> #{row.target_id}</span> : null}
                </td>
                <td className={styles.colIp}>{row.ip_address || "—"}</td>
                <td className={styles.colStatus}>
                  {row.success ? (
                    <span className={styles.successBadge} data-testid={`audit-row-${row.id}-status`}>
                      {t("admin.audit.success_yes")}
                    </span>
                  ) : (
                    <span className={styles.failedBadge} data-testid={`audit-row-${row.id}-status`}>
                      {t("admin.audit.success_no")}
                    </span>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default AuditTable;
