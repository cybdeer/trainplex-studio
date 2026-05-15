/**
 * PayoutQueueDrawer — slide-in drawer listing pending Razorpay payouts.
 *
 * Phase 1 Step 6.4 + 4.2-5. Admin opens this from the PaymentStatus page
 * header. Surface allows:
 *   - Browse all pending / failed PayoutQueue entries.
 *   - Inspect Razorpay payout id (when sent) + last_error (when failed).
 *   - Trigger a manual retry on a stuck payout.
 *
 * Backend
 * -------
 *   GET  /api/v1/payments/payout-queue                    (admin-only)
 *   POST /api/v1/payments/payout-queue/<id>/retry         (admin-only)
 *
 * Both endpoints @require_role(['admin']); we additionally wrap in
 * RoleGate so a misrouted non-admin sees the 403 surface and the GET
 * never even fires.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { PayoutQueueResponse, PayoutQueueRow } from "./types";
import styles from "./PaymentStatus.module.css";

const QUEUE_QUERY_KEY = ["admin-payout-queue"];

export interface PayoutQueueDrawerProps {
  open: boolean;
  onClose: () => void;
}

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

export function PayoutQueueDrawer({ open, onClose }: PayoutQueueDrawerProps) {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);

  const { data, isFetching, isError, refetch } = useQuery<PayoutQueueResponse>({
    queryKey: QUEUE_QUERY_KEY,
    queryFn: async () => {
      const res = await api.callApi("adminPayoutQueue");
      return res as PayoutQueueResponse;
    },
    enabled: open && user?.role === "admin",
  });

  const retryMutation = useMutation({
    mutationFn: async (payoutId: number) => {
      return api.callApi("adminPayoutRetry", {
        params: { payout_id: payoutId },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUEUE_QUERY_KEY });
    },
  });

  // Focus the close button when the drawer opens (a11y).
  useEffect(() => {
    if (open && closeBtnRef.current) {
      closeBtnRef.current.focus();
    }
  }, [open]);

  // Escape closes.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <RoleGate
      allow={["admin"]}
      userRole={user?.role}
      fallback={
        <div className={styles.errorBox} data-testid="payout-drawer-forbidden">
          403 — admin only
        </div>
      }
    >
      <div
        className={styles.drawerBackdrop}
        onClick={onClose}
        data-testid="payout-drawer-backdrop"
      />
      <aside
        className={styles.drawerPanel}
        role="dialog"
        aria-modal="true"
        aria-label={t("admin.payments.payout_queue")}
        data-testid="payout-drawer-panel"
      >
        <header className={styles.drawerHeader}>
          <h2 className={styles.drawerTitle}>
            {t("admin.payments.payout_queue")}
            {data ? ` (${data.total})` : ""}
          </h2>
          <button
            ref={closeBtnRef}
            type="button"
            onClick={onClose}
            className={styles.drawerCloseBtn}
            aria-label={t("common.cancel")}
            data-testid="payout-drawer-close"
          >
            ×
          </button>
        </header>
        <div className={styles.drawerBody}>
          {isFetching && !data ? (
            <div className={styles.loadingBox} data-testid="payout-drawer-loading">
              <Spinner />
            </div>
          ) : isError || !data ? (
            <div className={styles.errorBox} data-testid="payout-drawer-error">
              {t("admin.payments.fetch_failed")}
              <button
                type="button"
                onClick={() => refetch()}
                className={styles.pageBtn}
                style={{ marginLeft: 8 }}
              >
                {t("common.retry")}
              </button>
            </div>
          ) : data.results.length === 0 ? (
            <div className={styles.emptyBox} data-testid="payout-drawer-empty">
              {t("admin.payments.no_payouts")}
            </div>
          ) : (
            data.results.map((row: PayoutQueueRow) => (
              <div
                key={row.id}
                className={styles.payoutRow}
                data-testid={`payout-row-${row.id}`}
              >
                <span className={styles.payoutAmount}>₹{row.amount_inr}</span>
                <span>
                  {t("admin.payments.col_trainer")}: #{row.trainer_id}
                  <br />
                  <small>{formatDateTime(row.created_at)}</small>
                </span>
                <span>
                  <span
                    className={`${styles.statusBadge} ${
                      row.status === "sent"
                        ? styles.statusBadgeReleased
                        : row.status === "failed"
                          ? styles.statusBadgeDisputed
                          : styles.statusBadgeHeld
                    }`}
                  >
                    {t(`admin.payments.payout_status_${row.status}`)}
                  </span>
                  {row.razorpay_payout_id && (
                    <div className={styles.razorpayId}>
                      {t("admin.payments.razorpay_id")}: {row.razorpay_payout_id}
                    </div>
                  )}
                  {row.retry_count > 0 && (
                    <small>
                      {t("admin.payments.retry_count", { count: row.retry_count })}
                    </small>
                  )}
                </span>
                <button
                  type="button"
                  className={styles.retryBtn}
                  onClick={() => retryMutation.mutate(row.id)}
                  disabled={retryMutation.isPending || row.status === "sent"}
                  data-testid={`payout-retry-${row.id}`}
                >
                  {t("admin.payments.retry")}
                </button>
              </div>
            ))
          )}
        </div>
      </aside>
    </RoleGate>
  );
}

export default PayoutQueueDrawer;
