/**
 * Shared types for the TrainPlex Admin WhatsApp Broadcast page.
 *
 * Mirrors the backend contract in `label_studio/core/views_broadcast.py`.
 * Single source of truth on the frontend so the picker / selector / preview
 * components agree on shapes without duck-typing.
 *
 * Phase 1 Step 4.2-7.
 */

/** Status values mirrored from `core.models_broadcast.WhatsAppBroadcastLog`. */
export type WaBroadcastStatus = "queued" | "sent" | "failed" | "skipped";

/** One template card the admin can pick from. */
export interface WaTemplate {
  id: string;
  title_en: string;
  title_hi: string;
  description_en: string;
  description_hi: string;
}

/** Response shape of GET /api/v1/admin/wa/templates. */
export interface WaTemplateList {
  count: number;
  items: WaTemplate[];
}

/** One row from a fan-out send. */
export interface WaBroadcastLogRow {
  id: number;
  admin_id: number | null;
  admin_email?: string | null;
  template_id: string;
  trainer_id: number;
  trainer_email?: string | null;
  mobile_number: string;
  status: WaBroadcastStatus;
  aisensy_message_id: string;
  error: string;
  params: Record<string, unknown>;
  created_at: string;
}

/** Response shape of POST /api/v1/admin/wa/broadcast. */
export interface WaBroadcastResponse {
  ok: boolean;
  template_id: string;
  counts: {
    sent: number;
    failed: number;
    skipped: number;
    total: number;
  };
  logs: WaBroadcastLogRow[];
}

/** Response shape of GET /api/v1/admin/wa/broadcast/history. */
export interface WaHistoryResponse {
  count: number;
  items: WaBroadcastLogRow[];
}
