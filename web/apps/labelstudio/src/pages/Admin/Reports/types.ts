/**
 * Shared types for the TrainPlex Reports + BI suite.
 * Mirrors the backend contract from `label_studio/reports/services/*`.
 *
 * Phase 1 Step 7. Keep this file in lockstep with the service layer.
 */

// --- Founder weekly snapshot ---

export interface FounderTopKpis {
  submissions_weekly: number;
  submissions_delta_pct: number;
  revenue_weekly_inr: number;
  revenue_delta_pct: number;
  active_trainers: number;
  active_trainers_delta_pct: number;
  avg_payout_per_trainer_inr: number;
}

export interface TrendSubmissionsPoint {
  date: string;
  count: number;
}

export interface TrendRevenuePoint {
  month: string;
  revenue_inr: number;
}

export interface TrendTrainerGrowthPoint {
  month: string;
  active_trainers: number;
}

export interface FounderTrendLines {
  submissions_over_time: TrendSubmissionsPoint[];
  revenue_mom: TrendRevenuePoint[];
  trainer_growth: TrendTrainerGrowthPoint[];
}

export interface CohortRetentionWave {
  wave_name: string;
  wave_start: string;
  cohort_size: number;
  day_7: number;
  day_30: number;
  day_60: number;
  day_90: number;
}

export interface FounderProjectRoiRow {
  project_id: number;
  project_name: string;
  cost_inr: number;
  revenue_inr: number;
  roi_pct: number;
}

export interface GeographicSplitRow {
  state_code: string;
  state_name: string;
  submissions: number;
  active_trainers: number;
  earnings_inr: number;
}

export interface LanguageSplitRow {
  language_code: string;
  language_name: string;
  submissions: number;
  avg_quality_pct: number;
}

export interface ProblematicTrainer {
  trainer_id: number;
  name: string;
  state: string;
  dispute_count: number;
  submissions: number;
  dispute_rate_pct: number;
}

export interface QualityKpis {
  avg_consensus_pct: number;
  dispute_rate_pct: number;
  avg_consensus_pct_delta: number;
  dispute_rate_pct_delta: number;
  top_10_problematic: ProblematicTrainer[];
}

export interface FounderWeeklySnapshot {
  week_start: string;
  week_end: string;
  generated_at: string;
  top_kpis: FounderTopKpis;
  trend_lines: FounderTrendLines;
  cohort_retention: CohortRetentionWave[];
  project_roi: FounderProjectRoiRow[];
  geographic_split: GeographicSplitRow[];
  language_split: LanguageSplitRow[];
  quality_kpis: QualityKpis;
}

// --- Leaderboard ---

export type LeaderboardPeriod = "daily" | "weekly" | "monthly";

export interface LeaderboardRow {
  rank: number;
  trainer_id: number;
  name: string;
  state: string;
  tier: string;
  language: string;
  project_type: string;
  tasks_done: number;
  earnings_inr: number;
  quality_score_pct: number;
  consistency_pct: number;
}

export interface HallOfFameRow {
  rank: number;
  trainer_id: number;
  name: string;
  state: string;
  lifetime_tasks?: number;
  lifetime_earnings_inr?: number;
  tasks_this_month?: number;
  earnings_this_month_inr?: number;
}

export interface LeaderboardPayload {
  period: LeaderboardPeriod;
  filters: {
    state: string | null;
    tier: string | null;
    language: string | null;
    project_type: string | null;
  };
  total: number;
  results: LeaderboardRow[];
  hall_of_fame_lifetime: HallOfFameRow[];
  hall_of_fame_month: HallOfFameRow[];
}

// --- Cohorts ---

export interface CohortRetentionPoint {
  day: number;
  retention_pct: number;
}

export interface CohortProductivityPoint {
  week: number;
  avg_tasks_per_day: number;
}

export interface CohortEarningsPoint {
  week: number;
  cumulative_earnings_inr: number;
}

export interface CohortDropOffStage {
  stage: string;
  trainers_remaining: number;
  drop_pct: number;
}

export interface CohortMetrics {
  cohort_id: string;
  cohort_name: string;
  cohort_start: string;
  cohort_size: number;
  retention_curve: CohortRetentionPoint[];
  productivity_curve: CohortProductivityPoint[];
  earnings_curve: CohortEarningsPoint[];
  drop_off_analysis: CohortDropOffStage[];
}

export interface CohortsPayload {
  cohort_definition: "registration_week" | "signup_wave" | "tier_promotion_month";
  cohorts: CohortMetrics[];
}

// --- Project ROI ---

export interface ProjectROIRow {
  project_id: number;
  project_name: string;
  project_type: string;
  language: string;
  tasks_created: number;
  tasks_completed: number;
  trainer_payout_inr: number;
  reviewer_payout_inr: number;
  infra_cost_inr: number;
  total_cost_inr: number;
  external_revenue_inr: number;
  profit_inr: number;
  roi_pct: number;
  cost_per_quality_task_inr: number;
  time_to_complete_days: number;
  quality_score_pct: number;
}

export interface ProjectROIList {
  results: ProjectROIRow[];
}
