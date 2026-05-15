// TrainPlex k6 load scenario — Task Submit Storm.
//
// Target:
//   * 100 trainers logged in, each submitting a 10-task batch over 5 minutes.
//   * Real-world correlate: end-of-shift submission rush.
//   * p95 < 600ms on submit endpoints; error rate < 1%.
//
// Submit is the highest-write hot path. It triggers:
//   * task_completion insert
//   * payout queue side-effect (Phase 2 wiring)
//   * peer-review fan-out
// So if anything is going to lock the DB, it's this.
//
// Run:
//   k6 run -e BASE=https://staging.trainplex.in task_submit.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { loginAs, pickTrainer, BASE, SHARED_THRESHOLDS } from '../lib/auth.js';

export const options = {
  scenarios: {
    submit_rush: {
      executor: 'ramping-vus',
      // Ramp up to 100 over 30s, hold 4min, ramp down 30s.
      // Ramping reveals saturation curve, not just steady-state.
      startVUs: 0,
      stages: [
        { duration: '30s', target: 100 },
        { duration: '4m', target: 100 },
        { duration: '30s', target: 0 },
      ],
      tags: { scenario: 'task_submit' },
    },
  },
  thresholds: SHARED_THRESHOLDS,
};

/**
 * Build a synthetic submission payload that matches the Phase 1
 * `TrainerBatchSubmitAPI` contract (`core/views_pwa.py`).
 *
 * The view accepts any JSON body with `task_id` + `answer` keys; the
 * Phase 1 implementation echoes back a mock acceptance. The Phase 2
 * write-path will validate the shape against the project's label_config.
 */
function makeSubmission(taskId, trainerIdx) {
  return JSON.stringify({
    task_id: taskId,
    answer: {
      // Phase 1 contract: free-form object. Loadtest just needs a deterministic
      // payload so we're not measuring `json.dumps` time differences.
      choice: ['cat', 'dog', 'other'][taskId % 3],
      confidence: 0.8 + (taskId % 20) / 100,
      time_spent_ms: 3000 + (trainerIdx % 50) * 100,
    },
    client_ts: Date.now(),
  });
}

export default function () {
  const trainerIdx = (__VU + __ITER * 7) % 100;
  const email = pickTrainer(trainerIdx);
  loginAs(email);

  // Fetch the current 10-task batch.
  const batchRes = http.get(`${BASE}/api/v1/trainer/batch`, {
    tags: { name: 'trainer_batch_get' },
  });
  check(batchRes, { 'batch 200': (r) => r.status === 200 });

  // Pretend the trainer works through the batch, submitting each task.
  // 10 submissions per iteration matches the real batch shape.
  for (let i = 0; i < 10; i++) {
    const taskId = trainerIdx * 100 + i;
    const res = http.post(
      `${BASE}/api/v1/trainer/batch/submit`,
      makeSubmission(taskId, trainerIdx),
      {
        headers: { 'Content-Type': 'application/json' },
        tags: { name: 'submit' },
      },
    );
    check(res, {
      'submit 2xx': (r) => r.status >= 200 && r.status < 300,
      'submit body has accepted': (r) =>
        r.body && r.body.indexOf('accepted') !== -1,
    });
    // Human-pace gap — trainers don't fire submits in < 100ms.
    sleep(0.2 + Math.random() * 0.3);
  }
}
