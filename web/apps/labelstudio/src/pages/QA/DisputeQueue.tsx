/**
 * DisputeQueue — TrainPlex QA-lead's open-dispute list.
 *
 * Phase 1 Step 6. Route: /qa/disputes. RoleGate `['qa_lead']` — backend
 * also enforces via `@require_role(['qa_lead'])`.
 *
 * Columns
 * -------
 *   Task | Severity (3-dot ConsensusBadge) | Escalated | Status | Open
 *
 * "Severity" is computed from the consensus status:
 *   - rejected → critical
 *   - dispute  → high
 *   - flagged  → medium (rare here — flagged tasks usually don't escalate)
 *
 * Clicking a row navigates to /qa/disputes/:id for the three-way comparison
 * + resolve form (DisputeResolution component).
 */

import { ConsensusBadge, RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../providers/ApiProvider";
import type { Page } from "../types/Page";
import type {
  ConsensusStatusWire,
  DisputeListResponse,
  DisputeRow,
} from "./types";
import styles from "./QA.module.css";

const LIST_QUERY_KEY_PREFIX = "qa-disputes";

type StatusFilter = "open" | "resolved" | "all";
const STATUS_FILTERS: StatusFilter[] = ["open", "resolved", "all"];

const STATUS_LABEL_KEY: Record<StatusFilter, string> = {
  open: "qa.disputes.filter_open",
  resolved: "qa.disputes.filter_resolved",
  all: "qa.disputes.filter_all",
};

const SEVERITY_KEY: Record<ConsensusStatusWire, string> = {
  rejected: "qa.disputes.severity_critical",
  dispute: "qa.disputes.severity_high",
  flagged: "qa.disputes.severity_medium",
  approved: "qa.disputes.severity_low",
};

function formatWhen(locale: string, iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(locale === "hi" ? "hi-IN" : "en-IN", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export const DisputeQueue: Page = () => {
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

  const { data, isFetching, isError } = useQuery<DisputeListResponse>({
    queryKey: [LIST_QUERY_KEY_PREFIX, params],
    queryFn: async () => {
      const res = await api.callApi("qaDisputes", { params });
      return res as DisputeListResponse;
    },
    keepPreviousData: true,
    enabled: user?.role === "qa_lead",
  });

  const rows: DisputeRow[] = data?.results ?? [];

  return (
    <main className={`p-6 ${styles.qaRoot}`} data-testid="qa-disputes">
      <RoleGate
        allow={["qa_lead"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="qa-disputes-forbidden">
            403 — QA lead only
          </div>
        }
      >
        <header className={styles.header}>
          <h1 className={styles.title}>{t("qa.disputes.title")}</h1>
          {data ? (
            <span className={styles.totalCount} data-testid="qa-disputes-total">
              {t("qa.disputes.total_count", { count: data.total })}
            </span>
          ) : null}
        </header>

        <section className={styles.filterBar} data-testid="qa-disputes-filter-bar">
          <label className={styles.filterLabel}>
            {t("qa.disputes.filter_status")}
            <select
              className={styles.filterSelect}
              value={statusFilter}
              data-testid="qa-disputes-filter-status"
              onChange={(e) => {
                setStatusFilter(e.target.value as StatusFilter);
                setPage(1);
              }}
            >
              {STATUS_FILTERS.map((opt) => (
                <option key={opt} value={opt}>
                  {t(STATUS_LABEL_KEY[opt])}
                </option>
              ))}
            </select>
          </label>
        </section>

        {isError ? (
          <div className={styles.errorBox} data-testid="qa-disputes-error">
            {t("qa.disputes.fetch_failed")}
          </div>
        ) : isFetching && !data ? (
          <div className={styles.loadingBox} role="status" aria-live="polite">
            <Spinner />
            <span>{t("qa.disputes.loading")}</span>
          </div>
        ) : (
          <div className={styles.tableWrap} data-testid="qa-disputes-table">
            <table className={styles.disputesTable}>
              <thead>
                <tr>
                  <th>{t("qa.disputes.col_task")}</th>
                  <th>{t("qa.disputes.col_severity")}</th>
                  <th>{t("qa.disputes.col_escalated")}</th>
                  <th>{t("qa.disputes.col_status")}</th>
                  <th>{t("qa.disputes.col_action")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={5} className={styles.emptyRow} data-testid="qa-disputes-empty">
                      {t("qa.disputes.no_disputes")}
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr key={row.id} data-testid={`qa-disputes-row-${row.id}`}>
                      <td>
                        <Link
                          to={`/qa/disputes/${row.id}`}
                          data-testid={`qa-disputes-link-${row.id}`}
                          className={styles.taskLink}
                        >
                          #{row.task_id}
                        </Link>
                      </td>
                      <td>
                        <ConsensusBadge
                          status={row.consensus_status}
                          agreedCount={row.agreed_count}
                          totalReviewers={row.total_reviewers}
                          testId={`qa-disputes-badge-${row.id}`}
                        />
                        <div className={styles.metaLine}>
                          {t(SEVERITY_KEY[row.consensus_status] ?? "qa.disputes.severity_medium")}
                        </div>
                      </td>
                      <td>{formatWhen(locale, row.escalated_at)}</td>
                      <td>
                        <span className={row.resolved_at ? styles.statusResolved : styles.statusOpen}>
                          {row.resolved_at
                            ? t("qa.disputes.status_resolved")
                            : t("qa.disputes.status_open")}
                        </span>
                      </td>
                      <td>
                        <Link
                          to={`/qa/disputes/${row.id}`}
                          data-testid={`qa-disputes-open-${row.id}`}
                          className={styles.openLink}
                        >
                          {t("qa.disputes.open_action")}
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {data && data.total_pages > 1 ? (
          <nav className={styles.paginationBar} aria-label="pagination">
            <button
              type="button"
              className={styles.pageButton}
              disabled={page <= 1}
              data-testid="qa-disputes-page-prev"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              {t("qa.disputes.prev_page")}
            </button>
            <span data-testid="qa-disputes-page-label">
              {t("qa.disputes.page_of", { page, total: data.total_pages })}
            </span>
            <button
              type="button"
              className={styles.pageButton}
              disabled={page >= data.total_pages}
              data-testid="qa-disputes-page-next"
              onClick={() => setPage((p) => p + 1)}
            >
              {t("qa.disputes.next_page")}
            </button>
          </nav>
        ) : null}
      </RoleGate>
    </main>
  );
};

DisputeQueue.title = "Disputed Tasks";
DisputeQueue.path = "/qa/disputes";
DisputeQueue.exact = true;

export default DisputeQueue;
