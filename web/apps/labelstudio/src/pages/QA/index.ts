/**
 * QA-lead-side pages — TrainPlex Phase 1 Step 6.
 *
 * Routes
 * ------
 * * /qa/disputes              → <DisputeQueue>      (open + resolved list)
 * * /qa/disputes/:dispute_id  → <DisputeResolution> (three-way + verdict)
 *
 * Each page wraps content in `<RoleGate allow={['qa_lead']}>` so a misrouted
 * trainer / reviewer / admin sees a 403 surface. Backend enforces the same
 * via `@require_role(['qa_lead'])` on every endpoint.
 */

export { DisputeQueue } from "./DisputeQueue";
export { DisputeResolution } from "./DisputeResolution";
