/**
 * CohortHeatmap — Day 7 / 30 / 60 / 90 retention grid.
 *
 * Phase 1 Step 7. Each row is a cohort; each cell is the retention % shaded
 * green→amber→red by intensity. The intensity buckets are coarse so the
 * founder pattern-recognises high-vs-low retention waves at a glance without
 * needing legend-text reading.
 */

import { useTranslation } from "@humansignal/app-common";
import type { CohortRetentionWave } from "./types";
import styles from "./Reports.module.css";

interface CohortHeatmapProps {
  waves: CohortRetentionWave[];
  testId?: string;
}

const toneFor = (pct: number): string => {
  if (pct >= 90) return styles.tone90;
  if (pct >= 80) return styles.tone80;
  if (pct >= 70) return styles.tone70;
  if (pct >= 60) return styles.tone60;
  if (pct >= 50) return styles.tone50;
  if (pct >= 40) return styles.tone40;
  if (pct >= 30) return styles.tone30;
  return styles.toneLow;
};

export function CohortHeatmap({ waves, testId }: CohortHeatmapProps) {
  const { t } = useTranslation();

  return (
    <div className={styles.tableContainer} data-testid={testId}>
      <div
        className={styles.cohortHeatmap}
        role="table"
        aria-label={t("admin.reports.cohorts")}
      >
        {/* Header row */}
        <div className={styles.cohortHeaderCell} role="columnheader">
          {t("admin.reports.cohort_wave")}
        </div>
        <div className={styles.cohortHeaderCell} role="columnheader">
          {t("admin.reports.cohort_day_7")}
        </div>
        <div className={styles.cohortHeaderCell} role="columnheader">
          {t("admin.reports.cohort_day_30")}
        </div>
        <div className={styles.cohortHeaderCell} role="columnheader">
          {t("admin.reports.cohort_day_60")}
        </div>
        <div className={styles.cohortHeaderCell} role="columnheader">
          {t("admin.reports.cohort_day_90")}
        </div>

        {/* Wave rows */}
        {waves.map((w) => (
          <div role="row" key={w.wave_name} style={{ display: "contents" }}>
            <div className={styles.cohortLabelCell} role="cell">
              <span>{w.wave_name}</span>
              <span className={styles.cohortCohortSize}>
                {t("admin.reports.cohort_size_n", { count: w.cohort_size })}
              </span>
            </div>
            <div
              className={`${styles.cohortRetentionCell} ${toneFor(w.day_7)}`}
              role="cell"
              data-testid={`cohort-${w.wave_name}-d7`}
            >
              {w.day_7}%
            </div>
            <div
              className={`${styles.cohortRetentionCell} ${toneFor(w.day_30)}`}
              role="cell"
              data-testid={`cohort-${w.wave_name}-d30`}
            >
              {w.day_30}%
            </div>
            <div
              className={`${styles.cohortRetentionCell} ${toneFor(w.day_60)}`}
              role="cell"
              data-testid={`cohort-${w.wave_name}-d60`}
            >
              {w.day_60}%
            </div>
            <div
              className={`${styles.cohortRetentionCell} ${toneFor(w.day_90)}`}
              role="cell"
              data-testid={`cohort-${w.wave_name}-d90`}
            >
              {w.day_90}%
            </div>
          </div>
        ))}
      </div>

      {/* Tone legend so a colourblind viewer can still decode */}
      <div className={styles.legendRow} aria-hidden="true">
        <span>
          <span className={`${styles.legendSwatch} ${styles.tone90}`} />
          90+
        </span>
        <span>
          <span className={`${styles.legendSwatch} ${styles.tone80}`} />
          80-89
        </span>
        <span>
          <span className={`${styles.legendSwatch} ${styles.tone70}`} />
          70-79
        </span>
        <span>
          <span className={`${styles.legendSwatch} ${styles.tone60}`} />
          60-69
        </span>
        <span>
          <span className={`${styles.legendSwatch} ${styles.tone50}`} />
          50-59
        </span>
        <span>
          <span className={`${styles.legendSwatch} ${styles.toneLow}`} />
          {`<30`}
        </span>
      </div>
    </div>
  );
}

export default CohortHeatmap;
