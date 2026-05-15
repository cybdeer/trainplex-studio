/**
 * Shared types for the TrainPlex Admin Quality Alert Center.
 *
 * Mirrors the backend contract in `label_studio/core/views_alerts.py`.
 * Single source of truth on the frontend so the table / filter / drawer
 * components agree on shapes without duck-typing.
 *
 * Phase 1 Step 4.2-8.
 */

/** Trigger enum (mirrored from `QualityAlert.TRIGGER_CHOICES`). */
export type AlertTriggerType =
  | "reviewer_disagree"
  | "time_anomaly"
  | "duplicate_pattern"
  | "reviewer_conflict"
  | "cert_failed";

/** Severity bucket (mirrored from `QualityAlert.SEVERITY_CHOICES`). */
export type AlertSeverity = "low" | "medium" | "high" | "critical";

/** Status (mirrored from `QualityAlert.STATUS_CHOICES`). */
export type AlertStatus = "open" | "reviewed" | "dismissed" | "action_taken";

/** Resolution values accepted by `POST /<id>/review`. ``open`` is excluded
 * on purpose — re-opening a resolved alert is not a Phase 1 feature. */
export type AlertResolution = Exclude<AlertStatus, "open">;

/** Trainer / reviewer slim profile shipped on alert rows. */
export interface AlertActor {
  id: number | null;
  email: string;
  role?: string;
}

/** One alert row from the list endpoint. */
export interface AlertRow {
  id: number;
  trigger_type: AlertTriggerType;
  severity: AlertSeverity;
  status: AlertStatus;
  trainer: AlertActor | null;
  submission_id: number | null;
  details: Record<string, unknown>;
  reviewed_by: AlertActor | null;
  /** ISO-8601 UTC, ends in `Z`. ``null`` until resolved. */
  reviewed_at: string | null;
  resolution_notes: string;
  /** ISO-8601 UTC, ends in `Z`. */
  created_at: string;
}

/** Response shape of GET /api/v1/admin/quality-alerts. */
export interface AlertsListResponse {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  results: AlertRow[];
}

/** Response shape of GET /api/v1/admin/quality-alerts/stats. */
export interface AlertsStatsResponse {
  open: Record<AlertSeverity, number>;
  total_open: number;
}

/**
 * Query params the React filter bar sends to the list endpoint.
 * Each field is optional — omitted = "don't filter on this column".
 */
export interface AlertFilters {
  status?: AlertStatus | "";
  severity?: AlertSeverity | "";
  trigger_type?: AlertTriggerType | "";
  trainer_id?: number | "";
  page?: number;
  page_size?: number;
}

/** Choices shown in the trigger dropdown. */
export const ALERT_TRIGGER_CHOICES: ReadonlyArray<{
  value: AlertTriggerType | "";
  labelKey: string;
}> = [
  { value: "", labelKey: "common.all" },
  { value: "reviewer_disagree", labelKey: "admin.alerts.trigger_disagree" },
  { value: "time_anomaly", labelKey: "admin.alerts.trigger_time" },
  { value: "duplicate_pattern", labelKey: "admin.alerts.trigger_duplicate" },
  { value: "reviewer_conflict", labelKey: "admin.alerts.trigger_disagree" },
  { value: "cert_failed", labelKey: "admin.alerts.trigger_duplicate" },
] as const;

/** Choices shown in the severity dropdown. */
export const ALERT_SEVERITY_CHOICES: ReadonlyArray<{
  value: AlertSeverity | "";
  labelKey: string;
}> = [
  { value: "", labelKey: "common.all" },
  { value: "low", labelKey: "admin.alerts.severity_low" },
  { value: "medium", labelKey: "admin.alerts.severity_medium" },
  { value: "high", labelKey: "admin.alerts.severity_high" },
  { value: "critical", labelKey: "admin.alerts.severity_critical" },
] as const;

/** Choices shown in the status dropdown. */
export const ALERT_STATUS_CHOICES: ReadonlyArray<{
  value: AlertStatus | "";
  labelKey: string;
}> = [
  { value: "", labelKey: "common.all" },
  { value: "open", labelKey: "admin.alerts.status_open" },
  { value: "reviewed", labelKey: "admin.alerts.status_reviewed" },
  { value: "dismissed", labelKey: "admin.alerts.status_dismissed" },
  { value: "action_taken", labelKey: "admin.alerts.status_action" },
] as const;

/** Choices shown in the resolve dropdown on the detail drawer. */
export const ALERT_RESOLUTION_CHOICES: ReadonlyArray<{
  value: AlertResolution;
  labelKey: string;
}> = [
  { value: "reviewed", labelKey: "admin.alerts.status_reviewed" },
  { value: "dismissed", labelKey: "admin.alerts.status_dismissed" },
  { value: "action_taken", labelKey: "admin.alerts.status_action" },
] as const;
