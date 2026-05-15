/**
 * ReviewerDashboard — TrainPlex reviewer landing page.
 *
 * Phase 1 Step 6. Founder copy: "Aaj review karne hain" — the badge tells
 * the reviewer how many tasks are sitting in their queue + a quick CTA to
 * dive in.
 *
 * Layout
 * ------
 *   ┌───────────────────────────────────────────┐
 *   │ Reviewer Dashboard                        │  ← Indigo header
 *   ├───────────────────────────────────────────┤
 *   │ Aaj review karne hain: 7 reviews pending  │  ← Pending badge
 *   │  [ Open queue ]                            │  ← CTA → /reviewer/queue
 *   ├───────────────────────────────────────────┤
 *   │ My stats                                  │
 *   │  Accuracy: 94%   Peer agreement: 88%       │
 *   └───────────────────────────────────────────┘
 *
 * Mock-vs-real note
 * -----------------
 * The pending-count comes from the real `/api/v1/reviewer/queue` endpoint
 * (total field of the paginated response). Accuracy + peer-agreement are
 * placeholder fields populated client-side until the reviewer-stats service
 * lands in Step 8.
 */

import { Button, RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../providers/ApiProvider";
import type { Page } from "../types/Page";
import type { ReviewerQueueResponse } from "./types";
import styles from "./Reviewer.module.css";

const QUEUE_HEAD_QUERY_KEY = ["reviewer-queue-head"];

export const ReviewerDashboard: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();

  // Same endpoint the queue page uses; we only need `total` here so we
  // request page_size=1 to keep the payload small.
  const { data, isFetching, isError } = useQuery<ReviewerQueueResponse>({
    queryKey: QUEUE_HEAD_QUERY_KEY,
    queryFn: async () => {
      const res = await api.callApi("reviewerQueue", {
        params: { page: 1, page_size: 1, status: "open" },
      });
      return res as ReviewerQueueResponse;
    },
    staleTime: 30_000,
    enabled: user?.role === "reviewer",
  });

  return (
    <main className={`p-6 ${styles.reviewerRoot}`} data-testid="reviewer-dashboard">
      <RoleGate
        allow={["reviewer"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="reviewer-forbidden">
            403 — reviewer only
          </div>
        }
      >
        <header className={styles.header}>
          <h1 className={styles.title}>{t("reviewer.dashboard.title")}</h1>
        </header>

        {/* Pending-count badge */}
        <section className={styles.pendingCard} data-testid="reviewer-pending-card">
          {isFetching && !data ? (
            <div className={styles.loading}>
              <Spinner />
            </div>
          ) : isError ? (
            <div className={styles.errorBox} data-testid="reviewer-pending-error">
              {t("reviewer.dashboard.fetch_failed")}
            </div>
          ) : (
            <>
              <div className={styles.pendingHeadline} data-testid="reviewer-pending-count">
                {t("reviewer.dashboard.pending_count", { count: data?.total ?? 0 })}
              </div>
              <Link to="/reviewer/queue" data-testid="reviewer-open-queue">
                <Button look="filled" size="medium" className={styles.ctaPrimary}>
                  {t("reviewer.dashboard.open_queue")}
                </Button>
              </Link>
            </>
          )}
        </section>

        {/* Stats placeholder — populated client-side in Phase 1 (mock); real
            agreement-rate / accuracy aggregation lands Step 8. */}
        <section className={styles.statsCard} aria-label={t("reviewer.stats.title")}>
          <h2 className={styles.sectionHeading}>{t("reviewer.stats.title")}</h2>
          <div className={styles.statsRow}>
            <div className={styles.statTile} data-testid="reviewer-stat-accuracy">
              <span className={styles.statLabel}>{t("reviewer.stats.accuracy")}</span>
              <span className={styles.statValue}>—</span>
            </div>
            <div className={styles.statTile} data-testid="reviewer-stat-agreement">
              <span className={styles.statLabel}>{t("reviewer.stats.agreement_rate")}</span>
              <span className={styles.statValue}>—</span>
            </div>
            <Link to="/reviewer/stats" data-testid="reviewer-open-stats" className={styles.statsLink}>
              {t("reviewer.stats.view_details")}
            </Link>
          </div>
        </section>
      </RoleGate>
    </main>
  );
};

ReviewerDashboard.title = "Reviewer Dashboard";
ReviewerDashboard.path = "/reviewer/dashboard";
ReviewerDashboard.exact = true;

export default ReviewerDashboard;
