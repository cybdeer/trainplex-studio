/**
 * Leaderboard — TrainPlex Phase 1 Step 7.
 *
 * Trainer leaderboard at `/admin/reports/leaderboard`. Pills for daily /
 * weekly / monthly; dropdowns for state / tier / language / project_type;
 * CSV export anchor.
 *
 * Plus two Hall of Fame tables (lifetime + this month) below the main grid.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import type { HallOfFameRow, LeaderboardPayload, LeaderboardPeriod } from "./types";
import styles from "./Reports.module.css";

const PERIODS: LeaderboardPeriod[] = ["daily", "weekly", "monthly"];
const TIER_OPTIONS = ["", "bronze", "silver", "gold"];
const STATE_OPTIONS = [
  "", "RJ", "UP", "MH", "KA", "GJ", "PB", "TN", "MP", "TG", "WB",
  "BR", "KL", "JH", "OR", "AP", "DL", "AS", "HR",
];
const LANGUAGE_OPTIONS = ["", "hi", "bn", "mr", "ta", "te", "gu", "kn", "pa", "bho", "or"];
const PROJECT_TYPE_OPTIONS = ["", "ocr", "voice", "image", "sentiment", "moderation"];

const formatINR = (locale: string, v: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(v);

const formatInt = (locale: string, v: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(v);

const rankBadgeClass = (rank: number) =>
  `${styles.rankBadge} ${rank <= 3 ? styles.rankTop3 : ""}`;

const tierClass = (tier: string) => {
  if (tier === "gold") return `${styles.tagBadge} ${styles.tierGold}`;
  if (tier === "silver") return `${styles.tagBadge} ${styles.tierSilver}`;
  return `${styles.tagBadge} ${styles.tierBronze}`;
};

function HallOfFameTable({
  title,
  rows,
  earningsKey,
  tasksKey,
  testId,
}: {
  title: string;
  rows: HallOfFameRow[];
  earningsKey: "lifetime_earnings_inr" | "earnings_this_month_inr";
  tasksKey: "lifetime_tasks" | "tasks_this_month";
  testId: string;
}) {
  const { i18n, t } = useTranslation();
  const locale = i18n.language || "en";
  return (
    <div className={styles.sectionBlock}>
      <h3 className={styles.sectionHeading}>{title}</h3>
      <div className={styles.tableContainer}>
        <table className={styles.dataTable} data-testid={testId}>
          <thead>
            <tr>
              <th>#</th>
              <th>{t("admin.reports.trainer")}</th>
              <th>{t("admin.reports.state")}</th>
              <th className={styles.colNum}>{t("admin.reports.tasks_done")}</th>
              <th className={styles.colNum}>{t("admin.reports.earnings_inr")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.trainer_id}>
                <td>
                  <span className={rankBadgeClass(r.rank)}>{r.rank}</span>
                </td>
                <td>{r.name}</td>
                <td>{r.state}</td>
                <td className={styles.colNum}>
                  {formatInt(locale, (r[tasksKey] ?? 0) as number)}
                </td>
                <td className={styles.colNum}>
                  {formatINR(locale, (r[earningsKey] ?? 0) as number)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export const Leaderboard: Page = () => {
  const api = useAPI();
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const locale = i18n.language || "en";

  const [period, setPeriod] = useState<LeaderboardPeriod>("weekly");
  const [state, setState] = useState<string>("");
  const [tier, setTier] = useState<string>("");
  const [language, setLanguage] = useState<string>("");
  const [projectType, setProjectType] = useState<string>("");

  const queryParams = useMemo(
    () => ({ period, state, tier, language, project_type: projectType }),
    [period, state, tier, language, projectType],
  );

  const { data, isFetching, isError } = useQuery<LeaderboardPayload>({
    queryKey: ["admin-reports-leaderboard", queryParams],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("period", period);
      if (state) params.set("state", state);
      if (tier) params.set("tier", tier);
      if (language) params.set("language", language);
      if (projectType) params.set("project_type", projectType);
      const res = await api.callApi("adminReportsLeaderboard", {
        params: Object.fromEntries(params),
      });
      return res as LeaderboardPayload;
    },
    staleTime: 5 * 60 * 1000,
    enabled: user?.role === "admin",
  });

  // CSV export anchor — manual URL so the session cookie comes along.
  const csvHref = useMemo(() => {
    const params = new URLSearchParams();
    params.set("period", period);
    if (state) params.set("state", state);
    if (tier) params.set("tier", tier);
    if (language) params.set("language", language);
    if (projectType) params.set("project_type", projectType);
    return `/api/v1/admin/reports/leaderboard.csv?${params.toString()}`;
  }, [period, state, tier, language, projectType]);

  return (
    <main className={styles.reportsRoot} data-testid="leaderboard-page">
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="leaderboard-forbidden">
            403 — admin only
          </div>
        }
      >
        <header className={styles.reportsHeader}>
          <h2 className={styles.reportsTitle}>{t("admin.reports.leaderboard")}</h2>
          <div className={styles.actionBar}>
            <div className={styles.periodPills} role="group" aria-label={t("admin.reports.period")}>
              {PERIODS.map((p) => (
                <button
                  key={p}
                  type="button"
                  data-testid={`period-${p}`}
                  className={`${styles.periodPill} ${period === p ? styles.periodPillActive : ""}`}
                  onClick={() => setPeriod(p)}
                  aria-pressed={period === p}
                >
                  {t(`admin.reports.period_${p}`)}
                </button>
              ))}
            </div>
            <a
              className={styles.exportBtn}
              href={csvHref}
              data-testid="leaderboard-export-csv"
              target="_blank"
              rel="noreferrer"
            >
              {t("admin.reports.export_csv")}
            </a>
          </div>
        </header>

        <section className={styles.filterBar} aria-label={t("admin.reports.filters")}>
          <select
            className={styles.dropdown}
            value={state}
            onChange={(e) => setState(e.target.value)}
            data-testid="filter-state"
            aria-label={t("admin.reports.state")}
          >
            <option value="">{t("admin.reports.state_all")}</option>
            {STATE_OPTIONS.filter(Boolean).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select
            className={styles.dropdown}
            value={tier}
            onChange={(e) => setTier(e.target.value)}
            data-testid="filter-tier"
            aria-label={t("admin.reports.tier")}
          >
            <option value="">{t("admin.reports.tier_all")}</option>
            {TIER_OPTIONS.filter(Boolean).map((s) => (
              <option key={s} value={s}>
                {t(`admin.reports.tier_${s}`)}
              </option>
            ))}
          </select>
          <select
            className={styles.dropdown}
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            data-testid="filter-language"
            aria-label={t("admin.reports.language")}
          >
            <option value="">{t("admin.reports.language_all")}</option>
            {LANGUAGE_OPTIONS.filter(Boolean).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select
            className={styles.dropdown}
            value={projectType}
            onChange={(e) => setProjectType(e.target.value)}
            data-testid="filter-project-type"
            aria-label={t("admin.reports.project_type")}
          >
            <option value="">{t("admin.reports.project_type_all")}</option>
            {PROJECT_TYPE_OPTIONS.filter(Boolean).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </section>

        {isFetching && !data ? (
          <div className={styles.skeletonRoot} data-testid="leaderboard-skeleton">
            <Spinner />
            <span className="sr-only">{t("admin.reports.loading_snapshot")}</span>
            <div className={styles.skeletonBar} style={{ height: 320 }} />
          </div>
        ) : isError || !data ? (
          <div className={styles.errorBox} data-testid="leaderboard-error">
            {t("admin.reports.snapshot_failed")}
          </div>
        ) : (
          <>
            <section className={styles.sectionBlock}>
              <h3 className={styles.sectionHeading}>
                {t("admin.reports.leaderboard_total", { count: data.total })}
              </h3>
              <div className={styles.tableContainer}>
                <table className={styles.dataTable} data-testid="leaderboard-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>{t("admin.reports.trainer")}</th>
                      <th>{t("admin.reports.state")}</th>
                      <th>{t("admin.reports.tier")}</th>
                      <th>{t("admin.reports.language")}</th>
                      <th className={styles.colNum}>{t("admin.reports.tasks_done")}</th>
                      <th className={styles.colNum}>{t("admin.reports.earnings_inr")}</th>
                      <th className={styles.colNum}>{t("admin.reports.quality_score")}</th>
                      <th className={styles.colNum}>{t("admin.reports.consistency")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((r) => (
                      <tr key={r.trainer_id}>
                        <td>
                          <span className={rankBadgeClass(r.rank)}>{r.rank}</span>
                        </td>
                        <td>{r.name}</td>
                        <td>{r.state}</td>
                        <td>
                          <span className={tierClass(r.tier)}>{t(`admin.reports.tier_${r.tier}`)}</span>
                        </td>
                        <td>{r.language}</td>
                        <td className={styles.colNum}>{formatInt(locale, r.tasks_done)}</td>
                        <td className={styles.colNum}>{formatINR(locale, r.earnings_inr)}</td>
                        <td className={styles.colNum}>{r.quality_score_pct}%</td>
                        <td className={styles.colNum}>{r.consistency_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className={styles.gridTwo}>
              <HallOfFameTable
                title={t("admin.reports.hall_of_fame_lifetime")}
                rows={data.hall_of_fame_lifetime}
                earningsKey="lifetime_earnings_inr"
                tasksKey="lifetime_tasks"
                testId="hof-lifetime-table"
              />
              <HallOfFameTable
                title={t("admin.reports.hall_of_fame_month")}
                rows={data.hall_of_fame_month}
                earningsKey="earnings_this_month_inr"
                tasksKey="tasks_this_month"
                testId="hof-month-table"
              />
            </section>
          </>
        )}
      </RoleGate>
    </main>
  );
};

Leaderboard.title = "Trainer Leaderboard";
Leaderboard.path = "/admin/reports/leaderboard";
Leaderboard.exact = true;

export default Leaderboard;
