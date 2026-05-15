/**
 * Reviewer-side type contracts — TrainPlex Phase 1 Step 6.
 *
 * Mirrors the shape returned by the peer_review backend endpoints. Kept in
 * one file so the dashboard, queue and review form can import from a single
 * source of truth.
 */

export type ReviewerAssignmentStatus =
  | "pending"
  | "in_progress"
  | "done"
  | "expired";

export type ReviewAgreement = "agree" | "partial" | "disagree" | "dispute";

export interface ReviewerAssignmentRow {
  id: number;
  task_id: number;
  /** Blind review — only the integer id is surfaced. Never email / name. */
  trainer_id: number | null;
  assigned_at: string;
  deadline_at: string;
  status: ReviewerAssignmentStatus;
}

export interface ReviewerQueueResponse {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  results: ReviewerAssignmentRow[];
}

export interface ConsensusSummary {
  task_id: number;
  status: "approved" | "flagged" | "dispute" | "rejected" | string;
  agreed_count: number;
  disagree_count: number;
  partial_count: number;
  total_reviewers: number;
}

export interface SubmitReviewResponse {
  ok: boolean;
  review?: {
    id: number;
    review_assignment_id: number;
    score: number;
    agreement: ReviewAgreement;
    comment: string;
    category_checks: Record<string, boolean>;
    submitted_at: string;
  };
  consensus?: ConsensusSummary;
  error?: string;
}
