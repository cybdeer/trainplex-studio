/**
 * Reviewer-side pages — TrainPlex Phase 1 Step 6.
 *
 * Routes
 * ------
 * * /reviewer/dashboard   → <ReviewerDashboard>  (pending count + CTA)
 * * /reviewer/queue       → <ReviewQueue>        (blind task list)
 * * /reviewer/review/:id  → <ReviewSplitScreen>  (split-pane form)
 * * /reviewer/stats       → <MyStats>            (self-service metrics)
 *
 * Each page wraps content in `<RoleGate allow={['reviewer']}>` so a misrouted
 * trainer / admin / QA-lead sees a 403 surface. Backend enforces the same
 * via `@require_role(['reviewer'])` on every endpoint.
 */

export { ReviewerDashboard } from "./ReviewerDashboard";
export { ReviewQueue } from "./ReviewQueue";
export { ReviewSplitScreen } from "./ReviewSplitScreen";
export { MyStats } from "./MyStats";
