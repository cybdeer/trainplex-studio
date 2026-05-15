/**
 * BroadcastHistoryDrawer — Slide-out list of past WA broadcasts.
 *
 * Phase 1 Step 4.2-7. Fetches `/api/v1/admin/wa/broadcast/history` lazily
 * (only when the drawer opens) so the page initial-render is cheap. Status
 * chips reuse the WA Green / red / amber palette from the module CSS.
 */

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "@humansignal/app-common";
import { useAPI } from "../../../providers/ApiProvider";
import type { WaBroadcastLogRow, WaHistoryResponse } from "./types";
import styles from "./WhatsAppBroadcast.module.css";

export interface BroadcastHistoryDrawerProps {
  open: boolean;
  onClose: () => void;
}

const HISTORY_QUERY_KEY = ["admin-wa-broadcast-history"];

function statusLabel(t: (k: string) => string, status: WaBroadcastLogRow["status"]): string {
  if (status === "sent") return t("admin.wa.status_sent");
  if (status === "failed") return t("admin.wa.status_failed");
  if (status === "skipped") return t("admin.wa.status_skipped");
  return status;
}

function statusClass(status: WaBroadcastLogRow["status"]): string {
  if (status === "sent") return styles.status_sent;
  if (status === "failed") return styles.status_failed;
  if (status === "skipped") return styles.status_skipped;
  return styles.status_queued;
}

export function BroadcastHistoryDrawer({ open, onClose }: BroadcastHistoryDrawerProps) {
  const api = useAPI();
  const { t, i18n } = useTranslation();

  const { data, isFetching } = useQuery<WaHistoryResponse>({
    queryKey: HISTORY_QUERY_KEY,
    queryFn: async () => {
      const res = await api.callApi("adminWaBroadcastHistory");
      return res as WaHistoryResponse;
    },
    enabled: open,
    staleTime: 30_000,
  });

  if (!open) return null;

  const items: WaBroadcastLogRow[] = data?.items ?? [];

  return (
    <>
      <div
        className={styles.drawerBackdrop}
        data-testid="wa-history-backdrop"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={styles.drawer}
        data-testid="wa-history-drawer"
        role="dialog"
        aria-labelledby="wa-history-heading"
      >
        <header className={styles.drawerHeader}>
          <h2 id="wa-history-heading" className={styles.drawerHeading}>
            {t("admin.wa.history")}
          </h2>
          <button
            type="button"
            className={styles.drawerClose}
            onClick={onClose}
            aria-label="Close"
            data-testid="wa-history-close"
          >
            ×
          </button>
        </header>
        <div className={styles.drawerBody}>
          {isFetching && !data ? (
            <div className={styles.loadingBox} data-testid="wa-history-loading">
              Loading…
            </div>
          ) : items.length === 0 ? (
            <div className={styles.historyEmpty} data-testid="wa-history-empty">
              {/* Reuse the generic empty-state copy from i18n. */}
              {t("admin.wa.history")} —
            </div>
          ) : (
            items.map((row) => (
              <div
                key={row.id}
                className={styles.historyRow}
                data-testid={`wa-history-row-${row.id}`}
              >
                <div>
                  <strong>{row.template_id}</strong>{" "}
                  <span className={`${styles.statusChip} ${statusClass(row.status)}`}>
                    {statusLabel(t, row.status)}
                  </span>
                </div>
                <div className={styles.historyMeta}>
                  <span>#{row.trainer_id}</span>
                  <span>{row.mobile_number || "—"}</span>
                  <span>
                    {new Date(row.created_at).toLocaleString(
                      i18n.language === "hi" ? "hi-IN" : "en-IN",
                    )}
                  </span>
                </div>
                {row.error ? (
                  <div className={styles.historyMeta} data-testid={`wa-history-error-${row.id}`}>
                    {row.error}
                  </div>
                ) : null}
              </div>
            ))
          )}
        </div>
      </aside>
    </>
  );
}

export default BroadcastHistoryDrawer;
