/**
 * QA-lead-side type contracts — TrainPlex Phase 1 Step 6.
 *
 * Mirrors the GET /api/v1/qa/disputes response + POST resolve body.
 */

export type DisputeResolution =
  | "trainer_correct"
  | "reviewer_correct"
  | "ml_recheck"
  | "inconclusive";

export type ConsensusStatusWire =
  | "approved"
  | "flagged"
  | "dispute"
  | "rejected";

export interface DisputeRow {
  id: number;
  consensus_result_id: number;
  task_id: number;
  escalated_at: string;
  consensus_status: ConsensusStatusWire;
  agreed_count: number;
  disagree_count: number;
  partial_count: number;
  total_reviewers: number;
  fallback_used: boolean;
  qa_lead_id: number | null;
  qa_decision: string;
  qa_notes: string;
  resolved_at: string | null;
  resolution: DisputeResolution | "";
}

export interface DisputeListResponse {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  results: DisputeRow[];
}

export interface DisputeResolveBody {
  resolution: DisputeResolution;
  qa_notes: string;
  qa_decision?: string;
}
