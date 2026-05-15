/**
 * ProjectROI — TrainPlex Phase 1 Step 7.
 *
 * Per-project ROI table + drilldown panel at `/admin/reports/project-roi`.
 * The detail panel renders inline (no separate route) so the founder can
 * scan rows + click into a project without losing the table context. PDF
 * export anchor on the detail panel.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import type { ProjectROIList, ProjectROIRow } from "./types";
import { MetricCard } from "./MetricCard";
import styles from "./Reports.module.css";

const formatINR = (locale: string, v: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(v);

const formatInt = (locale: string, v: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(v);

interface DetailPanelProps {
  row: ProjectROIRow;
}

function DetailPanel({ row }: DetailPanelProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const pdfHref = `/api/v1/admin/reports/project-roi/${row.project_id}.pdf`;

  return (
    <section className={styles.sectionBlock} data-testid={`roi-detail-${row.project_id}`}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3 className={styles.sectionHeading} style={{ margin: 0 }}>
          #{row.project_id} {row.project_name}
        </h3>
        <a
          href={pdfHref}
          className={styles.exportBtn}
          data-testid={`roi-export-pdf-${row.project_id}`}
          target="_blank"
          rel="noreferrer"
        >
          {t("admin.reports.export_pdf")}
        </a>
      </div>
      <div className={styles.kpiRow}>
        <MetricCard
          testId={`roi-card-cost-${row.project_id}`}
          label={t("admin.reports.total_cost")}
          value={formatINR(locale, row.total_cost_inr)}
        />
        <MetricCard
          testId={`roi-card-revenue-${row.project_id}`}
          label={t("admin.reports.revenue_inr")}
          value={formatINR(locale, row.external_revenue_inr)}
        />
        <MetricCard
          testId={`roi-card-profit-${row.project_id}`}
          label={t("admin.reports.profit_inr")}
          value={formatINR(locale, row.profit_inr)}
        />
        <MetricCard
          testId={`roi-card-roi-${row.project_id}`}
          label={t("admin.reports.roi_pct")}
          value={`${row.roi_pct}%`}
        />
      </div>

      <div className={styles.gridTwo} style={{ marginTop: 16 }}>
        <div>
          <h4 className={styles.sectionHeading} style={{ fontSize: "0.9rem" }}>
            {t("admin.reports.throughput")}
          </h4>
          <table className={styles.dataTable}>
            <tbody>
              <tr>
                <td>{t("admin.reports.tasks_created")}</td>
                <td className={styles.colNum}>{formatInt(locale, row.tasks_created)}</td>
              </tr>
              <tr>
                <td>{t("admin.reports.tasks_completed")}</td>
                <td className={styles.colNum}>{formatInt(locale, row.tasks_completed)}</td>
              </tr>
              <tr>
                <td>{t("admin.reports.quality_score")}</td>
                <td className={styles.colNum}>{row.quality_score_pct}%</td>
              </tr>
              <tr>
                <td>{t("admin.reports.time_to_complete_days")}</td>
                <td className={styles.colNum}>{row.time_to_complete_days}</td>
              </tr>
              <tr>
                <td>{t("admin.reports.cost_per_task")}</td>
                <td className={styles.colNum}>
                  {formatINR(locale, row.cost_per_quality_task_inr)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div>
          <h4 className={styles.sectionHeading} style={{ fontSize: "0.9rem" }}>
            {t("admin.reports.cost_breakdown")}
          </h4>
          <table className={styles.dataTable}>
            <tbody>
              <tr>
                <td>{t("admin.reports.trainer_payout")}</td>
                <td className={styles.colNum}>{formatINR(locale, row.trainer_payout_inr)}</td>
              </tr>
              <tr>
                <td>{t("admin.reports.reviewer_payout")}</td>
                <td className={styles.colNum}>{formatINR(locale, row.reviewer_payout_inr)}</td>
              </tr>
              <tr>
                <td>{t("admin.reports.infra_cost")}</td>
                <td className={styles.colNum}>{formatINR(locale, row.infra_cost_inr)}</td>
              </tr>
              <tr style={{ fontWeight: 600 }}>
                <td>{t("admin.reports.total_cost")}</td>
                <td className={styles.colNum}>{formatINR(locale, row.total_cost_inr)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export const ProjectROI: Page = () => {
  const api = useAPI();
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const locale = i18n.language || "en";

  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data, isFetching, isError } = useQuery<ProjectROIList>({
    queryKey: ["admin-reports-project-roi-list"],
    queryFn: async () => {
      const res = await api.callApi("adminReportsProjectROIList");
      return res as ProjectROIList;
    },
    staleTime: 5 * 60 * 1000,
    enabled: user?.role === "admin",
  });

  const selected = useMemo<ProjectROIRow | null>(() => {
    if (!data || selectedId === null) return null;
    return data.results.find((r) => r.project_id === selectedId) ?? null;
  }, [data, selectedId]);

  return (
    <main className={styles.reportsRoot} data-testid="project-roi-page">
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="roi-forbidden">
            403 — admin only
          </div>
        }
      >
        <header className={styles.reportsHeader}>
          <h2 className={styles.reportsTitle}>{t("admin.reports.project_roi")}</h2>
        </header>

        {isFetching && !data ? (
          <div className={styles.skeletonRoot} data-testid="roi-skeleton">
            <Spinner />
            <span className="sr-only">{t("admin.reports.loading_snapshot")}</span>
            <div className={styles.skeletonBar} style={{ height: 320 }} />
          </div>
        ) : isError || !data ? (
          <div className={styles.errorBox} data-testid="roi-error">
            {t("admin.reports.snapshot_failed")}
          </div>
        ) : (
          <>
            <section className={styles.sectionBlock}>
              <h3 className={styles.sectionHeading}>
                {t("admin.reports.roi_overview")}
              </h3>
              <div className={styles.tableContainer}>
                <table className={styles.dataTable} data-testid="roi-table">
                  <thead>
                    <tr>
                      <th>{t("admin.reports.project_name")}</th>
                      <th>{t("admin.reports.project_type")}</th>
                      <th className={styles.colNum}>{t("admin.reports.tasks_completed")}</th>
                      <th className={styles.colNum}>{t("admin.reports.total_cost")}</th>
                      <th className={styles.colNum}>{t("admin.reports.revenue_inr")}</th>
                      <th className={styles.colNum}>{t("admin.reports.roi_pct")}</th>
                      <th className={styles.colNum}>{t("admin.reports.cost_per_task")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((r) => (
                      <tr
                        key={r.project_id}
                        onClick={() => setSelectedId(r.project_id)}
                        data-testid={`roi-row-${r.project_id}`}
                        style={{ cursor: "pointer" }}
                        aria-selected={selectedId === r.project_id}
                      >
                        <td>{r.project_name}</td>
                        <td>{r.project_type}</td>
                        <td className={styles.colNum}>{formatInt(locale, r.tasks_completed)}</td>
                        <td className={styles.colNum}>{formatINR(locale, r.total_cost_inr)}</td>
                        <td className={styles.colNum}>{formatINR(locale, r.external_revenue_inr)}</td>
                        <td className={styles.colNum}>{r.roi_pct}%</td>
                        <td className={styles.colNum}>
                          {formatINR(locale, r.cost_per_quality_task_inr)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {selected && <DetailPanel row={selected} />}
          </>
        )}
      </RoleGate>
    </main>
  );
};

ProjectROI.title = "Project ROI";
ProjectROI.path = "/admin/reports/project-roi";
ProjectROI.exact = true;

export default ProjectROI;
