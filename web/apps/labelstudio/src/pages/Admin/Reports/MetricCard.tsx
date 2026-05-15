/**
 * MetricCard — KPI tile for the Reports surfaces.
 *
 * Phase 1 Step 7. Mirrors the DashboardWidget MetricCard contract so the two
 * surfaces feel consistent, but lives in the Reports module so the founder
 * dashboard can evolve independently. Keep it dumb — the parent passes in an
 * already-translated `label` and a pre-formatted `value`.
 */

import type { ReactNode } from "react";
import styles from "./Reports.module.css";

export interface ReportsMetricCardProps {
  /** Already-translated tile label. */
  label: string;
  /** Pre-formatted display value (e.g. "8,420" or "₹4,12,500"). */
  value: ReactNode;
  /** Optional delta vs previous period. Positive = green up, negative = red down. */
  deltaPct?: number;
  /** Stable test id so tests can grab tiles deterministically. */
  testId?: string;
}

export function MetricCard({ label, value, deltaPct, testId }: ReportsMetricCardProps) {
  const showDelta = typeof deltaPct === "number" && deltaPct !== 0;
  const deltaClass = (deltaPct ?? 0) < 0 ? styles.kpiDeltaDown : styles.kpiDeltaUp;
  return (
    <div className={styles.kpiCard} data-testid={testId} role="group" aria-label={label}>
      <span className={styles.kpiLabel}>{label}</span>
      <div className={styles.kpiValueRow}>
        <span className={styles.kpiValue} data-testid={testId ? `${testId}-value` : undefined}>
          {value}
        </span>
        {showDelta ? (
          <span
            className={`${styles.kpiDelta} ${deltaClass}`}
            data-testid={testId ? `${testId}-delta` : undefined}
            aria-label={`${deltaPct! >= 0 ? "up" : "down"} ${Math.abs(deltaPct!)} percent`}
          >
            {deltaPct! >= 0 ? "▲" : "▼"} {Math.abs(deltaPct!)}%
          </span>
        ) : null}
      </div>
    </div>
  );
}

export default MetricCard;
