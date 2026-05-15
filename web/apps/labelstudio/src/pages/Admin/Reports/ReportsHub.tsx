/**
 * ReportsHub — TrainPlex Phase 1 Step 7.
 *
 * Single index page at `/admin/reports` that links to the 4 reporting
 * surfaces. RoleGate-restricted to admin; backend mirrors via @require_role.
 *
 * Layout
 * ------
 *   ┌───────────────────────────────────────────────┐
 *   │ Reports                                        │  ← Indigo header
 *   ├───────────────────────┬───────────────────────┤
 *   │ Founder Weekly        │ Trainer Leaderboard   │
 *   │ KPIs, trends, ROI …   │ Daily / weekly / mon… │
 *   ├───────────────────────┼───────────────────────┤
 *   │ Cohort Analysis       │ Project ROI           │
 *   │ Retention curves      │ Per-project cost+rev. │
 *   └───────────────────────────────────────────────┘
 */

import { RoleGate } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { Link } from "react-router-dom";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import type { Page } from "../../types/Page";
import styles from "./Reports.module.css";

const HUB_LINKS: Array<{
  to: string;
  titleKey: string;
  subtitleKey: string;
  testId: string;
}> = [
  {
    to: "/admin/reports/founder",
    titleKey: "admin.reports.founder_weekly",
    subtitleKey: "admin.reports.founder_weekly_subtitle",
    testId: "hub-link-founder",
  },
  {
    to: "/admin/reports/leaderboard",
    titleKey: "admin.reports.leaderboard",
    subtitleKey: "admin.reports.leaderboard_subtitle",
    testId: "hub-link-leaderboard",
  },
  {
    to: "/admin/reports/cohorts",
    titleKey: "admin.reports.cohorts",
    subtitleKey: "admin.reports.cohorts_subtitle",
    testId: "hub-link-cohorts",
  },
  {
    to: "/admin/reports/project-roi",
    titleKey: "admin.reports.project_roi",
    subtitleKey: "admin.reports.project_roi_subtitle",
    testId: "hub-link-project-roi",
  },
];

export const ReportsHub: Page = () => {
  const { t } = useTranslation();
  const { user } = useAuth();

  return (
    <main className={styles.reportsRoot} data-testid="admin-reports-hub">
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="reports-forbidden">
            403 — admin only
          </div>
        }
      >
        <header className={styles.reportsHeader}>
          <h2 className={styles.reportsTitle}>{t("admin.reports.title")}</h2>
        </header>
        <div className={styles.hubGrid}>
          {HUB_LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={styles.hubCard}
              data-testid={link.testId}
            >
              <h3 className={styles.hubCardTitle}>{t(link.titleKey)}</h3>
              <p className={styles.hubCardSubtitle}>{t(link.subtitleKey)}</p>
            </Link>
          ))}
        </div>
      </RoleGate>
    </main>
  );
};

ReportsHub.title = "Reports";
ReportsHub.path = "/admin/reports";
ReportsHub.exact = true;

export default ReportsHub;
