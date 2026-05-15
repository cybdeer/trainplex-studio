/**
 * Shared types for the TrainPlex Admin India Heatmap page.
 *
 * Mirrors the backend contract in
 * `label_studio/core/views_heatmap.py::_get_mock_state_activity`. Single
 * source of truth on the frontend so the map + table + legend agree on
 * shapes without duck-typing.
 *
 * Phase 1 Step 4.2-6.
 */

/** One state entry from GET /api/v1/admin/heatmap/state-activity. */
export interface StateActivity {
  /** ISO 3166-2:IN-* short code, e.g. "RJ" for Rajasthan. */
  state_code: string;
  /** Display name, English (e.g. "Rajasthan"). */
  state_name: string;
  /** Distinct active trainers operating in this state for the period. */
  active_trainers: number;
  /** Total submissions across all trainers in this state for the period. */
  submissions_count: number;
  /** Total earnings in whole INR (no paise) for the period. */
  total_earnings_inr: number;
}

/** Aggregation window the backend accepts on `?period=`. */
export type HeatmapPeriod = "today" | "week" | "month";

/** Sortable columns in the fallback state table. */
export type HeatmapSortKey =
  | "active_trainers"
  | "submissions_count"
  | "total_earnings_inr"
  | "state_name";
