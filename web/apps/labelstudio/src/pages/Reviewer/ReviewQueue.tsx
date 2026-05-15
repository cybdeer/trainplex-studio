/**
 * ReviewQueue — TrainPlex reviewer's pending-task queue.
 *
 * Phase 1 Step 6. Blind review: trainer name / email is intentionally NOT
 * surfaced — only an anonymous integer id. Reviewer clicks a row to open
 * the split-screen review form at /reviewer/review/:task_id.
 *
 * Columns
 * -------
 *   Submission (task id) | Time (age + deadline) | Status
 *
 * Filters
 * -------
 * Phase 1 ships only the status filter (open / done / expired / all). The
 * full filter set (language / type / age) is sketched in the FilterBar but
 * left as placeholder controls — the real filters land Step 8 when the
 * trainer-profile + task-language schema is real. Founder requested the
 * placeholder so the UI affordance is visible in the demo.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../providers/ApiProvider";
import type { Page } from "../types/Page";
import type {
  ReviewerAssignmentRow,
  ReviewerAssignmentStatus,
  ReviewerQueueResponse,
} from "./types";
import styles from "./Reviewer.module.css";

const QUEUE_QUERY_KEY_PREFIX = "reviewer-queue";

type StatusFilter = "open" | "done" | "expired" | "all";

const STATUS_OPTIONS: StatusFilter[] = ["open", "done", "expired", "all"];

const STATUS_LABEL_KEY: Record<StatusFilter, string> = {
  open: "reviewer.queue.filter_open",
  done: "reviewer.queue.filter_done",
  expired: "reviewer.queue.filter_expired",
  all: "reviewer.queue.filter_all",
};

const STATUS_BADGE_KEY: Record<ReviewerAssignmentStatus, string> = {
  pending: "reviewer.queue.status_pending",
  in_progress: "reviewer.queue.status_in_progress",
  done: "reviewer.queue.status_done",
  expired: "reviewer.queue.status_expired",
};

function formatDeadline(locale: string, isoTimestamp: string): string {
  try {
    const d = new Date(isoTimestamp);
    if (Number.isNaN(d.getTime())) return isoTimestamp;
    return d.toLocaleString(locale === "hi" ? "hi-IN" : "en-IN", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoTimestamp;
  }
}

export const ReviewQueue: Page = () => {
  const api = useAPI();
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const locale = i18n.language || "en";

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("open");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const params = useMemo(() => ({
    page,
    page_size: pageSize,
    status: statusFilter,
  }), [page, statusFilter]);

  const { data, isFetching, isError } = useQuery<ReviewerQueueResponse>({
    queryKey: [QUEUE_QUERY_KEY_PREFIX, params],
    queryFn: async () => {
      const res = await api.callApi("reviewerQueue", { params });
      return res as ReviewerQueueResponse;
    },
    keepPreviousData: true,
    enabled: user?.role === "reviewer",
  });

  const rows: ReviewerAssignmentRow[] = data?.results ?? [];

  return (
    <main className={`p-6 ${styles.reviewerRoot}`} data-testid="reviewer-queue">
      <RoleGate
        allow={["reviewer"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="reviewer-queue-forbidden">
            403 — reviewer only
          </div>
        }
      >
        <header className={styles.header}>
          <h1 className={styles.title}>{t("reviewer.queue.title")}</h1>
          {data ? (
            <span className={styles.totalCount} data-testid="reviewer-queue-total">
              {t("reviewer.queue.total_count", { count: data.total })}
            </span>
          ) : null}
        </header>

        {/* Filter bar — Phase 1 only status; language/type filters parked. */}
        <section className={styles.filterBar} data-testid="reviewer-queue-filter-bar">
          <label className={styles.filterLabel}>
            {t("reviewer.queue.filter_status")}
            <select
              className={styles.filterSelect}
              value={statusFilter}
              data-testid="reviewer-queue-filter-status"
              onChange={(e) => {
                setStatusFilter(e.target.value as StatusFilter);
                setPage(1);
              }}
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {t(STATUS_LABEL_KEY[opt])}
                </option>
              ))}
            </select>
          </label>
          {/* Placeholder filters — real wiring lands Step 8 when the
              task-profile schema exposes language + type. */}
          <span className={styles.filterPlaceholder} data-testid="reviewer-queue-filter-lang">
            {t("reviewer.queue.col_language")}: —
          </span>
        </section>

        {isError ? (
          <div className={styles.errorBox} data-testid="reviewer-queue-error">
            {t("reviewer.queue.fetch_failed")}
          </div>
        ) : isFetching && !data ? (
          <div className={styles.loadingBox} role="status" aria-live="polite">
            <Spinner />
            <span>{t("reviewer.queue.loading")}</span>
          </div>
        ) : (
          <div className={styles.tableWrap} data-testid="reviewer-queue-table">
            <table className={styles.queueTable}>
              <thead>
                <tr>
                  <th>{t("reviewer.queue.col_submission")}</th>
                  <th>{t("reviewer.queue.col_time")}</th>
                  <th>{t("reviewer.queue.col_language")}</th>
                  <th>{t("reviewer.queue.col_status")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={4} className={styles.emptyRow} data-testid="reviewer-queue-empty">
                      {t("reviewer.queue.no_tasks")}
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr key={row.id} data-testid={`reviewer-queue-row-${row.id}`}>
                      <td>
                        <Link
                          to={`/reviewer/review/${row.task_id}`}
                          data-testid={`reviewer-queue-link-${row.id}`}
                          className={styles.submissionLink}
                        >
                          {/* Blind label — trainer name / email never shown.
                              Anonymous "#<task_id>" identifies the work without
                              leaking who submitted it. */}
                          #{row.task_id}
                        </Link>
                      </td>
                      <td data-testid={`reviewer-queue-deadline-${row.id}`}>
                        {formatDeadline(locale, row.deadline_at)}
                      </td>
                      <td className={styles.metaLine}>—</td>
                      <td>
                        <span className={styles.statusChip} data-testid={`reviewer-queue-status-${row.id}`}>
                          {t(STATUS_BADGE_KEY[row.status])}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {data && data.total_pages > 1 ? (
          <nav className={styles.paginationBar} aria-label="pagination" data-testid="reviewer-queue-pagination">
            <button
              type="button"
              className={styles.pageButton}
              disabled={page <= 1}
              data-testid="reviewer-queue-page-prev"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              {t("reviewer.queue.prev_page")}
            </button>
            <span data-testid="reviewer-queue-page-label">
              {t("reviewer.queue.page_of", { page, total: data.total_pages })}
            </span>
            <button
              type="button"
              className={styles.pageButton}
              disabled={page >= data.total_pages}
              data-testid="reviewer-queue-page-next"
              onClick={() => setPage((p) => p + 1)}
            >
              {t("reviewer.queue.next_page")}
            </button>
          </nav>
        ) : null}
      </RoleGate>
    </main>
  );
};

ReviewQueue.title = "Review Queue";
ReviewQueue.path = "/reviewer/queue";
ReviewQueue.exact = true;

export default ReviewQueue;
