// TrainPlex k6 load scenario — Login Burst.
//
// Target (per Week 8 plan):
//   * 100 concurrent logins / second sustained for 60 seconds.
//   * p95 < 500ms (login is the cold-start path; if it cracks here,
//     trainers waiting for the daily 9am push notification will see
//     the spinner of doom).
//   * Error rate < 1%.
//
// Why a separate scenario for login: it's the only endpoint that hits
// both Django session middleware and the password hasher (PBKDF2 by
// default = expensive). Spiking it isolates whether gunicorn workers
// or the DB pool is the bottleneck.
//
// Run:
//   k6 run -e BASE=https://staging.trainplex.in login_burst.js
//
// CI gate: see `loadtest/k6/README.md` for the GitHub Actions wrapper.

import { sleep } from 'k6';
import { loginAs, pickTrainer, SHARED_THRESHOLDS } from '../lib/auth.js';

export const options = {
  scenarios: {
    burst: {
      // Constant-arrival-rate gives us the *requested* RPS regardless of
      // VU response time — the cleanest way to verify "100 logins/sec".
      // If the server can't keep up we'll spawn more VUs (up to max).
      executor: 'constant-arrival-rate',
      rate: 100,
      timeUnit: '1s',
      duration: '60s',
      preAllocatedVUs: 100,
      maxVUs: 400,
      tags: { scenario: 'login_burst' },
    },
  },
  thresholds: {
    ...SHARED_THRESHOLDS,
    // Login-specific tightening — if login alone exceeds the global
    // budget the whole platform feels broken at 9am push.
    'http_req_duration{name:login_post}': ['p(95)<500', 'p(99)<1000'],
  },
};

export default function () {
  // Each iteration picks a different synthetic trainer so we don't
  // serialise on a single account / session row.
  const email = pickTrainer(__ITER + __VU * 1000);
  loginAs(email);
  // Tight think-time — login_burst is the worst-case "everyone arrives
  // in the same second" event (e.g. WhatsApp blast at 9am).
  sleep(0.1);
}
