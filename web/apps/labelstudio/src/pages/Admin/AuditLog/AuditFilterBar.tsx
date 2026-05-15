/**
 * AuditFilterBar — controls for narrowing the audit log query.
 *
 * Phase 1 Step 4.2-4. Renders five inputs above the table:
 *   - Action (dropdown, populated from AUDIT_ACTION_CHOICES)
 *   - Actor email (substring text search)
 *   - Target type (dropdown)
 *   - Success / failed (radio-style select)
 *   - Date range (start_date + end_date, native <input type=date>)
 *
 * The bar is fully controlled — it holds no internal state; the parent
 * `<AuditLogPage>` owns the `AuditFilters` object and re-fetches when it
 * changes. "Apply" is implicit: every input change flushes upward.
 *
 * Resetting clears the filters back to `{}` so the page returns the full
 * unfiltered listing on the next fetch.
 */

import { useTranslation } from "@humansignal/app-common";
import { AUDIT_ACTION_CHOICES, AUDIT_TARGET_TYPE_CHOICES } from "./types";
import type { AuditFilters } from "./types";
import styles from "./AuditLog.module.css";

export interface AuditFilterBarProps {
  filters: AuditFilters;
  onFiltersChange: (next: AuditFilters) => void;
  onReset: () => void;
}

export function AuditFilterBar({ filters, onFiltersChange, onReset }: AuditFilterBarProps) {
  const { t } = useTranslation();

  /** Merge a single field into the filters and bubble up; reset page=1. */
  const patch = (delta: Partial<AuditFilters>) => {
    onFiltersChange({ ...filters, ...delta, page: 1 });
  };

  return (
    <form
      className={styles.filterBar}
      data-testid="audit-filter-bar"
      onSubmit={(e) => e.preventDefault()}
      role="search"
      aria-label={t("admin.audit.title")}
    >
      <div className={styles.filterField}>
        <label className={styles.filterLabel} htmlFor="audit-filter-action">
          {t("admin.audit.filter_action")}
        </label>
        <select
          id="audit-filter-action"
          data-testid="audit-filter-action"
          className={styles.filterSelect}
          value={filters.action ?? ""}
          onChange={(e) => patch({ action: e.target.value })}
        >
          {AUDIT_ACTION_CHOICES.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {t(opt.labelKey)}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.filterField}>
        <label className={styles.filterLabel} htmlFor="audit-filter-actor">
          {t("admin.audit.filter_actor")}
        </label>
        <input
          id="audit-filter-actor"
          data-testid="audit-filter-actor"
          className={styles.filterInput}
          type="text"
          placeholder="search@email.com"
          value={filters.actor_email ?? ""}
          onChange={(e) => patch({ actor_email: e.target.value })}
        />
      </div>

      <div className={styles.filterField}>
        <label className={styles.filterLabel} htmlFor="audit-filter-target">
          {t("admin.audit.filter_target")}
        </label>
        <select
          id="audit-filter-target"
          data-testid="audit-filter-target"
          className={styles.filterSelect}
          value={filters.target_type ?? ""}
          onChange={(e) => patch({ target_type: e.target.value })}
        >
          {AUDIT_TARGET_TYPE_CHOICES.map((opt) => (
            <option key={opt.value || "any"} value={opt.value}>
              {opt.label || t("common.all")}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.filterField}>
        <label className={styles.filterLabel} htmlFor="audit-filter-success">
          {t("admin.audit.filter_success")}
        </label>
        <select
          id="audit-filter-success"
          data-testid="audit-filter-success"
          className={styles.filterSelect}
          value={filters.success ?? ""}
          onChange={(e) =>
            patch({ success: (e.target.value || "") as AuditFilters["success"] })
          }
        >
          <option value="">{t("common.all")}</option>
          <option value="true">{t("admin.audit.success_yes")}</option>
          <option value="false">{t("admin.audit.success_no")}</option>
        </select>
      </div>

      <div className={styles.filterField}>
        <label className={styles.filterLabel} htmlFor="audit-filter-start">
          {t("admin.audit.filter_start_date")}
        </label>
        <input
          id="audit-filter-start"
          data-testid="audit-filter-start"
          className={styles.filterInput}
          type="date"
          value={filters.start_date ?? ""}
          onChange={(e) => patch({ start_date: e.target.value })}
        />
      </div>

      <div className={styles.filterField}>
        <label className={styles.filterLabel} htmlFor="audit-filter-end">
          {t("admin.audit.filter_end_date")}
        </label>
        <input
          id="audit-filter-end"
          data-testid="audit-filter-end"
          className={styles.filterInput}
          type="date"
          value={filters.end_date ?? ""}
          onChange={(e) => patch({ end_date: e.target.value })}
        />
      </div>

      <div className={styles.filterActions}>
        <button
          type="button"
          className={styles.ctaSecondary}
          data-testid="audit-filter-reset"
          onClick={onReset}
        >
          {t("admin.audit.reset_filters")}
        </button>
      </div>
    </form>
  );
}

export default AuditFilterBar;
