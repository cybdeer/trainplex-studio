/**
 * HeatmapPage — TrainPlex Admin India geographic activity heatmap.
 *
 * Phase 1 Step 4.2-6. Per plan: "State-wise active trainers, intensity
 * color (dark = zyada activity). Geo-distribution at glance, hiring
 * decisions easier."
 *
 * Layout
 * ------
 *   ┌────────────────────────────────────────────────────┐
 *   │ India Activity Heatmap   [Today][Week][Month]      │  ← Indigo header
 *   ├──────────────────────────┬─────────────────────────┤
 *   │ State tile grid          │ Sortable state table    │
 *   │  RJ ███  UP ███  ...     │ State | Trainers | …    │
 *   │ (intensity = trainers)   │  (sort by any column)   │
 *   ├──────────────────────────┴─────────────────────────┤
 *   │  light gradient → dark      light → more activity  │
 *   └────────────────────────────────────────────────────┘
 *
 * Data
 * ----
 * Fetches `GET /api/v1/admin/heatmap/state-activity?period=...` (admin-only).
 * In Phase 1 the backend returns mock data for 17 Indian states; the JSON
 * contract is pinned by `core/tests/test_heatmap.py` so this UI stays stable
 * when real DB wiring lands in Phase 2 / Step 8.
 *
 * Map approach
 * ------------
 * Phase 1 ships a CSS-grid of state tiles (the agreed-upon fallback). Adding
 * `react-simple-maps` would require a lockfile change, which this agent run
 * cannot safely do. Phase 2 swaps `<IndiaMap />` for the real GeoJSON-driven
 * `<ComposableMap />` — the underlying data shape (`StateActivity`) does not
 * change, so this is a one-component swap.
 */

import { Button, RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { IndiaMap } from "./IndiaMap";
import { StateTable } from "./StateTable";
import type { HeatmapPeriod, StateActivity } from "./types";
import styles from "./Heatmap.module.css";

const HEATMAP_QUERY_KEY = "admin-heatmap-state-activity";

const PERIODS: { value: HeatmapPeriod; i18nKey: string; testId: string }[] = [
  { value: "today", i18nKey: "admin.heatmap.period_today", testId: "period-today" },
  { value: "week", i18nKey: "admin.heatmap.period_week", testId: "period-week" },
  { value: "month", i18nKey: "admin.heatmap.period_month", testId: "period-month" },
];

/** Loading skeleton — same dimensions as the live grid so there's no CLS. */
function HeatmapSkeleton({ loadingLabel }: { loadingLabel: string }) {
  return (
    <div className={styles.loadingBox} role="status" aria-live="polite" data-testid="heatmap-skeleton">
      <Spinner />
      <span>{loadingLabel}</span>
    </div>
  );
}

export const HeatmapPage: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();
  const [period, setPeriod] = useState<HeatmapPeriod>("month");

  // Query key includes the period so React Query caches each period
  // separately — pressing Today → Month → Today is instant after the
  // first fetch of each.
  const { data, isFetching, isError } = useQuery<StateActivity[]>({
    queryKey: [HEATMAP_QUERY_KEY, period],
    queryFn: async () => {
      const res = await api.callApi("adminHeatmapStateActivity", {
        params: { period },
      });
      return (res as StateActivity[]) ?? [];
    },
    // Heatmap is "right now" — small stale window so the founder can refresh
    // by clicking the period filter again without an unnecessary refetch.
    staleTime: 30_000,
    enabled: user?.role === "admin",
  });

  return (
    <main className={`p-6 ${styles.heatmapRoot}`} data-testid="admin-heatmap-page">
      <RoleGate
        allow={["admin"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="heatmap-forbidden">
            403 — admin only
          </div>
        }
      >
        <header className={styles.heatmapHeader}>
          <h1 className={styles.heatmapTitle}>{t("admin.heatmap.title")}</h1>
          <div className={styles.periodFilterRow} role="group" aria-label="period filter">
            {PERIODS.map((p) => {
              const active = p.value === period;
              return (
                <Button
                  key={p.value}
                  look={active ? "filled" : "outlined"}
                  size="small"
                  className={`${styles.periodPill} ${active ? styles.periodPillActive : ""}`}
                  data-testid={p.testId}
                  data-active={active ? "true" : "false"}
                  onClick={() => setPeriod(p.value)}
                >
                  {t(p.i18nKey)}
                </Button>
              );
            })}
          </div>
        </header>

        {isFetching && !data ? (
          <HeatmapSkeleton loadingLabel={t("admin.heatmap.loading")} />
        ) : isError || !data ? (
          <div className={styles.errorBox} data-testid="heatmap-error">
            {t("admin.heatmap.load_failed")}
          </div>
        ) : (
          <div className={styles.heatmapBody}>
            <IndiaMap data={data} />
            <StateTable data={data} />
          </div>
        )}
      </RoleGate>
    </main>
  );
};

HeatmapPage.title = "India Activity Heatmap";
HeatmapPage.path = "/admin/heatmap";
HeatmapPage.exact = true;

export default HeatmapPage;
