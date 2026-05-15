// TrainPlex k6 load scenario — WhatsApp Broadcast fan-out.
//
// Target:
//   * One admin fires a broadcast to 100 trainers and waits for the
//     mock-AiSensy fan-out to complete.
//   * Tests both the `/api/v1/admin/wa/broadcast` POST (rate-limited
//     to 3 per hour per admin in code, but we hit it as a single VU
//     so we don't burn the limiter) AND the history pagination.
//   * p95 < 1500ms for the broadcast call (it touches `htx_wa_broadcast_log`
//     N times; we want to know if the bulk insert is healthy).
//
// Why a separate scenario:
//   * Broadcast is the lowest-frequency / highest-burst endpoint we own.
//     A single call can produce 100 outbound network calls to AiSensy.
//     We need to verify the in-band call returns fast and the per-row
//     log inserts don't lock up the table.
//
// Run:
//   k6 run -e BASE=https://staging.trainplex.in wa_broadcast.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { loginAs, pickAdmin, BASE, SHARED_THRESHOLDS } from '../lib/auth.js';

export const options = {
  scenarios: {
    broadcast_send: {
      executor: 'per-vu-iterations',
      // 5 admins, 3 broadcasts each = 15 total. We deliberately stay
      // under the per-admin rate limit (3/hr) so the scenario isolates
      // *throughput*, not *throttling*.
      vus: 5,
      iterations: 3,
      maxDuration: '5m',
      tags: { scenario: 'wa_broadcast' },
    },
  },
  thresholds: {
    ...SHARED_THRESHOLDS,
    'http_req_duration{name:wa_broadcast}': ['p(95)<1500', 'p(99)<3000'],
    'http_req_duration{name:wa_history}': ['p(95)<500'],
  },
};

function buildBroadcastBody(adminIdx, iter) {
  // Templates list endpoint in production returns the catalog; for the
  // loadtest we hard-code a known template name + 100-trainer recipient
  // set. The Phase 1 mock fan-out logs each recipient to
  // `htx_wa_broadcast_log`.
  return JSON.stringify({
    template_name: 'tpl_payout_released',
    recipients: Array.from({ length: 100 }).map((_, i) => ({
      trainer_id: i + 1,
      mobile: `+91900000${String(i).padStart(4, '0')}`,
      // Deterministic but not equal so dedup doesn't kick in.
      vars: { name: `Trainer ${i}`, amount: 250 + adminIdx * 10 + iter },
    })),
    test_mode: true, // mock fan-out path; doesn't dial real AiSensy
  });
}

export default function () {
  const adminIdx = __VU % 5;
  const email = pickAdmin(adminIdx);
  loginAs(email);

  // The broadcast call itself.
  const sendRes = http.post(
    `${BASE}/api/v1/admin/wa/broadcast`,
    buildBroadcastBody(adminIdx, __ITER),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { name: 'wa_broadcast' },
    },
  );
  check(sendRes, {
    'broadcast 200/202': (r) => r.status === 200 || r.status === 202,
    'broadcast has dispatched_count': (r) =>
      r.body && r.body.indexOf('dispatched_count') !== -1,
  });

  // History page right after — admin always opens it to verify rollout.
  const histRes = http.get(`${BASE}/api/v1/admin/wa/broadcast/history?page=1`, {
    tags: { name: 'wa_history' },
  });
  check(histRes, { 'history 200': (r) => r.status === 200 });

  sleep(2);
}
