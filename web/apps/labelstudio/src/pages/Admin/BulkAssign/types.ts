/**
 * Shared types for the TrainPlex Admin Bulk Task Assign page.
 *
 * Mirrors the backend contract in `label_studio/core/views_bulk_assign.py`.
 * Single source of truth on the frontend so the filter / table / form
 * components agree on shapes without duck-typing.
 *
 * Phase 1 Step 4.2-3.
 */

/** Tier values mirrored from `core.services.bulk_assign._TIER_WEIGHTS`. */
export type TrainerTier = "bronze" | "silver" | "gold" | "platinum";

/** Distribution strategies mirrored from the same module. */
export type DistributeStrategy = "even" | "tier-weighted";

/** One row from GET /api/v1/admin/trainers/filter. */
export interface TrainerMatch {
  id: number;
  name: string;
  state: string;
  tier: TrainerTier;
  language: string;
  languages: string[];
  cert_passed: boolean;
  current_active_tasks_count: number;
}

/** Response shape of GET /api/v1/admin/trainers/filter. */
export interface TrainerFilterResponse {
  count: number;
  items: TrainerMatch[];
}

/** One row in the assignment plan returned by POST /tasks/bulk-assign. */
export interface AssignmentPlanRow {
  trainer_id: number;
  name: string;
  tier: string;
  state: string;
  language: string;
  will_assign: number;
  current_active_tasks_count: number;
  unknown: boolean;
}

/** Response shape of POST /api/v1/admin/tasks/bulk-assign. */
export interface BulkAssignResponse {
  ok: boolean;
  project_id: number;
  strategy: DistributeStrategy;
  tasks_per_trainer: number;
  plan: AssignmentPlanRow[];
  totals: {
    trainers: number;
    tasks: number;
  };
  summary: {
    project_id: number;
    trainer_count: number;
    total_tasks: number;
    strategy: DistributeStrategy;
  };
}

/** Local UI state for the filter chips. */
export interface BulkFilterState {
  states: Set<string>;
  tiers: Set<string>;
  languages: Set<string>;
  cert: Set<string>;
}
