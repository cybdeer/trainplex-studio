/**
 * CohortAnalysis — TrainPlex Phase 1 Step 7.
 *
 * Cohort retention + productivity at `/admin/reports/cohorts`. Pills for the
 * 3 cohort definitions; per-cohort retention heatmap + drop-off table.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import type { CohortsPayload } from "./types";
import styles from "./Reports.module.css";

type CohortDefinition = CohortsPayload["cohort_definition"];

const DEFINITIONS: CohortDefinition[] = [
  "signup_wave",
  "registration_week",
  "tier_promotion_month",
];

const formatINR = (locale: string, v: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(v);

const toneClassForPct = (pct: number): string => {
  if (pct >= 90) return styles.tone90;
  if (pct >= 80) return styles.tone80;
  if (pct >= 70) return styles.tone70;
  if (pct >= 60) return styles.tone60;
  if (pct >= 50) return styles.tone50;
  if (pct >= 40) return styles.tone40;
  if (pct >= 30) return styles.tone30;
  return styles.toneLow;
};

export const CohortAnalysis: Page = () => {
  const api = useAPI();
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const locale = i18n.language || "en";

  const [definition, setDefinition] = useState<CohortDefinition>("signup_wave");

  const { data, isFetching, isError } = useQuery<CohortsPayload>({
    queryKey: ["admin-reports-cohorts", definition],
    queryFn: async () => {
      const res = await api.callApi("adminReportsCohorts", {
        params: { cohort_definition: definition },
      });
      return res as CohortsPayload;
    },
    staleTime: 5 * 60 * 1000,
    enabled: user?.role === "admin",
  });

  return (
    <main className={styles.reportsRoot} data-testid="cohort-analysis-page">
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="cohorts-forbidden">
            403 — admin only
          </div>
        }
      >
        <header className={styles.reportsHeader}>
          <h2 className={styles.reportsTitle}>{t("admin.reports.cohorts")}</h2>
          <div className={styles.actionBar}>
            <div className={styles.periodPills} role="group" aria-label={t("admin.reports.cohort_definition")}>
              {DEFINITIONS.map((d) => (
                <button
                  key={d}
                  type="button"
                  data-testid={`cohort-def-${d}`}
                  className={`${styles.periodPill} ${definition === d ? styles.periodPillActive : ""}`}
                  onClick={() => setDefinition(d)}
                  aria-pressed={definition === d}
                >
                  {t(`admin.reports.cohort_def_${d}`)}
                </button>
              ))}
            </div>
          </div>
        </header>

        {isFetching && !data ? (
          <div className={styles.skeletonRoot} data-testid="cohorts-skeleton">
            <Spinner />
            <span className="sr-only">{t("admin.reports.loading_snapshot")}</span>
            <div className={styles.skeletonBar} style={{ height: 320 }} />
          </div>
        ) : isError || !data ? (
          <div className={styles.errorBox} data-testid="cohorts-error">
            {t("admin.reports.snapshot_failed")}
          </div>
        ) : (
          <>
            {/* Overall retention heatmap — 4 cells per cohort */}
            <section className={styles.sectionBlock}>
              <h3 className={styles.sectionHeading}>{t("admin.reports.cohort_retention")}</h3>
              <div
                className={styles.cohortHeatmap}
                role="table"
                data-testid="cohort-overview-heatmap"
                aria-label={t("admin.reports.cohort_retention")}
              >
                <div className={styles.cohortHeaderCell} role="columnheader">
                  {t("admin.reports.cohort_wave")}
                </div>
                <div className={styles.cohortHeaderCell} role="columnheader">
                  {t("admin.reports.cohort_day_7")}
                </div>
                <div className={styles.cohortHeaderCell} role="columnheader">
                  {t("admin.reports.cohort_day_30")}
                </div>
                <div className={styles.cohortHeaderCell} role="columnheader">
                  {t("admin.reports.cohort_day_60")}
                </div>
                <div className={styles.cohortHeaderCell} role="columnheader">
                  {t("admin.reports.cohort_day_90")}
                </div>
                {data.cohorts.map((c) => {
                  const points = c.retention_curve;
                  return (
                    <div role="row" key={c.cohort_id} style={{ display: "contents" }}>
                      <div className={styles.cohortLabelCell} role="cell">
                        <span>{c.cohort_name}</span>
                        <span className={styles.cohortCohortSize}>
                          {t("admin.reports.cohort_size_n", { count: c.cohort_size })}
                        </span>
                      </div>
                      {points.map((p) => (
                        <div
                          key={p.day}
                          className={`${styles.cohortRetentionCell} ${toneClassForPct(p.retention_pct)}`}
                          role="cell"
                          data-testid={`cohort-${c.cohort_id}-d${p.day}`}
                        >
                          {p.retention_pct}%
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Per-cohort detail: drop-off + cumulative earnings */}
            {data.cohorts.map((c) => (
              <section key={c.cohort_id} className={styles.sectionBlock} data-testid={`cohort-detail-${c.cohort_id}`}>
                <h3 className={styles.sectionHeading}>
                  {c.cohort_name} — {t("admin.reports.cohort_size_n", { count: c.cohort_size })}
                </h3>
                <div className={styles.gridTwo}>
                  <div>
                    <h4 className={styles.sectionHeading} style={{ fontSize: "0.9rem" }}>
                      {t("admin.reports.drop_off")}
                    </h4>
                    <div className={styles.tableContainer}>
                      <table className={styles.dataTable}>
                        <thead>
                          <tr>
                            <th>{t("admin.reports.stage")}</th>
                            <th className={styles.colNum}>{t("admin.reports.remaining")}</th>
                            <th className={styles.colNum}>{t("admin.reports.drop_pct")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {c.drop_off_analysis.map((s) => (
                            <tr key={s.stage}>
                              <td>{s.stage}</td>
                              <td className={styles.colNum}>{s.trainers_remaining}</td>
                              <td className={styles.colNum}>{s.drop_pct}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div>
                    <h4 className={styles.sectionHeading} style={{ fontSize: "0.9rem" }}>
                      {t("admin.reports.cumulative_earnings")}
                    </h4>
                    <div className={styles.tableContainer}>
                      <table className={styles.dataTable}>
                        <thead>
                          <tr>
                            <th>{t("admin.reports.week")}</th>
                            <th className={styles.colNum}>{t("admin.reports.cumulative_inr")}</th>
                            <th className={styles.colNum}>{t("admin.reports.avg_tasks_day")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {c.earnings_curve.map((e, idx) => {
                            const prod = c.productivity_curve[idx];
                            return (
                              <tr key={e.week}>
                                <td>{e.week}</td>
                                <td className={styles.colNum}>
                                  {formatINR(locale, e.cumulative_earnings_inr)}
                                </td>
                                <td className={styles.colNum}>{prod?.avg_tasks_per_day ?? 0}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </section>
            ))}
          </>
        )}
      </RoleGate>
    </main>
  );
};

CohortAnalysis.title = "Cohort Analysis";
CohortAnalysis.path = "/admin/reports/cohorts";
CohortAnalysis.exact = true;

export default CohortAnalysis;
