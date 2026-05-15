// TrainPlex k6 load scenario — Realistic Combined Workload.
//
// Target:
//   * Mix of all four hot paths in production proportions, run for 15min.
//   * Simulates a "typical Tuesday afternoon" — most users are trainers
//     submitting, a handful of admins watching the dashboard, one
//     reviewer working a queue, occasional broadcasts.
//   * p95 < 500ms for /api/v1/* (the global SLO).
//
// Workload mix (per Phase 1 BUILD_LOG analytics):
//   * 80% trainers — login + view batch + submit
//   * 15% admins   — login + dashboard poll
//   * 4% reviewers — login + review queue + consensus vote
//   * 1% admins    — login + WA broadcast (rate-limited)
//
// k6 implements the mix with named scenarios that all run in parallel.
//
// Run:
//   k6 run -e BASE=https://staging.trainplex.in full_workflow.js
//
// CI gate: this scenario is the one we report against the Step-9.5 SLO.

import http from 'k6/http';
import { check, sleep } from 'k6';
import {
  loginAs,
  pickTrainer,
  pickAdmin,
  BASE,
  SHARED_THRESHOLDS,
} from '../lib/auth.js';

// Roll forward in the same iteration counter space so VUs don't clobber
// each other's email pool slots.
function trainerForVU() {
  return pickTrainer(__VU * 31 + __ITER);
}
function adminForVU() {
  return pickAdmin(__VU + __ITER);
}

// ── trainer flow ──────────────────────────────────────────────────────
function trainerFlow() {
  loginAs(trainerForVU());
  const batch = http.get(`${BASE}/api/v1/trainer/batch`, {
    tags: { name: 'trainer_batch_get' },
  });
  check(batch, { 'batch 200': (r) => r.status === 200 });
  // Submit half of the 10-task batch to reflect a mid-shift snapshot;
  // most trainers don't finish all 10 in one go.
  for (let i = 0; i < 5; i++) {
    const res = http.post(
      `${BASE}/api/v1/trainer/batch/submit`,
      JSON.stringify({
        task_id: __VU * 100 + i,
        answer: { choice: 'cat', confidence: 0.9 },
        client_ts: Date.now(),
      }),
      {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'submit' },
      },
    );
    check(res, { 'submit ok': (r) => r.status >= 200 && r.status < 300 });
    sleep(0.5 + Math.random() * 1.0);
  }
}

// ── admin flow (dashboard polling) ────────────────────────────────────
function adminDashboardFlow() {
  loginAs(adminForVU());
  http.get(`${BASE}/api/v1/admin/dashboard/snapshot`, {
    tags: { name: 'dashboard_snapshot' },
  });
  http.get(`${BASE}/api/v1/admin/heatmap/state-activity?period=7d`, {
    tags: { name: 'heatmap' },
  });
  http.get(`${BASE}/api/v1/admin/submissions/preview?limit=20`, {
    tags: { name: 'submissions_preview' },
  });
  sleep(20 + Math.random() * 20);
}

// ── reviewer flow ─────────────────────────────────────────────────────
function reviewerFlow() {
  loginAs(`reviewer${(__VU % 5) + 1}@loadtest.trainplex.in`);
  http.get(`${BASE}/api/v1/reviewer/queue?limit=20`, { tags: { name: 'reviewer_queue' } });
  // Vote on the top of queue — Phase 1 mock accepts any decision JSON.
  http.post(
    `${BASE}/api/v1/reviewer/vote`,
    JSON.stringify({ submission_id: __VU + __ITER, decision: 'accept', note: 'OK' }),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { name: 'reviewer_vote' },
    },
  );
  sleep(3);
}

// ── admin broadcast flow ──────────────────────────────────────────────
function broadcastFlow() {
  loginAs(adminForVU());
  http.post(
    `${BASE}/api/v1/admin/wa/broadcast`,
    JSON.stringify({
      template_name: 'tpl_daily_announcement',
      recipients: Array.from({ length: 50 }).map((_, i) => ({
        trainer_id: i + 1,
        mobile: `+91900000${String(i).padStart(4, '0')}`,
        vars: { name: `T${i}` },
      })),
      test_mode: true,
    }),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { name: 'wa_broadcast' },
    },
  );
  sleep(60);
}

export const options = {
  scenarios: {
    trainers: {
      executor: 'constant-vus',
      vus: 80,
      duration: '15m',
      exec: 'trainers',
    },
    admins_dashboard: {
      executor: 'constant-vus',
      vus: 15,
      duration: '15m',
      exec: 'adminsDashboard',
    },
    reviewers: {
      executor: 'constant-vus',
      vus: 4,
      duration: '15m',
      exec: 'reviewers',
    },
    broadcasts: {
      executor: 'constant-vus',
      vus: 1,
      duration: '15m',
      exec: 'broadcasts',
    },
  },
  thresholds: SHARED_THRESHOLDS,
};

export function trainers() {
  trainerFlow();
}
export function adminsDashboard() {
  adminDashboardFlow();
}
export function reviewers() {
  reviewerFlow();
}
export function broadcasts() {
  broadcastFlow();
}
