"""TrainPlex Reports + BI app — Phase 1 Step 7.

Founder dashboard + Trainer leaderboard + Cohort analysis + Project ROI +
Auto-email schedules. All endpoints are admin-gated via @require_role.

Phase 1 status
--------------
All services return deterministic MOCK snapshots so the React surfaces can be
built and pinned by tests against a stable contract. Real DB aggregation lands
in Phase 2 / Step 8 (the same SUBMISSIONS / PAYMENTS / TRAINERS tables that the
heatmap + dashboard widget will swap onto).
"""

default_app_config = 'reports.apps.ReportsConfig'
