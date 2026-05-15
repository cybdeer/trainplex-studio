/**
 * PaymentStatusTable — sticky-header list of PaymentHold rows.
 *
 * Phase 1 Step 6.4 + 4.2-5. Renders the response of
 * `GET /api/v1/admin/payment-status`. Status badges use the founder palette:
 *   held=orange, released=green, disputed=red, refunded=grey.
 */

import { useTranslation } from "@humansignal/app-common";
import type { PaymentHoldStatus, PaymentStatusRow } from "./types";
import styles from "./PaymentStatus.module.css";

const STATUS_BADGE_CLASS: Record<PaymentHoldStatus, string> = {
  held: styles.statusBadgeHeld,
  released: styles.statusBadgeReleased,
  disputed: styles.statusBadgeDisputed,
  refunded: styles.statusBadgeRefunded,
};

const STATUS_I18N_KEY: Record<PaymentHoldStatus, string> = {
  held: "admin.payments.status_held",
  released: "admin.payments.status_released",
  disputed: "admin.payments.status_disputed",
  refunded: "admin.payments.status_refunded",
};

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

export interface PaymentStatusTableProps {
  rows: PaymentStatusRow[];
}

export function PaymentStatusTable({ rows }: PaymentStatusTableProps) {
  const { t } = useTranslation();

  if (rows.length === 0) {
    return (
      <div className={styles.emptyBox} data-testid="payment-status-empty">
        {t("admin.payments.no_rows")}
      </div>
    );
  }

  return (
    <table className={styles.paymentTable} data-testid="payment-status-table">
      <thead>
        <tr>
          <th>{t("admin.payments.col_task")}</th>
          <th>{t("admin.payments.col_trainer")}</th>
          <th>{t("admin.payments.col_amount")}</th>
          <th>{t("admin.payments.col_status")}</th>
          <th>{t("admin.payments.col_held_at")}</th>
          <th>{t("admin.payments.col_released_at")}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id} data-testid={`payment-status-row-${row.id}`}>
            <td>#{row.task_id}</td>
            <td>#{row.trainer_id}</td>
            <td>₹{row.amount_inr}</td>
            <td>
              <span
                className={`${styles.statusBadge} ${STATUS_BADGE_CLASS[row.status]}`}
                data-testid={`payment-status-badge-${row.id}`}
              >
                {t(STATUS_I18N_KEY[row.status])}
              </span>
            </td>
            <td>{formatDateTime(row.held_at)}</td>
            <td>{formatDateTime(row.released_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
