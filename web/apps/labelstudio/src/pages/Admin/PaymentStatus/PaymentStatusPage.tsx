/**
 * PaymentStatusPage — TrainPlex Admin Payment Status table.
 *
 * Phase 1 Step 6.4 + 4.2-5. Surfaces every PaymentHold row with status
 * badge (held / released / disputed / refunded). Admin can:
 *   - Filter by status / trainer_id / task_id.
 *   - Page through rows.
 *   - Open the PayoutQueueDrawer for pending Razorpay payouts + retry.
 *
 * Backend
 * -------
 *   GET  /api/v1/admin/payment-status                — list + summary
 *   GET  /api/v1/payments/payout-queue               — drawer body
 *   POST /api/v1/payments/payout-queue/<id>/retry    — manual retry
 *
 * All endpoints @require_role(['admin']); we additionally wrap with
 * <RoleGate allow={['admin']}> so a misrouted non-admin sees the 403
 * surface and the GET never even fires.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { PaymentStatusTable } from "./PaymentStatusTable";
import { PayoutQueueDrawer } from "./PayoutQueueDrawer";
import {
  HOLD_STATUS_CHOICES,
  type PaymentHoldStatus,
  type PaymentStatusQuery,
  type PaymentStatusResponse,
} from "./types";
import styles from "./PaymentStatus.module.css";

const LIST_QUERY_KEY_PREFIX = "admin-payment-status";

const DEFAULT_FILTERS: PaymentStatusQuery = {
  status: "",
  trainer_id: "",
  task_id: "",
  page: 1,
  page_size: 50,
};

function buildQueryParams(
  filters: PaymentStatusQuery,
): Record<string, string | number> {
  const out: Record<string, string | number> = {};
  if (filters.status) out.status = filters.status;
  if (filters.trainer_id) out.trainer_id = filters.trainer_id;
  if (filters.task_id) out.task_id = filters.task_id;
  out.page = filters.page ?? 1;
  out.page_size = filters.page_size ?? 50;
  return out;
}

export const PaymentStatusPage: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();

  const [filters, setFilters] = useState<PaymentStatusQuery>(DEFAULT_FILTERS);
  const [queueOpen, setQueueOpen] = useState(false);

  const params = useMemo(() => buildQueryParams(filters), [filters]);

  const listQuery = useQuery<PaymentStatusResponse>({
    queryKey: [LIST_QUERY_KEY_PREFIX, params],
    queryFn: async () => {
      const res = await api.callApi("adminPaymentStatus", { params });
      return res as PaymentStatusResponse;
    },
    keepPreviousData: true,
    enabled: user?.role === "admin",
  });

  const summary = listQuery.data?.summary;

  return (
    <main className={styles.paymentRoot} data-testid="payment-status-page">
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="payment-status-forbidden">
            403 — admin only
          </div>
        }
      >
        <header className={styles.paymentHeader}>
          <h1 className={styles.paymentTitle}>
            {t("admin.payments.title")}
          </h1>
          <div className={styles.headerActions}>
            <span className={styles.totalCount} data-testid="payment-total-count">
              {listQuery.data
                ? t("admin.payments.total_count", { count: listQuery.data.total })
                : ""}
            </span>
            <button
              type="button"
              className={styles.payoutQueueBtn}
              onClick={() => setQueueOpen(true)}
              data-testid="payment-open-payout-queue"
            >
              {t("admin.payments.payout_queue")}
            </button>
          </div>
        </header>

        {summary && (
          <div className={styles.statsStrip} data-testid="payment-status-summary">
            <div className={`${styles.statCard} ${styles.statCardHeld}`}>
              <span className={styles.statCardLabel}>
                {t("admin.payments.status_held")}
              </span>
              <span className={styles.statCardCount}>{summary.held}</span>
            </div>
            <div className={`${styles.statCard} ${styles.statCardReleased}`}>
              <span className={styles.statCardLabel}>
                {t("admin.payments.status_released")}
              </span>
              <span className={styles.statCardCount}>{summary.released}</span>
            </div>
            <div className={`${styles.statCard} ${styles.statCardDisputed}`}>
              <span className={styles.statCardLabel}>
                {t("admin.payments.status_disputed")}
              </span>
              <span className={styles.statCardCount}>{summary.disputed}</span>
            </div>
            <div className={`${styles.statCard} ${styles.statCardRefunded}`}>
              <span className={styles.statCardLabel}>
                {t("admin.payments.status_refunded")}
              </span>
              <span className={styles.statCardCount}>{summary.refunded}</span>
            </div>
          </div>
        )}

        <div className={styles.filterBar} data-testid="payment-status-filter-bar">
          <div className={styles.filterField}>
            <label className={styles.filterLabel} htmlFor="payment-filter-status">
              {t("admin.payments.col_status")}
            </label>
            <select
              id="payment-filter-status"
              className={styles.filterSelect}
              value={filters.status ?? ""}
              data-testid="payment-filter-status"
              onChange={(e) =>
                setFilters((prev) => ({
                  ...prev,
                  status: (e.target.value as PaymentHoldStatus | "") || "",
                  page: 1,
                }))
              }
            >
              {HOLD_STATUS_CHOICES.map((c) => (
                <option key={c.value || "all"} value={c.value}>
                  {t(c.labelKey)}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.filterField}>
            <label className={styles.filterLabel} htmlFor="payment-filter-trainer">
              {t("admin.payments.col_trainer")}
            </label>
            <input
              id="payment-filter-trainer"
              className={styles.filterInput}
              type="number"
              min={1}
              placeholder="trainer id"
              data-testid="payment-filter-trainer"
              value={filters.trainer_id ?? ""}
              onChange={(e) => {
                const raw = e.target.value;
                setFilters((prev) => ({
                  ...prev,
                  trainer_id: raw ? Number(raw) : "",
                  page: 1,
                }));
              }}
            />
          </div>
          <div className={styles.filterField}>
            <label className={styles.filterLabel} htmlFor="payment-filter-task">
              {t("admin.payments.col_task")}
            </label>
            <input
              id="payment-filter-task"
              className={styles.filterInput}
              type="number"
              min={1}
              placeholder="task id"
              data-testid="payment-filter-task"
              value={filters.task_id ?? ""}
              onChange={(e) => {
                const raw = e.target.value;
                setFilters((prev) => ({
                  ...prev,
                  task_id: raw ? Number(raw) : "",
                  page: 1,
                }));
              }}
            />
          </div>
        </div>

        {listQuery.isFetching && !listQuery.data ? (
          <div className={styles.loadingBox} data-testid="payment-status-loading">
            <Spinner />
            <span style={{ marginLeft: 10 }}>{t("admin.payments.loading")}</span>
          </div>
        ) : listQuery.isError || !listQuery.data ? (
          <div className={styles.errorBox} data-testid="payment-status-error">
            {t("admin.payments.fetch_failed")}
          </div>
        ) : (
          <>
            <PaymentStatusTable rows={listQuery.data.results} />
            {listQuery.data.total_pages > 1 && (
              <div className={styles.pagination}>
                <span>
                  {t("admin.payments.page_of", {
                    page: listQuery.data.page,
                    total: listQuery.data.total_pages,
                  })}
                </span>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    className={styles.pageBtn}
                    disabled={listQuery.data.page <= 1}
                    onClick={() =>
                      setFilters((prev) => ({
                        ...prev,
                        page: Math.max(1, (prev.page ?? 1) - 1),
                      }))
                    }
                    data-testid="payment-prev-page"
                  >
                    {t("admin.payments.prev_page")}
                  </button>
                  <button
                    type="button"
                    className={styles.pageBtn}
                    disabled={listQuery.data.page >= listQuery.data.total_pages}
                    onClick={() =>
                      setFilters((prev) => ({
                        ...prev,
                        page: (prev.page ?? 1) + 1,
                      }))
                    }
                    data-testid="payment-next-page"
                  >
                    {t("admin.payments.next_page")}
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        <PayoutQueueDrawer open={queueOpen} onClose={() => setQueueOpen(false)} />
      </RoleGate>
    </main>
  );
};

PaymentStatusPage.title = "Payment Status";
PaymentStatusPage.path = "/admin/payment-status";
PaymentStatusPage.exact = true;

export default PaymentStatusPage;
