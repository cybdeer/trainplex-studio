/**
 * AuditLogPage — TrainPlex admin viewer over `users.AuditLog`.
 *
 * Phase 1 Step 4.2-4. Wraps:
 *   - <AuditFilterBar>    — filter inputs
 *   - <AuditTable>        — paginated table with sticky header
 *   - <AuditRowDetailDrawer> — click-to-open detail panel
 *
 * Backend wiring
 * --------------
 *   GET /api/v1/admin/audit/log
 *   Query: action, actor_email, target_type, success, start_date, end_date,
 *          page, page_size  (all optional)
 *
 * The endpoint is admin-only via `@require_role(['admin'])`. We additionally
 * wrap this page in `<RoleGate allow={['admin']}>` so a misrouted
 * trainer/reviewer/QA-lead sees a 403 surface and never even issues the GET.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { AuditFilterBar } from "./AuditFilterBar";
import { AuditRowDetailDrawer } from "./AuditRowDetailDrawer";
import { AuditTable } from "./AuditTable";
import type { AuditFilters, AuditLogResponse, AuditRow } from "./types";
import styles from "./AuditLog.module.css";

const QUERY_KEY_PREFIX = "admin-audit-log";

const DEFAULT_FILTERS: AuditFilters = {
  action: "",
  actor_email: "",
  target_type: "",
  success: "",
  start_date: "",
  end_date: "",
  page: 1,
  page_size: 50,
};

/** Build the query params object the api wrapper sends. Strip empty strings. */
function buildQueryParams(filters: AuditFilters): Record<string, string | number> {
  const out: Record<string, string | number> = {};
  if (filters.action) out.action = filters.action;
  if (filters.actor_email) out.actor_email = filters.actor_email;
  if (filters.target_type) out.target_type = filters.target_type;
  if (filters.success) out.success = filters.success;
  if (filters.start_date) out.start_date = filters.start_date;
  if (filters.end_date) out.end_date = filters.end_date;
  out.page = filters.page ?? 1;
  out.page_size = filters.page_size ?? 50;
  return out;
}

export const AuditLogPage: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();

  const [filters, setFilters] = useState<AuditFilters>(DEFAULT_FILTERS);
  const [selectedRow, setSelectedRow] = useState<AuditRow | null>(null);

  const params = useMemo(() => buildQueryParams(filters), [filters]);

  const { data, isFetching, isError } = useQuery<AuditLogResponse>({
    queryKey: [QUERY_KEY_PREFIX, params],
    queryFn: async () => {
      const res = await api.callApi("adminAuditLog", { params });
      return res as AuditLogResponse;
    },
    // Keep prior data on screen while a filter change re-fetches — avoids the
    // table blanking-out flicker that confuses the founder mid-scroll.
    keepPreviousData: true,
    enabled: user?.role === "admin",
  });

  const totalPages = data?.total_pages ?? 0;
  const currentPage = filters.page ?? 1;

  const handlePrev = () => {
    if (currentPage > 1) setFilters({ ...filters, page: currentPage - 1 });
  };
  const handleNext = () => {
    if (currentPage < totalPages) setFilters({ ...filters, page: currentPage + 1 });
  };

  const body = (() => {
    if (isError) {
      return (
        <div className={styles.errorBox} data-testid="audit-error">
          {t("admin.audit.fetch_failed")}
        </div>
      );
    }
    return (
      <>
        <AuditFilterBar
          filters={filters}
          onFiltersChange={setFilters}
          onReset={() => setFilters(DEFAULT_FILTERS)}
        />

        {isFetching && !data ? (
          <div className={styles.loadingBox} role="status" aria-live="polite" data-testid="audit-loading">
            <Spinner />
            <span>{t("admin.audit.loading")}</span>
          </div>
        ) : (
          <AuditTable
            rows={data?.results ?? []}
            onRowClick={(r) => setSelectedRow(r)}
          />
        )}

        {data ? (
          <nav className={styles.paginationBar} aria-label="pagination" data-testid="audit-pagination">
            <span className={styles.paginationInfo} data-testid="audit-total">
              {t("admin.audit.total_count", { count: data.total })}
            </span>
            <div className={styles.paginationControls}>
              <button
                type="button"
                className={styles.pageButton}
                data-testid="audit-page-prev"
                onClick={handlePrev}
                disabled={currentPage <= 1}
              >
                {t("admin.audit.prev_page")}
              </button>
              <span className={styles.pageLabel} data-testid="audit-page-label">
                {t("admin.audit.page_of", {
                  page: currentPage,
                  total: Math.max(totalPages, 1),
                })}
              </span>
              <button
                type="button"
                className={styles.pageButton}
                data-testid="audit-page-next"
                onClick={handleNext}
                disabled={currentPage >= totalPages}
              >
                {t("admin.audit.next_page")}
              </button>
            </div>
          </nav>
        ) : null}

        <AuditRowDetailDrawer row={selectedRow} onClose={() => setSelectedRow(null)} />
      </>
    );
  })();

  return (
    <main className={`p-6 ${styles.auditRoot}`} data-testid="admin-audit-page">
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="audit-forbidden">
            403 — admin only
          </div>
        }
      >
        <header className={styles.auditHeader}>
          <h1 className={styles.auditTitle}>{t("admin.audit.title")}</h1>
          {data ? (
            <span className={styles.totalCount}>
              {t("admin.audit.total_count", { count: data.total })}
            </span>
          ) : null}
        </header>
        {body}
      </RoleGate>
    </main>
  );
};

AuditLogPage.title = "Audit Log";
AuditLogPage.path = "/admin/audit";
AuditLogPage.exact = true;

export default AuditLogPage;
