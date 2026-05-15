/**
 * SeverityBadge — coloured chip for one of the 4 severity buckets.
 *
 * Phase 1 Step 4.2-8. Pure presentational. Colour ramp (from coolest →
 * hottest) mirrors the design language used by the dashboard widget:
 *   - low      → grey
 *   - medium   → amber
 *   - high     → orange
 *   - critical → red
 *
 * The label is i18n-resolved by the parent, but for a self-contained chip
 * we accept an explicit `label` prop and only fall back to the i18n key
 * `admin.alerts.severity_<value>` if no label is provided.
 */

import { useTranslation } from "@humansignal/app-common";
import type { AlertSeverity } from "./types";
import styles from "./QualityAlerts.module.css";

export interface SeverityBadgeProps {
  severity: AlertSeverity;
  /** Optional pre-resolved label. If omitted, the i18n key is used. */
  label?: string;
  /** Optional extra test-id suffix so a row of badges can be targeted. */
  testIdSuffix?: string;
}

const CLASS_BY_SEVERITY: Record<AlertSeverity, string> = {
  low: styles.sevLow,
  medium: styles.sevMedium,
  high: styles.sevHigh,
  critical: styles.sevCritical,
};

const I18N_KEY_BY_SEVERITY: Record<AlertSeverity, string> = {
  low: "admin.alerts.severity_low",
  medium: "admin.alerts.severity_medium",
  high: "admin.alerts.severity_high",
  critical: "admin.alerts.severity_critical",
};

export function SeverityBadge({ severity, label, testIdSuffix }: SeverityBadgeProps) {
  const { t } = useTranslation();
  const className = `${styles.severityBadge} ${CLASS_BY_SEVERITY[severity]}`;
  const text = label ?? t(I18N_KEY_BY_SEVERITY[severity]);
  return (
    <span
      className={className}
      data-testid={`alert-severity${testIdSuffix ? `-${testIdSuffix}` : ""}`}
      data-severity={severity}
    >
      {text}
    </span>
  );
}

export default SeverityBadge;
