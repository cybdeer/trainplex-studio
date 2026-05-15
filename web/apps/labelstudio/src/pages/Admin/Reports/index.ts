/**
 * Barrel for the TrainPlex Reports + BI suite.
 * Phase 1 Step 7.
 */

export { ReportsHub, default as ReportsHubDefault } from "./ReportsHub";
export { FounderDashboard } from "./FounderDashboard";
export { Leaderboard } from "./Leaderboard";
export { CohortAnalysis } from "./CohortAnalysis";
export { ProjectROI } from "./ProjectROI";
export { MetricCard } from "./MetricCard";
export { TrendChart } from "./TrendChart";
export type { TrendChartPoint } from "./TrendChart";
export { CohortHeatmap } from "./CohortHeatmap";
export type {
  FounderWeeklySnapshot,
  LeaderboardPayload,
  LeaderboardPeriod,
  LeaderboardRow,
  CohortsPayload,
  CohortMetrics,
  ProjectROIList,
  ProjectROIRow,
} from "./types";
