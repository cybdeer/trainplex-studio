/**
 * AuditRowDetailDrawer — slide-in panel showing full row metadata.
 *
 * Phase 1 Step 4.2-4. Renders next to the table when the user clicks a row.
 *
 * Content:
 *   - When / Who / Action / Target / IP / UA / Status (same as table, untrimmed)
 *   - Pretty-printed `metadata` JSONB so the founder can read the full event
 *     payload — useful for permission_change events where the metadata holds
 *     `{old_role, new_role, target_email}`.
 *
 * Accessibility:
 *   - Backdrop click + Escape key close the drawer.
 *   - Focus is moved into the close button on open.
 */

import { useEffect, useRef } from "react";
import { useTranslation } from "@humansignal/app-common";
import type { AuditRow } from "./types";
import styles from "./AuditLog.module.css";

export interface AuditRowDetailDrawerProps {
  row: AuditRow | null;
  onClose: () => void;
}

export function AuditRowDetailDrawer({ row, onClose }: AuditRowDetailDrawerProps) {
  const { t, i18n } = useTranslation();
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const locale = i18n.language || "en";

  // Move focus into the drawer on open and trap Escape.
  useEffect(() => {
    if (!row) return;
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
      // Restore focus to the previously focused element (usually the row).
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

  const prettyMetadata = (() => {
    try {
      return JSON.stringify(row.metadata ?? {}, null, 2);
    } catch {
      return String(row.metadata);
    }
  })();

  return (
    <div
      className={styles.drawerBackdrop}
      data-testid="audit-drawer-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <aside
        className={styles.drawer}
        data-testid="audit-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={t("admin.audit.row_metadata")}
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.drawerHeader}>
          <h2 className={styles.drawerTitle}>{t("admin.audit.row_metadata")}</h2>
          <button
            ref={closeRef}
            type="button"
            className={styles.drawerCloseBtn}
            data-testid="audit-drawer-close"
            onClick={onClose}
            aria-label={t("common.cancel")}
          >
            ×
          </button>
        </header>

        <div className={styles.drawerBody}>
          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.audit.col_when")}</span>
            <span className={styles.drawerValue}>{formattedWhen}</span>
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.audit.col_actor")}</span>
            <span className={styles.drawerValue}>
              {row.actor ? (
                <>
                  {row.actor.email || "—"}
                  {row.actor.role ? ` (${row.actor.role})` : ""}
                </>
              ) : (
                "—"
              )}
            </span>
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.audit.col_action")}</span>
            <span className={styles.drawerValue}>{row.action}</span>
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.audit.col_target")}</span>
            <span className={styles.drawerValue}>
              {row.target_type || "—"}
              {row.target_id ? ` #${row.target_id}` : ""}
            </span>
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.audit.col_ip")}</span>
            <span className={styles.drawerValue}>{row.ip_address || "—"}</span>
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>User-Agent</span>
            <span className={styles.drawerValue}>{row.user_agent || "—"}</span>
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.audit.col_success")}</span>
            <span className={styles.drawerValue}>
              {row.success ? t("admin.audit.success_yes") : t("admin.audit.success_no")}
            </span>
          </div>

          <div className={styles.drawerSection}>
            <span className={styles.drawerLabel}>{t("admin.audit.row_metadata")}</span>
            <pre className={styles.drawerMetadata} data-testid="audit-drawer-metadata">
              {prettyMetadata}
            </pre>
          </div>
        </div>
      </aside>
    </div>
  );
}

export default AuditRowDetailDrawer;
