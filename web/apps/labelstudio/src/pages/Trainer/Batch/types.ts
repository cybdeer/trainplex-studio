/**
 * Shared types for the TrainPlex Trainer Batch view.
 *
 * Mirrors the backend contract in
 * `label_studio/tasks/api_batch.py::_build_mock_batch`. Single source of
 * truth on the frontend so the tile grid + earnings ticker + completion
 * modal agree without duck-typing.
 *
 * Phase 1 Step 1.4-E.
 */

/** Each task row returned by GET /api/v1/trainer/batch. */
export interface BatchTask {
  /** Backend task id — used as the React key and the open-task deep link. */
  task_id: number;
  /** Project the task belongs to. */
  project_id: number;
  /** Coarse task-type slug (e.g. "image_classification"). */
  task_type: string;
  /** Short prompt preview rendered on the tile. */
  preview: string;
  /** Earnings credit on completion, in whole INR (no paise). */
  earnings_inr: number;
  /** Median time to complete, minutes. Drives the "X min remaining" hint. */
  estimated_min: number;
  /** Tier badge: bronze | silver | gold. */
  tier: BatchTier;
  /** Lifecycle state. */
  status: BatchStatus;
}

export type BatchTier = "bronze" | "silver" | "gold";

export type BatchStatus = "pending" | "in_progress" | "done";
