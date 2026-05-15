/**
 * Shared types for the TrainPlex Admin Dashboard widget.
 * Mirrors the backend contract from
 * `label_studio/core/views_dashboard.py::_get_mock_dashboard_snapshot`.
 *
 * Phase 1 Step 4.2-1. Keep this file in lockstep with the backend response.
 */

export interface DashboardTopTrainer {
  id: number;
  name: string;
  state: string;
  tasks_today: number;
  earnings_today_inr: number;
}

export interface DashboardTodayKpis {
  submissions_count: number;
  submissions_delta_pct: number;
  active_trainers: number;
  pay_hold_total_inr: number;
  pay_released_today_inr: number;
}

export interface DashboardAlerts {
  disputes_pending: number;
  quality_flags: number;
  stuck_payouts: number;
}

export interface DashboardSnapshot {
  as_of: string;
  today: DashboardTodayKpis;
  top_trainers: DashboardTopTrainer[];
  alerts: DashboardAlerts;
}
