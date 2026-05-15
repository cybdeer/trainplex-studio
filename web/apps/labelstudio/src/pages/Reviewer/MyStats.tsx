/**
 * MyStats — TrainPlex reviewer's own quality metrics page.
 *
 * Phase 1 Step 6. Lightweight placeholder surface: accuracy + peer-agreement
 * rate so the reviewer can self-monitor before the QA lead pings them.
 * Numbers are MOCK in Phase 1; the real reviewer-stats service lands in
 * Step 8 (it aggregates over ConsensusResult.status + Review rows the
 * reviewer authored).
 *
 * Route: /reviewer/stats
 */

import { RoleGate } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import type { Page } from "../types/Page";
import styles from "./Reviewer.module.css";

export const MyStats: Page = () => {
  const { t } = useTranslation();
  const { user } = useAuth();

  // Phase 1 placeholder numbers. Real aggregation lands Step 8 — replace
  // this block with a useQuery against `/api/v1/reviewer/stats/me`.
  const mockStats = {
    accuracy_pct: null as number | null,
    agreement_rate_pct: null as number | null,
    total_reviews: 0,
  };

  return (
    <main className={`p-6 ${styles.reviewerRoot}`} data-testid="reviewer-stats">
      <RoleGate
        allow={["reviewer"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="reviewer-stats-forbidden">
            403 — reviewer only
          </div>
        }
      >
        <header className={styles.header}>
          <h1 className={styles.title}>{t("reviewer.stats.title")}</h1>
        </header>

        <section className={styles.statsCard} aria-label={t("reviewer.stats.title")}>
          <div className={styles.statsRow}>
            <div className={styles.statTile} data-testid="reviewer-mystats-accuracy">
              <span className={styles.statLabel}>{t("reviewer.stats.accuracy")}</span>
              <span className={styles.statValue}>
                {mockStats.accuracy_pct == null ? "—" : `${mockStats.accuracy_pct}%`}
              </span>
            </div>
            <div className={styles.statTile} data-testid="reviewer-mystats-agreement">
              <span className={styles.statLabel}>{t("reviewer.stats.agreement_rate")}</span>
              <span className={styles.statValue}>
                {mockStats.agreement_rate_pct == null ? "—" : `${mockStats.agreement_rate_pct}%`}
              </span>
            </div>
            <div className={styles.statTile} data-testid="reviewer-mystats-total">
              <span className={styles.statLabel}>{t("reviewer.stats.total_reviews")}</span>
              <span className={styles.statValue}>{mockStats.total_reviews}</span>
            </div>
          </div>
          <p className={styles.placeholderText}>
            {t("reviewer.stats.coming_soon")}
          </p>
        </section>
      </RoleGate>
    </main>
  );
};

MyStats.title = "My Stats";
MyStats.path = "/reviewer/stats";
MyStats.exact = true;

export default MyStats;
