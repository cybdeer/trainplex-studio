/**
 * AlertFilterBar — controls for narrowing the quality-alert query.
 *
 * Phase 1 Step 4.2-8. Renders four inputs above the table:
 *   - Status     (dropdown, all / open / reviewed / dismissed / action_taken)
 *   - Severity   (dropdown, all / low / medium / high / critical)
 *   - Trigger    (dropdown, all / disagree / time / duplicate / conflict / cert)
 *   - Trainer ID (numeric text input — admin pastes an id from another page)
 *
 * Fully controlled — the parent owns the `AlertFilters` object. Resetting
 * clears every field so the page returns the full unfiltered listing.
 *
 * Pattern mirrors `AuditFilterBar` exactly so admins who have used the
 * audit-log page already know the affordance.
 */

import { useTranslation } from "@humansignal/app-common";
import {
  ALERT_SEVERITY_CHOICES,
  ALERT_STATUS_CHOICES,
  ALERT_TRIGGER_CHOICES,
} from "./types";
import type {
  AlertFilters,
  AlertSeverity,
  AlertStatus,
  AlertTriggerType,
} from "./types";
import styles from "./QualityAlerts.module.css";

export interface AlertFilterBarProps {
  filters: AlertFilters;
  onFiltersChange: (next: AlertFilters) => void;
  onReset: () => void;
}

export function AlertFilterBar({
  filters,
  onFiltersChange,
  onReset,
}: AlertFilterBarProps) {
  const { t } = useTranslation();

  /** Merge a single field into the filters; bubble up; reset page=1. */
  const patch = (delta: Partial<AlertFilters>) => {
    onFiltersChange({ ...filters, ...delta, page: 1 });
  };

  return (
    <form
      className={styles.filterBar}
      data-testid="alerts-filter-bar"
      onSubmit={(e) => e.preventDefault()}
      role="search"
      aria-label={t("admin.alerts.title")}
    >
      <div className={styles.filterField}>
        <label className={styles.filterLabel} htmlFor="alert-filter-status">
          {t("admin.alerts.filter_status")}
        </label>
        <select
          id="alert-filter-status"
          data-testid="alert-filter-status"
          className={styles.filterSelect}
          value={filters.status ?? ""}
          onChange={(e) =>
            patch({ status: (e.target.value || "") as AlertStatus | "" })
          }
        >
          {ALERT_STATUS_CHOICES.map((opt) => (
            <option key={opt.value || "all"} value={opt.value}>
              {t(opt.labelKey)}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.filterField}>
        <label className={styles.filterLabel} htmlFor="alert-filter-severity">
          {t("admin.alerts.filter_severity")}
        </label>
        <select
          id="alert-filter-severity"
          data-testid="alert-filter-severity"
          className={styles.filterSelect}
          value={filters.severity ?? ""}
          onChange={(e) =>
            patch({ severity: (e.target.value || "") as AlertSeverity | "" })
          }
        >
          {ALERT_SEVERITY_CHOICES.map((opt) => (
            <option key={opt.value || "all"} value={opt.value}>
              {t(opt.labelKey)}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.filterField}>
        <label className={styles.filterLabel} htmlFor="alert-filter-trigger">
          {t("admin.alerts.filter_trigger")}
        </label>
        <select
          id="alert-filter-trigger"
          data-testid="alert-filter-trigger"
          className={styles.filterSelect}
          value={filters.trigger_type ?? ""}
          onChange={(e) =>
            patch({
              trigger_type: (e.target.value || "") as AlertTriggerType | "",
            })
          }
        >
          {ALERT_TRIGGER_CHOICES.map((opt) => (
            <option key={opt.value || "all"} value={opt.value}>
              {t(opt.labelKey)}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.filterField}>
        <label className={styles.filterLabel} htmlFor="alert-filter-trainer">
          {t("admin.alerts.filter_trainer")}
        </label>
        <input
          id="alert-filter-trainer"
          data-testid="alert-filter-trainer"
          className={styles.filterInput}
          type="number"
          inputMode="numeric"
          min={1}
          placeholder="123"
          value={filters.trainer_id === "" || filters.trainer_id == null ? "" : filters.trainer_id}
          onChange={(e) => {
            const raw = e.target.value;
            if (!raw) {
              patch({ trainer_id: "" });
              return;
            }
            const n = Number.parseInt(raw, 10);
            patch({ trainer_id: Number.isFinite(n) && n > 0 ? n : "" });
          }}
        />
      </div>

      <div className={styles.filterActions}>
        <button
          type="button"
          className={styles.ctaSecondary}
          data-testid="alerts-filter-reset"
          onClick={onReset}
        >
          {t("admin.alerts.reset_filters")}
        </button>
      </div>
    </form>
  );
}

export default AlertFilterBar;
