/**
 * DashboardWidget — TrainPlex founder ops snapshot.
 *
 * Phase 1 Step 4.2-1. Login hote hi: aaj ke submissions, kitne pay-hold,
 * top 5 trainers state-wise, alerts ka counter — sab ek screen pe.
 *
 * Layout
 * ------
 *   ┌────────────────────────────────────────────┐
 *   │ Today's snapshot                           │  ← Indigo header
 *   ├────────┬────────┬────────┬─────────────────┤
 *   │ Submi… │ Active │ Pay    │ Alerts (3)      │  ← 4-tile KPI row
 *   │ 142 ▲  │  47    │ ₹4,200 │                 │
 *   ├────────┴────────┴────────┴─────────────────┤
 *   │ Top 5 trainers (state-wise)                │
 *   │ ┌──┬──┬───────────┬──────────────────────┐ │
 *   │ │N │S │Tasks today│Earnings today        │ │
 *   ├────────────────────────────────────────────┤
 *   │ Quick actions:                             │
 *   │ [ New Project ] [ WA Broadcast ] [ Bulk… ] │  ← Orange CTA
 *   └────────────────────────────────────────────┘
 *
 * Data
 * ----
 * Fetches `GET /api/v1/admin/dashboard/snapshot` (admin-only). For Phase 1 the
 * backend returns deterministic mock data; the contract is pinned by backend
 * tests so the frontend stays stable when real wiring lands in Phase 2.
 */

import { Button, RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { MetricCard } from "./MetricCard";
import { TopTrainersTable } from "./TopTrainersTable";
import type { DashboardSnapshot } from "./types";
import styles from "./DashboardWidget.module.css";

const QUERY_KEY = ["admin-dashboard-snapshot"];

const formatINR = (locale: string, value: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);

const formatInt = (locale: string, value: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(value);

/**
 * Loading skeleton — keeps layout stable while the snapshot is in-flight so
 * the founder doesn't see a layout shift on login.
 */
function DashboardSkeleton({ loadingLabel }: { loadingLabel: string }) {
  return (
    <div className={styles.skeletonRoot} data-testid="dashboard-skeleton" role="status" aria-live="polite">
      <div className={styles.skeletonHeader} />
      <div className={styles.skeletonKpiRow}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className={styles.skeletonTile} />
        ))}
      </div>
      <div className={styles.skeletonTable} />
      <span className={styles.srOnly}>
        <Spinner /> {loadingLabel}
      </span>
    </div>
  );
}

interface DashboardBodyProps {
  data: DashboardSnapshot;
}

function DashboardBody({ data }: DashboardBodyProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const totalAlerts =
    data.alerts.disputes_pending +
    data.alerts.quality_flags +
    data.alerts.stuck_payouts;

  return (
    <>
      <header className={styles.dashboardHeader}>
        <h2 className={styles.dashboardTitle}>{t("admin.dashboard.today_snapshot")}</h2>
        <span className={styles.asOf} data-testid="as-of">
          {new Date(data.as_of).toLocaleString(locale === "hi" ? "hi-IN" : "en-IN")}
        </span>
      </header>

      {/* 4-tile KPI row */}
      <section className={styles.kpiRow} data-testid="kpi-row">
        <MetricCard
          testId="kpi-submissions"
          label={t("admin.dashboard.submissions")}
          value={formatInt(locale, data.today.submissions_count)}
          deltaPct={data.today.submissions_delta_pct}
        />
        <MetricCard
          testId="kpi-active-trainers"
          label={t("admin.dashboard.active_trainers")}
          value={formatInt(locale, data.today.active_trainers)}
        />
        <MetricCard
          testId="kpi-pay-hold"
          label={t("admin.dashboard.pay_hold")}
          value={formatINR(locale, data.today.pay_hold_total_inr)}
          tone={data.today.pay_hold_total_inr > 0 ? "warning" : "default"}
        />
        <MetricCard
          testId="kpi-alerts"
          label={t("admin.dashboard.alerts")}
          value={formatInt(locale, totalAlerts)}
          tone={totalAlerts > 0 ? "danger" : "default"}
        />
      </section>

      {/* Top trainers */}
      <TopTrainersTable trainers={data.top_trainers} />

      {/* Alert detail row — small chips so founder sees the breakdown without leaving screen */}
      <section className={styles.alertsBreakdown} aria-label={t("admin.dashboard.alerts")}>
        <span className={styles.alertChip} data-testid="alert-disputes">
          {t("admin.dashboard.disputes_pending")}: {data.alerts.disputes_pending}
        </span>
        <span className={styles.alertChip} data-testid="alert-quality">
          {t("admin.dashboard.quality_flags")}: {data.alerts.quality_flags}
        </span>
        <span className={styles.alertChip} data-testid="alert-stuck">
          {t("admin.dashboard.stuck_payouts")}: {data.alerts.stuck_payouts}
        </span>
      </section>

      {/* Quick actions — buttons only, no handlers yet (placeholders to /projects etc) */}
      <section className={styles.quickActions} aria-label={t("admin.dashboard.quick_actions")}>
        <h3 className={styles.sectionHeading}>{t("admin.dashboard.quick_actions")}</h3>
        <div className={styles.quickActionRow}>
          <Link to="/projects" data-testid="qa-new-project">
            <Button look="filled" size="medium" className={styles.ctaPrimary}>
              {t("admin.dashboard.new_project")}
            </Button>
          </Link>
          {/* Placeholders — wired in later phases. Keep them as <Button disabled> so
              the founder sees the surface but can't no-op the click. */}
          <Button
            look="outlined"
            size="medium"
            disabled
            aria-disabled="true"
            data-testid="qa-wa-broadcast"
          >
            {t("admin.dashboard.wa_broadcast")}
          </Button>
          <Button
            look="outlined"
            size="medium"
            disabled
            aria-disabled="true"
            data-testid="qa-bulk-assign"
          >
            {t("admin.dashboard.bulk_assign")}
          </Button>
        </div>
      </section>
    </>
  );
}

export const DashboardWidget: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();

  const { data, isFetching, isError } = useQuery<DashboardSnapshot>({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      // Use the LS API gateway (rooted at `${hostname}/api`) — endpoint
      // resolves to `/api/v1/admin/dashboard/snapshot`.
      const res = await api.callApi("adminDashboardSnapshot");
      return res as DashboardSnapshot;
    },
    // Snapshot is "right now"; let it stay fresh across short tab switches.
    staleTime: 30_000,
    // Backend already 403's non-admins; only fire the query for admins.
    enabled: user?.role === "admin",
  });

  return (
    <main className={`p-6 ${styles.dashboardRoot}`} data-testid="admin-dashboard-widget">
      {/* Step 1.4-B — RoleGate hides the dashboard for non-admins. The backend
          still 403's per request, but this prevents the UI from even surfacing
          founder-only data to a misrouted trainer/reviewer/QA-lead. */}
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="dashboard-forbidden">
            403 — admin only
          </div>
        }
      >
        {isFetching && !data ? (
          <DashboardSkeleton loadingLabel={t("admin.dashboard.loading_snapshot")} />
        ) : isError || !data ? (
          <div className={styles.errorBox} data-testid="dashboard-error">
            {t("admin.dashboard.snapshot_failed")}
          </div>
        ) : (
          <DashboardBody data={data} />
        )}
      </RoleGate>
    </main>
  );
};

DashboardWidget.title = "Dashboard";
DashboardWidget.path = "/admin/dashboard";
DashboardWidget.exact = true;

export default DashboardWidget;
