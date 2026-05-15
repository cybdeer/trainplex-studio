/**
 * QualityAlertsPage — TrainPlex Admin Quality Alert Center.
 *
 * Phase 1 Step 4.2-8. Surfaces auto-flagged reviewer-disagreement /
 * time-anomaly / duplicate-answer-pattern signals for an admin to triage.
 *
 * Layout
 * ------
 *   Header  — title + total-open badge
 *   Stats   — 4 severity bucket cards (low/medium/high/critical)
 *   Filter  — status / severity / trigger / trainer-id
 *   Table   — sticky-header AlertListPanel
 *   Drawer  — AlertDetailDrawer (opens on row click, holds resolve form)
 *
 * Backend wiring
 * --------------
 *   GET  /api/v1/admin/quality-alerts             — list with filters
 *   GET  /api/v1/admin/quality-alerts/stats       — severity counts for widget
 *   POST /api/v1/admin/quality-alerts/<id>/review — resolve a single alert
 *
 * Both endpoints are admin-only via `@require_role(['admin'])`. We
 * additionally wrap this page in `<RoleGate allow={['admin']}>` so a
 * misrouted trainer/reviewer/QA-lead sees a 403 surface and never even
 * issues the GET.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { AlertDetailDrawer } from "./AlertDetailDrawer";
import { AlertFilterBar } from "./AlertFilterBar";
import { AlertListPanel } from "./AlertListPanel";
import type {
  AlertFilters,
  AlertResolution,
  AlertRow,
  AlertsListResponse,
  AlertsStatsResponse,
  AlertSeverity,
} from "./types";
import styles from "./QualityAlerts.module.css";

const LIST_QUERY_KEY_PREFIX = "admin-quality-alerts";
const STATS_QUERY_KEY = ["admin-quality-alerts-stats"];

const DEFAULT_FILTERS: AlertFilters = {
  status: "",
  severity: "",
  trigger_type: "",
  trainer_id: "",
  page: 1,
  page_size: 50,
};

/** Build the query params object the api wrapper sends. Strip empties. */
function buildQueryParams(filters: AlertFilters): Record<string, string | number> {
  const out: Record<string, string | number> = {};
  if (filters.status) out.status = filters.status;
  if (filters.severity) out.severity = filters.severity;
  if (filters.trigger_type) out.trigger_type = filters.trigger_type;
  if (filters.trainer_id) out.trainer_id = filters.trainer_id;
  out.page = filters.page ?? 1;
  out.page_size = filters.page_size ?? 50;
  return out;
}

const SEVERITY_ORDER: AlertSeverity[] = ["critical", "high", "medium", "low"];

const STAT_CARD_CLASS: Record<AlertSeverity, string> = {
  low: styles.statCardLow,
  medium: styles.statCardMedium,
  high: styles.statCardHigh,
  critical: styles.statCardCritical,
};

const STAT_CARD_LABEL_KEY: Record<AlertSeverity, string> = {
  low: "admin.alerts.severity_low",
  medium: "admin.alerts.severity_medium",
  high: "admin.alerts.severity_high",
  critical: "admin.alerts.severity_critical",
};

export const QualityAlertsPage: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [filters, setFilters] = useState<AlertFilters>(DEFAULT_FILTERS);
  const [selectedRow, setSelectedRow] = useState<AlertRow | null>(null);
  const [resolveBanner, setResolveBanner] = useState<string | null>(null);

  const params = useMemo(() => buildQueryParams(filters), [filters]);

  const listQuery = useQuery<AlertsListResponse>({
    queryKey: [LIST_QUERY_KEY_PREFIX, params],
    queryFn: async () => {
      const res = await api.callApi("adminQualityAlerts", { params });
      return res as AlertsListResponse;
    },
    keepPreviousData: true,
    enabled: user?.role === "admin",
  });

  const statsQuery = useQuery<AlertsStatsResponse>({
    queryKey: STATS_QUERY_KEY,
    queryFn: async () => {
      const res = await api.callApi("adminQualityAlertsStats");
      return res as AlertsStatsResponse;
    },
    enabled: user?.role === "admin",
  });

  const resolveMutation = useMutation<
    { ok: boolean; alert?: AlertRow; error?: string } | undefined,
    Error,
    { alertId: number; resolution: AlertResolution; notes: string }
  >({
    mutationFn: async ({ alertId, resolution, notes }) => {
      const res = (await api.callApi("adminQualityAlertReview", {
        params: { alert_id: alertId },
        body: { resolution, notes },
      })) as { ok: boolean; alert?: AlertRow; error?: string } | undefined;
      return res;
    },
    onSuccess: (res) => {
      if (!res || (res as any)?.error) {
        const msg = (res as any)?.error || t("admin.alerts.resolve_failed");
        setResolveBanner(msg);
        return;
      }
      setResolveBanner(null);
      setSelectedRow(null);
      // Re-fetch list + stats so the row's new status + counts are reflected.
      queryClient.invalidateQueries({ queryKey: [LIST_QUERY_KEY_PREFIX] });
      queryClient.invalidateQueries({ queryKey: STATS_QUERY_KEY });
    },
    onError: (err) => {
      setResolveBanner(err.message || t("admin.alerts.resolve_failed"));
    },
  });

  const totalPages = listQuery.data?.total_pages ?? 0;
  const currentPage = filters.page ?? 1;

  const handlePrev = () => {
    if (currentPage > 1) setFilters({ ...filters, page: currentPage - 1 });
  };
  const handleNext = () => {
    if (currentPage < totalPages) setFilters({ ...filters, page: currentPage + 1 });
  };

  const onResolve = (alertId: number, body: { resolution: AlertResolution; notes: string }) => {
    setResolveBanner(null);
    resolveMutation.mutate({ alertId, ...body });
  };

  const body = (() => {
    if (listQuery.isError) {
      return (
        <div className={styles.errorBox} data-testid="alerts-error">
          {t("admin.alerts.fetch_failed")}
        </div>
      );
    }

    return (
      <>
        {/* Stats strip — 4 severity buckets */}
        <section className={styles.statsStrip} data-testid="alerts-stats-strip">
          {SEVERITY_ORDER.map((sev) => (
            <div
              key={sev}
              className={`${styles.statCard} ${STAT_CARD_CLASS[sev]}`}
              data-testid={`alerts-stats-${sev}`}
            >
              <span className={styles.statCardLabel}>{t(STAT_CARD_LABEL_KEY[sev])}</span>
              <span className={styles.statCardCount}>
                {statsQuery.data?.open?.[sev] ?? 0}
              </span>
            </div>
          ))}
        </section>

        <AlertFilterBar
          filters={filters}
          onFiltersChange={setFilters}
          onReset={() => setFilters(DEFAULT_FILTERS)}
        />

        {resolveBanner ? (
          <div className={styles.errorBox} data-testid="alerts-resolve-banner">
            {resolveBanner}
          </div>
        ) : null}

        {listQuery.isFetching && !listQuery.data ? (
          <div className={styles.loadingBox} role="status" aria-live="polite" data-testid="alerts-loading">
            <Spinner />
            <span>{t("admin.alerts.loading")}</span>
          </div>
        ) : (
          <AlertListPanel
            rows={listQuery.data?.results ?? []}
            onRowClick={(r) => setSelectedRow(r)}
          />
        )}

        {listQuery.data ? (
          <nav className={styles.paginationBar} aria-label="pagination" data-testid="alerts-pagination">
            <span className={styles.paginationInfo} data-testid="alerts-total">
              {t("admin.alerts.total_count", { count: listQuery.data.total })}
            </span>
            <div className={styles.paginationControls}>
              <button
                type="button"
                className={styles.pageButton}
                data-testid="alerts-page-prev"
                onClick={handlePrev}
                disabled={currentPage <= 1}
              >
                {t("admin.alerts.prev_page")}
              </button>
              <span className={styles.pageLabel} data-testid="alerts-page-label">
                {t("admin.alerts.page_of", {
                  page: currentPage,
                  total: Math.max(totalPages, 1),
                })}
              </span>
              <button
                type="button"
                className={styles.pageButton}
                data-testid="alerts-page-next"
                onClick={handleNext}
                disabled={currentPage >= totalPages}
              >
                {t("admin.alerts.next_page")}
              </button>
            </div>
          </nav>
        ) : null}

        <AlertDetailDrawer
          row={selectedRow}
          onClose={() => setSelectedRow(null)}
          onResolve={onResolve}
          isResolving={resolveMutation.isPending}
        />
      </>
    );
  })();

  return (
    <main className={`p-6 ${styles.alertsRoot}`} data-testid="admin-quality-alerts">
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="alerts-forbidden">
            403 — admin only
          </div>
        }
      >
        <header className={styles.alertsHeader}>
          <h1 className={styles.alertsTitle}>{t("admin.alerts.title")}</h1>
          {statsQuery.data ? (
            <span className={styles.totalCount} data-testid="alerts-total-open">
              {t("admin.alerts.total_open", { count: statsQuery.data.total_open })}
            </span>
          ) : null}
        </header>
        {body}
      </RoleGate>
    </main>
  );
};

QualityAlertsPage.title = "Quality Alerts";
QualityAlertsPage.path = "/admin/quality-alerts";
QualityAlertsPage.exact = true;

export default QualityAlertsPage;
