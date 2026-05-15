// TrainPlex k6 load scenario — Admin Dashboard view.
//
// Target:
//   * 50 admins concurrently polling the dashboard snapshot endpoint.
//   * Real-world correlate: morning standup where 5 admins each open the
//     dashboard, plus 45 schedule auto-refresh tabs (the React app polls
//     every 30s by default).
//   * p95 < 400ms (dashboard is fully aggregate / read-only, so anything
//     slower means we forgot to denormalise something).
//
// This scenario exercises the heaviest read paths:
//   * /api/v1/admin/dashboard/snapshot
//   * /api/v1/admin/heatmap/state-activity
//   * /api/v1/admin/submissions/preview
//   * /api/v1/admin/quality-alerts (top-of-page badge)
//
// Run:
//   k6 run -e BASE=https://staging.trainplex.in dashboard.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { loginAs, pickAdmin, BASE, SHARED_THRESHOLDS } from '../lib/auth.js';

export const options = {
  scenarios: {
    admin_dashboard: {
      executor: 'constant-vus',
      vus: 50,
      duration: '3m',
      tags: { scenario: 'dashboard' },
    },
  },
  thresholds: {
    ...SHARED_THRESHOLDS,
    'http_req_duration{name:dashboard_snapshot}': ['p(95)<400'],
    'http_req_duration{name:heatmap}': ['p(95)<500'],
    'http_req_duration{name:submissions_preview}': ['p(95)<500'],
  },
};

export default function () {
  const email = pickAdmin(__VU);
  loginAs(email);

  // Hit each tile in the order the React `<DashboardPage />` mounts them.
  // We don't parallelise here because the real browser doesn't either —
  // the SPA fires them sequentially after the page shell renders.
  let res = http.get(`${BASE}/api/v1/admin/dashboard/snapshot`, {
    tags: { name: 'dashboard_snapshot' },
  });
  check(res, { 'snapshot 200': (r) => r.status === 200 });

  res = http.get(`${BASE}/api/v1/admin/heatmap/state-activity?period=7d`, {
    tags: { name: 'heatmap' },
  });
  check(res, { 'heatmap 200': (r) => r.status === 200 });

  res = http.get(`${BASE}/api/v1/admin/submissions/preview?limit=20`, {
    tags: { name: 'submissions_preview' },
  });
  check(res, { 'preview 200': (r) => r.status === 200 });

  res = http.get(`${BASE}/api/v1/admin/quality-alerts/stats`, {
    tags: { name: 'quality_alerts_stats' },
  });
  check(res, { 'quality stats 200': (r) => r.status === 200 });

  // Simulate the 30s SPA auto-refresh cadence.
  sleep(30);
}
