/**
 * Shared types for the TrainPlex Admin Payment Status table.
 *
 * Mirrors the backend contract in
 * `label_studio/payments/api.py::AdminPaymentStatusAPI` +
 * `AdminPayoutQueueAPI`.
 *
 * Phase 1 Step 6.4 + 4.2-5. Keep this file in lockstep with the backend
 * response shape.
 */

/** Payment hold status values accepted by the backend filter. */
export type PaymentHoldStatus = "held" | "released" | "disputed" | "refunded";

/** Payout queue entry status values. */
export type PayoutQueueStatus =
  | "pending"
  | "processing"
  | "sent"
  | "failed";

/** One hold row on the admin payment-status table. */
export interface PaymentStatusRow {
  id: number;
  task_id: number;
  trainer_id: number;
  /** Decimal string like "150.00" — frontend never re-formats. */
  amount_inr: string;
  status: PaymentHoldStatus;
  /** ISO-8601 UTC. */
  held_at: string;
  released_at: string | null;
  consensus_result_id: number | null;
  payout_queue_id: number | null;
}

/** Summary counts per status — header band on the table. */
export interface PaymentStatusSummary {
  held: number;
  released: number;
  disputed: number;
  refunded: number;
}

/** Response shape of GET /api/v1/admin/payment-status. */
export interface PaymentStatusResponse {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  summary: PaymentStatusSummary;
  results: PaymentStatusRow[];
}

/** Query params the table sends to the endpoint. */
export interface PaymentStatusQuery {
  status?: PaymentHoldStatus | "all" | "";
  trainer_id?: number | "";
  task_id?: number | "";
  page?: number;
  page_size?: number;
}

/** One PayoutQueue row in the drawer. */
export interface PayoutQueueRow {
  id: number;
  trainer_id: number;
  amount_inr: string;
  status: PayoutQueueStatus;
  razorpay_payout_id: string;
  retry_count: number;
  last_error: string;
  created_at: string;
  sent_at: string | null;
}

/** Response shape of GET /api/v1/payments/payout-queue. */
export interface PayoutQueueResponse {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  results: PayoutQueueRow[];
}

/** Status options for the table filter dropdown. */
export const HOLD_STATUS_CHOICES: ReadonlyArray<{
  value: PaymentHoldStatus | "";
  labelKey: string;
}> = [
  { value: "", labelKey: "common.all" },
  { value: "held", labelKey: "admin.payments.status_held" },
  { value: "released", labelKey: "admin.payments.status_released" },
  { value: "disputed", labelKey: "admin.payments.status_disputed" },
  { value: "refunded", labelKey: "admin.payments.status_refunded" },
] as const;
