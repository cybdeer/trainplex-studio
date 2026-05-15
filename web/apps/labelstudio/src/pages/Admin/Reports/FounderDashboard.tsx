/**
 * FounderDashboard — TrainPlex Phase 1 Step 7.
 *
 * Founder weekly snapshot at `/admin/reports/founder`. Renders every section
 * the backend serves up under `/api/v1/admin/reports/founder-weekly`:
 *
 * 1. 4 top KPIs           — submissions, revenue, active trainers, avg payout
 * 2. 3 trend charts       — 7-day submissions, 6-month revenue MoM, growth
 * 3. Cohort retention     — 4-row heatmap
 * 4. Project ROI summary  — top-5 inline; full table at /admin/reports/project-roi
 * 5. Geographic split     — top states table
 * 6. Language split       — table
 * 7. Quality KPIs         — consensus / dispute rate + top-10 problematic
 *
 * Plus header CTA: PDF export. RoleGate-restricted to admin.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import type { FounderWeeklySnapshot, FounderTrendLines } from "./types";
import { MetricCard } from "./MetricCard";
import { TrendChart } from "./TrendChart";
import { CohortHeatmap } from "./CohortHeatmap";
import styles from "./Reports.module.css";

const QUERY_KEY = ["admin-reports-founder-weekly"];

const formatINR = (locale: string, v: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(v);

const formatInt = (locale: string, v: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(v);

const trendToChartPoints = (trends: FounderTrendLines) => ({
  submissions: trends.submissions_over_time.map((p) => ({
    label: p.date.slice(5), // "MM-DD"
    value: p.count,
  })),
  revenue: trends.revenue_mom.map((p) => ({
    label: p.month.slice(5), // "MM"
    value: p.revenue_inr,
  })),
  growth: trends.trainer_growth.map((p) => ({
    label: p.month.slice(5),
    value: p.active_trainers,
  })),
});

function FounderSkeleton({ label }: { label: string }) {
  return (
    <div className={styles.skeletonRoot} data-testid="founder-skeleton" role="status" aria-live="polite">
      <div className={styles.skeletonBar} style={{ height: 56 }} />
      <div className={styles.kpiRow}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className={styles.skeletonBar} style={{ height: 96 }} />
        ))}
      </div>
      <div className={styles.skeletonBar} style={{ height: 220 }} />
      <span className="sr-only">
        <Spinner /> {label}
      </span>
    </div>
  );
}

interface FounderBodyProps {
  data: FounderWeeklySnapshot;
  pdfHref: string;
}

function FounderBody({ data, pdfHref }: FounderBodyProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const trend = trendToChartPoints(data.trend_lines);

  return (
    <>
      <header className={styles.reportsHeader}>
        <h2 className={styles.reportsTitle}>{t("admin.reports.founder_weekly")}</h2>
        <div className={styles.actionBar}>
          <span data-testid="week-range" style={{ fontSize: "0.875rem", opacity: 0.85 }}>
            {data.week_start} — {data.week_end}
          </span>
          <a
            className={styles.exportBtn}
            href={pdfHref}
            data-testid="founder-export-pdf"
            target="_blank"
            rel="noreferrer"
          >
            {t("admin.reports.export_pdf")}
          </a>
        </div>
      </header>

      {/* KPI row */}
      <section className={styles.kpiRow} data-testid="founder-kpi-row">
        <MetricCard
          testId="kpi-submissions"
          label={t("admin.reports.kpi_submissions")}
          value={formatInt(locale, data.top_kpis.submissions_weekly)}
          deltaPct={data.top_kpis.submissions_delta_pct}
        />
        <MetricCard
          testId="kpi-revenue"
          label={t("admin.reports.kpi_revenue")}
          value={formatINR(locale, data.top_kpis.revenue_weekly_inr)}
          deltaPct={data.top_kpis.revenue_delta_pct}
        />
        <MetricCard
          testId="kpi-active-trainers"
          label={t("admin.reports.kpi_active_trainers")}
          value={formatInt(locale, data.top_kpis.active_trainers)}
          deltaPct={data.top_kpis.active_trainers_delta_pct}
        />
        <MetricCard
          testId="kpi-avg-payout"
          label={t("admin.reports.kpi_avg_payout")}
          value={formatINR(locale, data.top_kpis.avg_payout_per_trainer_inr)}
        />
      </section>

      {/* Trend charts */}
      <section className={styles.gridTwo}>
        <div className={styles.sectionBlock}>
          <h3 className={styles.sectionHeading}>{t("admin.reports.trend_submissions")}</h3>
          <TrendChart
            data={trend.submissions}
            formatY={(v) => formatInt(locale, v)}
            testId="trend-submissions"
            ariaLabel={t("admin.reports.trend_submissions")}
          />
        </div>
        <div className={styles.sectionBlock}>
          <h3 className={styles.sectionHeading}>{t("admin.reports.trend_revenue")}</h3>
          <TrendChart
            data={trend.revenue}
            formatY={(v) => formatINR(locale, v)}
            testId="trend-revenue"
            ariaLabel={t("admin.reports.trend_revenue")}
          />
        </div>
      </section>

      <section className={styles.sectionBlock}>
        <h3 className={styles.sectionHeading}>{t("admin.reports.trend_growth")}</h3>
        <TrendChart
          data={trend.growth}
          formatY={(v) => formatInt(locale, v)}
          testId="trend-growth"
          ariaLabel={t("admin.reports.trend_growth")}
        />
      </section>

      {/* Cohort retention heatmap */}
      <section className={styles.sectionBlock}>
        <h3 className={styles.sectionHeading}>{t("admin.reports.cohort_retention")}</h3>
        <CohortHeatmap waves={data.cohort_retention} testId="cohort-heatmap" />
      </section>

      {/* Project ROI summary */}
      <section className={styles.sectionBlock}>
        <h3 className={styles.sectionHeading}>{t("admin.reports.project_roi")}</h3>
        <div className={styles.tableContainer}>
          <table className={styles.dataTable} data-testid="founder-project-roi-table">
            <thead>
              <tr>
                <th>{t("admin.reports.project_name")}</th>
                <th className={styles.colNum}>{t("admin.reports.cost_inr")}</th>
                <th className={styles.colNum}>{t("admin.reports.revenue_inr")}</th>
                <th className={styles.colNum}>{t("admin.reports.roi_pct")}</th>
              </tr>
            </thead>
            <tbody>
              {data.project_roi.map((p) => (
                <tr key={p.project_id}>
                  <td>{p.project_name}</td>
                  <td className={styles.colNum}>{formatINR(locale, p.cost_inr)}</td>
                  <td className={styles.colNum}>{formatINR(locale, p.revenue_inr)}</td>
                  <td className={styles.colNum}>{p.roi_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Geographic + Language splits */}
      <section className={styles.gridTwo}>
        <div className={styles.sectionBlock}>
          <h3 className={styles.sectionHeading}>{t("admin.reports.geographic_split")}</h3>
          <div className={styles.tableContainer}>
            <table className={styles.dataTable} data-testid="founder-geo-table">
              <thead>
                <tr>
                  <th>{t("admin.reports.state")}</th>
                  <th className={styles.colNum}>{t("admin.reports.kpi_submissions")}</th>
                  <th className={styles.colNum}>{t("admin.reports.earnings_inr")}</th>
                </tr>
              </thead>
              <tbody>
                {data.geographic_split.map((g) => (
                  <tr key={g.state_code}>
                    <td>
                      {g.state_name} <span style={{ opacity: 0.6 }}>({g.state_code})</span>
                    </td>
                    <td className={styles.colNum}>{formatInt(locale, g.submissions)}</td>
                    <td className={styles.colNum}>{formatINR(locale, g.earnings_inr)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className={styles.sectionBlock}>
          <h3 className={styles.sectionHeading}>{t("admin.reports.language_split")}</h3>
          <div className={styles.tableContainer}>
            <table className={styles.dataTable} data-testid="founder-language-table">
              <thead>
                <tr>
                  <th>{t("admin.reports.language")}</th>
                  <th className={styles.colNum}>{t("admin.reports.kpi_submissions")}</th>
                  <th className={styles.colNum}>{t("admin.reports.quality_score")}</th>
                </tr>
              </thead>
              <tbody>
                {data.language_split.map((l) => (
                  <tr key={l.language_code}>
                    <td>{l.language_name}</td>
                    <td className={styles.colNum}>{formatInt(locale, l.submissions)}</td>
                    <td className={styles.colNum}>{l.avg_quality_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Quality KPIs + problematic trainers */}
      <section className={styles.sectionBlock}>
        <h3 className={styles.sectionHeading}>{t("admin.reports.quality_kpis")}</h3>
        <div className={styles.kpiRow}>
          <MetricCard
            testId="kpi-consensus"
            label={t("admin.reports.avg_consensus_pct")}
            value={`${data.quality_kpis.avg_consensus_pct}%`}
            deltaPct={data.quality_kpis.avg_consensus_pct_delta}
          />
          <MetricCard
            testId="kpi-dispute-rate"
            label={t("admin.reports.dispute_rate_pct")}
            value={`${data.quality_kpis.dispute_rate_pct}%`}
            deltaPct={data.quality_kpis.dispute_rate_pct_delta}
          />
        </div>
        <h4 className={styles.sectionHeading} style={{ marginTop: 16 }}>
          {t("admin.reports.top_problematic")}
        </h4>
        <div className={styles.tableContainer}>
          <table className={styles.dataTable} data-testid="founder-problematic-table">
            <thead>
              <tr>
                <th>{t("admin.reports.trainer")}</th>
                <th>{t("admin.reports.state")}</th>
                <th className={styles.colNum}>{t("admin.reports.dispute_count")}</th>
                <th className={styles.colNum}>{t("admin.reports.dispute_rate_pct")}</th>
              </tr>
            </thead>
            <tbody>
              {data.quality_kpis.top_10_problematic.map((p) => (
                <tr key={p.trainer_id}>
                  <td>{p.name}</td>
                  <td>{p.state}</td>
                  <td className={styles.colNum}>{p.dispute_count}</td>
                  <td className={styles.colNum}>{p.dispute_rate_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

export const FounderDashboard: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();

  const { data, isFetching, isError } = useQuery<FounderWeeklySnapshot>({
    queryKey: QUERY_KEY,
    queryFn: async () => {
      const res = await api.callApi("adminReportsFounderWeekly");
      return res as FounderWeeklySnapshot;
    },
    staleTime: 5 * 60 * 1000,
    enabled: user?.role === "admin",
  });

  // The PDF endpoint is served by the same backend; the route registered in
  // ApiConfig.js maps "adminReportsFounderWeeklyPdf" → the .pdf URL. We
  // resolve manually so the export anchor points at the actual file. We use
  // a same-origin relative URL so the founder's session cookie travels.
  const pdfHref = "/api/v1/admin/reports/founder-weekly.pdf";

  return (
    <main className={styles.reportsRoot} data-testid="founder-dashboard">
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="founder-forbidden">
            403 — admin only
          </div>
        }
      >
        {isFetching && !data ? (
          <FounderSkeleton label={t("admin.reports.loading_snapshot")} />
        ) : isError || !data ? (
          <div className={styles.errorBox} data-testid="founder-error">
            {t("admin.reports.snapshot_failed")}
          </div>
        ) : (
          <FounderBody data={data} pdfHref={pdfHref} />
        )}
      </RoleGate>
    </main>
  );
};

FounderDashboard.title = "Founder Weekly";
FounderDashboard.path = "/admin/reports/founder";
FounderDashboard.exact = true;

export default FounderDashboard;
