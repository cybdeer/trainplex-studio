/**
 * Shared types for the TrainPlex Trainer Wallet page.
 *
 * Mirrors `label_studio/payments/api.py::TrainerWalletAPI`.
 * Phase 1 Step 6.4. Keep in lockstep with the backend response.
 */

/** Wallet transaction kind. */
export type WalletTxnType = "hold" | "release" | "payout" | "refund";

/** One wallet ledger row in the trainer wallet response. */
export interface WalletTxnRow {
  id: number;
  txn_type: WalletTxnType;
  /** Decimal string, e.g. "150.00". Frontend never re-formats. */
  amount_inr: string;
  balance_after_inr: string;
  description: string;
  related_task_id: number | null;
  related_payout_id: number | null;
  /** ISO-8601 UTC. */
  created_at: string;
}

/** Response shape of GET /api/v1/payments/wallet. */
export interface WalletResponse {
  balance_inr: string;
  held_inr: string;
  this_month_inr: string;
  transactions: WalletTxnRow[];
  transaction_limit: number;
}
