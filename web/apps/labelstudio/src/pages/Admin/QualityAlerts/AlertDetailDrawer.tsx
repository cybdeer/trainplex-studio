/**
 * AlertDetailDrawer — slide-in panel for one quality alert + resolution form.
 *
 * Phase 1 Step 4.2-8. Renders next to the table when the admin clicks a row.
 *
 * Content
 * -------
 *   - Severity / Trigger / Status / Trainer / Submission / When (read-only)
 *   - Pretty-printed `details` JSON so admin can see the detector inputs
 *   - Resolution form (resolution dropdown + notes textarea + Resolve button)
 *
 * Resolution semantics
 * --------------------
 *   * The form is only enabled when the alert is open OR when the admin
 *     wants to change a prior verdict — same endpoint accepts both flows.
 *   * On submit, the parent's `onResolve(id, body)` callback fires; the
 *     parent owns the mutation + cache invalidation.
 *
 * Accessibility
 * -------------
 *   * Backdrop click + Escape key close the drawer.
 *   * Focus moves into the close button on open.
 */

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "@humansignal/app-common";
import { SeverityBadge } from "./SeverityBadge";
import {
  ALERT_RESOLUTION_CHOICES,
} from "./types";
import type { AlertResolution, AlertRow } from "./types";
import styles from "./QualityAlerts.module.css";

export interface AlertDetailDrawerProps {
  row: AlertRow | null;
  onClose: () => void;
  onResolve: (alertId: number, body: { resolution: AlertResolution; notes: string }) => void;
  /** Set true while the resolve mutation is in flight; disables the form. */
  isResolving?: boolean;
}

const TRIGGER_LABEL_KEY: Record<string, string> = {
  reviewer_disagree: "admin.alerts.trigger_disagree",
  reviewer_conflict: "admin.alerts.trigger_disagree",
  time_anomaly: "admin.alerts.trigger_time",
  duplicate_pattern: "admin.alerts.trigger_duplicate",
  cert_failed: "admin.alerts.trigger_duplicate",
};

const STATUS_LABEL_KEY: Record<string, string> = {
  open: "admin.alerts.status_open",
  reviewed: "admin.alerts.status_reviewed",
  dismissed: "admin.alerts.status_dismissed",
  action_taken: "admin.alerts.status_action",
};

export function AlertDetailDrawer({
  row,
  onClose,
  onResolve,
  isResolving,
}: AlertDetailDrawerProps) {
  const { t, i18n } = useTranslation();
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const locale = i18n.language || "en";

  // Local form state. Re-initialised every time a new alert opens.
  const [resolution, setResolution] = useState<AlertResolution>("reviewed");
  const [notes, setNotes] = useState<string>("");

  useEffect(() => {
    if (!row) return;
    // Reset to defaults each open.
    setResolution("reviewed");
    setNotes(row.resolution_notes || "");

    const previouslyFocused = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
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
  }, [row, onClose]);

  if (!row) return null;

  const formattedWhen = (() => {
    try {
      const d = new Date(row.created_at);
      if (Number.isNaN(d.getTime())) return row.created_at;
      return d.toLocaleString(locale === "hi" ? "hi-IN" : "en-IN");
    } catch {
      return row.created_at;
    }
  })();

  const prettyDetails = (() => {
    try {
      return JSON.stringify(row.details ?? {}, null, 2);
    } catch {
      return String(row.details);
    }
  })();

  const onSubmit = () => {
    onResolve(row.id, { resolution, notes });
  };

  return (
    <div
      className={styles.drawerBackdrop}
      data-testid="alerts-drawer-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <aside
        className={styles.drawer}
        data-testid="alerts-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={t("admin.alerts.row_details")}
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.drawerHeader}>
          <h2 className={styles.drawerTitle}>{t("admin.alerts.row_details")}</h2>
          <button
            ref={closeRef}
            type="button"
            className={styles.drawerCloseBtn}
            data-testid="alerts-drawer-close"
            onClick={onClose}
            aria-label={t("common.cancel")}
          >
            ×
          </button>
        </header>

        <div className={styles.drawerBody}>
          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.alerts.col_severity")}</span>
            <SeverityBadge severity={row.severity} testIdSuffix="drawer" />
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.alerts.col_trigger")}</span>
            <span className={styles.drawerValue}>
              {t(TRIGGER_LABEL_KEY[row.trigger_type] ?? "admin.alerts.trigger_disagree")}
            </span>
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.alerts.col_status")}</span>
            <span className={styles.drawerValue} data-testid="alerts-drawer-status">
              {t(STATUS_LABEL_KEY[row.status] ?? "admin.alerts.status_open")}
            </span>
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.alerts.col_trainer")}</span>
            <span className={styles.drawerValue}>
              {row.trainer
                ? row.trainer.email || `#${row.trainer.id ?? "?"}`
                : "—"}
              {row.trainer?.role ? ` (${row.trainer.role})` : ""}
            </span>
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.alerts.col_submission")}</span>
            <span className={styles.drawerValue}>
              {row.submission_id != null ? `#${row.submission_id}` : "—"}
            </span>
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.alerts.col_when")}</span>
            <span className={styles.drawerValue}>{formattedWhen}</span>
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.alerts.row_details")}</span>
            <pre className={styles.drawerDetails} data-testid="alerts-drawer-details">
              {prettyDetails}
            </pre>
          </div>

          {row.reviewed_by ? (
            <div className={styles.drawerSection}>
              <span className={styles.drawerLabel}>{t("admin.alerts.resolved_by")}</span>
              <span className={styles.drawerValue}>
                {row.reviewed_by.email || `#${row.reviewed_by.id ?? "?"}`}
                {row.reviewed_at ? ` · ${row.reviewed_at}` : ""}
              </span>
            </div>
          ) : null}

          {/* ─── Resolution form ─── */}
          <form
            className={styles.resolveForm}
            data-testid="alerts-resolve-form"
            onSubmit={(e) => {
              e.preventDefault();
              onSubmit();
            }}
          >
            <div className={styles.drawerSection}>
              <label className={styles.drawerLabel} htmlFor="alerts-resolution-select">
                {t("admin.alerts.resolve_button")}
              </label>
              <select
                id="alerts-resolution-select"
                data-testid="alerts-resolution-select"
                className={styles.filterSelect}
                value={resolution}
                onChange={(e) => setResolution(e.target.value as AlertResolution)}
                disabled={isResolving}
              >
                {ALERT_RESOLUTION_CHOICES.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {t(opt.labelKey)}
                  </option>
                ))}
              </select>
            </div>

            <div className={styles.drawerSection}>
              <label className={styles.drawerLabel} htmlFor="alerts-resolution-notes">
                {t("admin.alerts.notes_label")}
              </label>
              <textarea
                id="alerts-resolution-notes"
                data-testid="alerts-resolution-notes"
                className={styles.notesTextarea}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={isResolving}
                rows={4}
                maxLength={4096}
              />
            </div>

            <button
              type="submit"
              className={styles.ctaPrimary}
              data-testid="alerts-resolve-submit"
              disabled={isResolving}
            >
              {t("admin.alerts.resolve_button")}
            </button>
          </form>
        </div>
      </aside>
    </div>
  );
}

export default AlertDetailDrawer;
