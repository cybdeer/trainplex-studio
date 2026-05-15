/**
 * SubmissionsPreviewDrawer — slide-in drawer for the most-recent 10
 * submissions sample.
 *
 * Phase 1 Step 4.2-9. Founder spot-check tool: admin opens this from the
 * Dashboard Widget (or any other admin page), sees recent submissions
 * (image / answer / 3 reviewer scores), and can scan for fraud / quality
 * issues at random. The drawer is purely read-only — it's the cheapest
 * possible auditing surface.
 *
 * Behaviour
 * ---------
 *   - Mounted everywhere via the dashboard's "Recent Submissions" button,
 *     but the drawer itself only renders when `open === true`. Parent
 *     toggles via `onClose()` / re-mount with `open=true`.
 *   - Wrapped in RoleGate('admin') so a misrouted non-admin sees the
 *     forbidden box (backend also 403's the API).
 *   - Backdrop click + Escape key close the drawer (a11y).
 *   - Focus moves to the close button on open; previously-focused element
 *     is restored on close.
 *   - Status filter is in the header; project_id / trainer_id are optional
 *     props for the parent to pass when scoping the drawer to a context.
 *
 * Backend
 * -------
 *   GET /api/v1/admin/submissions/preview (admin-only)
 *   - limit (default 10, cap 50) / project_id / trainer_id / status
 *   - Mock data in Phase 1; real DB wiring lands in Phase 2 / Step 8.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import { SubmissionCard } from "./SubmissionCard";
import {
  SUBMISSION_STATUS_CHOICES,
} from "./types";
import type {
  SubmissionStatus,
  SubmissionsPreviewQuery,
  SubmissionsPreviewResponse,
} from "./types";
import styles from "./SubmissionsPreview.module.css";

const QUERY_KEY_PREFIX = "admin-submissions-preview";

const DEFAULT_LIMIT = 10;

export interface SubmissionsPreviewDrawerProps {
  /** Drawer visible? Parent owns the toggle. */
  open: boolean;
  /** Called when the drawer requests close (backdrop / Escape / X button). */
  onClose: () => void;
  /** Optional scope: only show submissions from this project. */
  projectId?: number;
  /** Optional scope: only show this trainer's submissions. */
  trainerId?: number;
  /** Override default limit (10). Backend caps at 50. */
  limit?: number;
}

/** Strip empty filter slots so the query string is clean. */
function buildQueryParams(
  query: SubmissionsPreviewQuery,
): Record<string, string | number> {
  const out: Record<string, string | number> = {};
  if (query.limit) out.limit = query.limit;
  if (query.project_id) out.project_id = query.project_id;
  if (query.trainer_id) out.trainer_id = query.trainer_id;
  if (query.status) out.status = query.status;
  return out;
}

export function SubmissionsPreviewDrawer({
  open,
  onClose,
  projectId,
  trainerId,
  limit = DEFAULT_LIMIT,
}: SubmissionsPreviewDrawerProps) {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);

  const [statusFilter, setStatusFilter] = useState<SubmissionStatus | "">("");

  const query: SubmissionsPreviewQuery = useMemo(
    () => ({
      limit,
      project_id: projectId ?? "",
      trainer_id: trainerId ?? "",
      status: statusFilter,
    }),
    [limit, projectId, trainerId, statusFilter],
  );

  const params = useMemo(() => buildQueryParams(query), [query]);

  const previewQuery = useQuery<SubmissionsPreviewResponse>({
    queryKey: [QUERY_KEY_PREFIX, params],
    queryFn: async () => {
      const res = await api.callApi("adminSubmissionsPreview", { params });
      return res as SubmissionsPreviewResponse;
    },
    // The drawer is on-demand; the data is "recent N" — let it stay fresh
    // for short tab switches but always refetch on open.
    staleTime: 15_000,
    // Only fire when the drawer is open AND the user is an admin (backend
    // would 403 a non-admin anyway, but we don't even want the request).
    enabled: open && user?.role === "admin",
  });

  // a11y: focus management + Escape-to-close.
  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    closeBtnRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previouslyFocused?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  const body = (() => {
    if (previewQuery.isError) {
      return (
        <div className={styles.errorBox} data-testid="submissions-preview-error">
          {t("admin.submissions.fetch_failed")}
        </div>
      );
    }

    if (previewQuery.isFetching && !previewQuery.data) {
      return (
        <div
          className={styles.stateBox}
          role="status"
          aria-live="polite"
          data-testid="submissions-preview-loading"
        >
          <Spinner />
          <span>{t("admin.submissions.loading")}</span>
        </div>
      );
    }

    const rows = previewQuery.data?.submissions ?? [];
    if (rows.length === 0) {
      return (
        <div className={styles.stateBox} data-testid="submissions-preview-empty">
          {t("admin.submissions.no_recent")}
        </div>
      );
    }

    return (
      <div data-testid="submissions-preview-list">
        {rows.map((row) => (
          <SubmissionCard key={row.id} submission={row} />
        ))}
      </div>
    );
  })();

  return (
    <div
      className={styles.drawerBackdrop}
      data-testid="submissions-preview-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <aside
        className={styles.drawer}
        data-testid="submissions-preview-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={t("admin.submissions.title")}
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.drawerHeader}>
          <h2 className={styles.drawerTitle}>{t("admin.submissions.title")}</h2>
          <button
            ref={closeBtnRef}
            type="button"
            className={styles.drawerCloseBtn}
            data-testid="submissions-preview-close"
            onClick={onClose}
            aria-label={t("common.cancel")}
          >
            ×
          </button>
        </header>

        <RoleGate
          allow={["admin"]}
          userRole={user?.role}
          fallback={
            <div
              className={styles.forbiddenBox}
              data-testid="submissions-preview-forbidden"
            >
              403 — admin only
            </div>
          }
        >
          {/* Filter toolbar */}
          <div className={styles.drawerToolbar} data-testid="submissions-preview-toolbar">
            <div className={styles.toolbarField}>
              <label
                className={styles.toolbarLabel}
                htmlFor="submissions-preview-status"
              >
                {t("admin.submissions.filter_status")}
              </label>
              <select
                id="submissions-preview-status"
                data-testid="submissions-preview-status-filter"
                className={styles.toolbarSelect}
                value={statusFilter}
                onChange={(e) =>
                  setStatusFilter(e.target.value as SubmissionStatus | "")
                }
              >
                {SUBMISSION_STATUS_CHOICES.map((opt) => (
                  <option key={opt.value || "all"} value={opt.value}>
                    {t(opt.labelKey)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className={styles.drawerBody}>{body}</div>
        </RoleGate>
      </aside>
    </div>
  );
}

export default SubmissionsPreviewDrawer;
