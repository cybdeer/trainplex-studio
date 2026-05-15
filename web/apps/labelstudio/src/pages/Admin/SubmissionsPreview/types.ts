/**
 * Shared types for the TrainPlex Admin Submissions Preview drawer.
 *
 * Mirrors the backend contract in
 * `label_studio/core/views_submissions_preview.py`.
 *
 * Phase 1 Step 4.2-9. Keep this file in lockstep with the backend response.
 */

/** Submission status values accepted by the backend filter. */
export type SubmissionStatus =
  | "submitted"
  | "under_review"
  | "approved"
  | "rejected";

/** Slim trainer profile shipped on every submission row. */
export interface SubmissionTrainer {
  id: number;
  name: string;
  role: string;
}

/**
 * Single reviewer's verdict on a submission.
 *
 * For the dashboard's 3-dot consensus visualisation we always send 3
 * entries — even when one reviewer hasn't scored yet, the backend
 * pre-fills with score=0 / agreed=false so the dots render deterministically.
 */
export interface ReviewerScore {
  reviewer_id: number;
  /** 0 or 1 — used for visual dot fill. */
  score: 0 | 1;
  /** Mirrors score, but typed as a bool for readability in i18n labels. */
  agreed: boolean;
}

/** One submission preview row from the endpoint. */
export interface SubmissionPreview {
  id: number;
  project_id: number;
  trainer: SubmissionTrainer;
  /** ≤ 200 chars. May be a thumbnail URL (starts with `http(s)://`) or a
   *  truncated text snippet — frontend should sniff and render accordingly. */
  task_preview: string;
  /** ≤ 200 chars truncated text snippet of the trainer's answer. */
  answer_preview: string;
  /** Always exactly 3 entries — pad with score=0 reviewers backend-side. */
  reviewer_scores: ReviewerScore[];
  /** ISO-8601 UTC, ends in `Z`. */
  created_at: string;
  status: SubmissionStatus;
}

/** Echo of which filters the backend actually applied (empties omitted). */
export interface SubmissionsPreviewFilters {
  project_id?: number;
  trainer_id?: number;
  status?: SubmissionStatus;
}

/** Response shape of GET /api/v1/admin/submissions/preview. */
export interface SubmissionsPreviewResponse {
  /** ISO-8601 UTC, ends in `Z`. */
  as_of: string;
  /** Effective limit (after the 50-cap is applied). */
  limit: number;
  filters: SubmissionsPreviewFilters;
  submissions: SubmissionPreview[];
}

/**
 * Query params the React drawer sends to the endpoint.
 * Each field is optional — omitted = "don't filter on this column".
 */
export interface SubmissionsPreviewQuery {
  limit?: number;
  project_id?: number | "";
  trainer_id?: number | "";
  status?: SubmissionStatus | "";
}

/** Choices shown in the status dropdown (drawer header). */
export const SUBMISSION_STATUS_CHOICES: ReadonlyArray<{
  value: SubmissionStatus | "";
  labelKey: string;
}> = [
  { value: "", labelKey: "common.all" },
  { value: "submitted", labelKey: "admin.submissions.status_submitted" },
  { value: "under_review", labelKey: "admin.submissions.status_under_review" },
  { value: "approved", labelKey: "admin.submissions.status_approved" },
  { value: "rejected", labelKey: "admin.submissions.status_rejected" },
] as const;
