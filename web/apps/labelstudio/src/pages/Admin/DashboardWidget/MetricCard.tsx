/**
 * MetricCard — single KPI tile for the admin dashboard.
 *
 * Phase 1 Step 4.2-1. Used by `DashboardWidget` as the building block of the
 * 4-tile KPI row. Visual styling pulls from `DashboardWidget.module.css` so
 * the tile inherits the TrainPlex Indigo header treatment + Orange CTA
 * accent. Component itself is dumb — no API calls, no i18n; the parent passes
 * in already-translated `label` and pre-formatted `value`.
 */

import type { ReactNode } from "react";
import styles from "./DashboardWidget.module.css";

export interface MetricCardProps {
  /** Already-translated tile label (e.g. "Submissions" / "जमा कार्य"). */
  label: string;
  /** Pre-formatted display value (e.g. "142" or "₹4,200"). */
  value: ReactNode;
  /**
   * Optional delta (% change vs yesterday). Positive number renders a green ↑,
   * negative renders a red ↓, zero / undefined renders nothing.
   */
  deltaPct?: number;
  /** Optional accent — tint the value to convey severity (e.g. red for alerts). */
  tone?: "default" | "warning" | "danger";
  /** Optional leading icon slot. */
  icon?: ReactNode;
  /** Stable test id so tests can grab tiles deterministically. */
  testId?: string;
}

const formatDelta = (pct: number) => {
  const abs = Math.abs(pct);
  const sign = pct > 0 ? "+" : "−";
  return `${sign}${abs}%`;
};

export function MetricCard({
  label,
  value,
  deltaPct,
  tone = "default",
  icon,
  testId,
}: MetricCardProps) {
  const showDelta = typeof deltaPct === "number" && deltaPct !== 0;
  const deltaClass =
    deltaPct !== undefined && deltaPct < 0
      ? styles.deltaDown
      : styles.deltaUp;

  return (
    <div
      className={`${styles.metricCard} ${tone !== "default" ? styles[`tone_${tone}`] : ""}`}
      data-testid={testId}
      role="group"
      aria-label={label}
    >
      <div className={styles.metricCardHeader}>
        {icon ? <span className={styles.metricCardIcon}>{icon}</span> : null}
        <span className={styles.metricCardLabel}>{label}</span>
      </div>
      <div className={styles.metricCardValueRow}>
        <span className={styles.metricCardValue} data-testid={testId ? `${testId}-value` : undefined}>
          {value}
        </span>
        {showDelta ? (
          <span
            className={`${styles.metricCardDelta} ${deltaClass}`}
            data-testid={testId ? `${testId}-delta` : undefined}
            aria-label={`${deltaPct! >= 0 ? "up" : "down"} ${Math.abs(deltaPct!)} percent`}
          >
            {deltaPct! >= 0 ? "▲" : "▼"} {formatDelta(deltaPct!)}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export default MetricCard;
