/**
 * IndiaMap — TrainPlex Admin geographic heatmap (Phase 1 fallback).
 *
 * Phase 1 Step 4.2-6.
 *
 * Approach
 * --------
 * The spec preferred `react-simple-maps` (real GeoJSON polygons of Indian
 * states). Adding that to the lockfile is risky in a `node_modules`-free
 * agent run, so we ship the agreed-upon fallback: a CSS-grid of state
 * tiles painted with an Indigo intensity ramp proportional to the active-
 * trainer count for the selected period.
 *
 * - Tile colour is one of 6 bands (0 → 5). 0 is "no activity" (lightest);
 *   5 is "max activity" (darkest Indigo, matches the spec "dark = zyada").
 * - Bands are computed against the page-level max so the ramp re-renders
 *   correctly when the founder changes the period filter.
 * - Each tile shows the ISO state code + the active-trainer count.
 *
 * TODO Phase 2: swap the `<div class="stateGrid">` body for the real
 * GeoJSON-driven `react-simple-maps` <ComposableMap /> once we can bring
 * the dep in cleanly. The data shape (`StateActivity`) is identical, so
 * only the renderer changes.
 */

import { useMemo } from "react";
import { useTranslation } from "@humansignal/app-common";
import type { StateActivity } from "./types";
import styles from "./Heatmap.module.css";

export interface IndiaMapProps {
  data: StateActivity[];
}

/** 6 intensity buckets — picked so 0 is its own band ("no activity"). */
const NUM_BANDS = 6;

/**
 * Bucket the trainer count into one of 6 bands.
 *
 *   0           → band 0
 *   else        → 1 + floor((count-1) / max * (NUM_BANDS - 1))
 *
 * The +1 ensures any active state lands at least in band 1; band 5 (the
 * darkest) is reserved for the page-max state. Capped at NUM_BANDS-1.
 */
function intensityBand(count: number, max: number): number {
  if (count <= 0 || max <= 0) return 0;
  const idx = 1 + Math.floor(((count - 1) / max) * (NUM_BANDS - 2));
  return Math.max(0, Math.min(NUM_BANDS - 1, idx));
}

const formatInt = (locale: string, value: number) =>
  new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN").format(value);

export function IndiaMap({ data }: IndiaMapProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";

  // Compute the max active_trainers count so the colour ramp scales to the
  // current period (today vs week vs month all have different max bands).
  const maxTrainers = useMemo(
    () => data.reduce((acc, row) => Math.max(acc, row.active_trainers), 0),
    [data],
  );

  return (
    <section className={styles.mapBlock} data-testid="india-map" aria-label={t("admin.heatmap.map_heading")}>
      <h3 className={styles.mapHeading}>{t("admin.heatmap.map_heading")}</h3>

      <div className={styles.stateGrid} role="grid">
        {data.map((row) => {
          const band = intensityBand(row.active_trainers, maxTrainers);
          const intensityClass =
            styles[`intensity_${band}` as keyof typeof styles] as string;
          return (
            <div
              key={row.state_code}
              className={`${styles.stateTile} ${intensityClass}`}
              role="gridcell"
              data-testid={`state-tile-${row.state_code}`}
              data-intensity={band}
              title={`${row.state_name}: ${row.active_trainers} ${t("admin.heatmap.col_trainers")}`}
              aria-label={`${row.state_name}: ${row.active_trainers} ${t("admin.heatmap.col_trainers")}`}
            >
              <span className={styles.stateTileCode}>{row.state_code}</span>
              <span className={styles.stateTileMetric}>
                {formatInt(locale, row.active_trainers)}
              </span>
              <span className={styles.stateTileLabel}>
                {t("admin.heatmap.col_trainers")}
              </span>
            </div>
          );
        })}
      </div>

      {/* Legend — light → dark gradient, with bilingual end labels */}
      <div className={styles.legend} data-testid="heatmap-legend">
        <span>{t("admin.heatmap.legend_light")}</span>
        <span className={styles.legendBar} aria-hidden="true" />
        <span>{t("admin.heatmap.legend_dark")}</span>
      </div>
    </section>
  );
}

export default IndiaMap;
