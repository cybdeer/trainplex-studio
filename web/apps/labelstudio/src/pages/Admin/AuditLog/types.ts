/**
 * Shared types for the TrainPlex Admin Audit Log viewer.
 *
 * Mirrors the backend contract from
 * `label_studio/core/views_audit.py::AdminAuditLogAPI`.
 * Phase 1 Step 4.2-4. Keep this file in lockstep with the backend response.
 */

export interface AuditActor {
  id: number | null;
  email: string;
  role: string;
}

export interface AuditRow {
  id: number;
  action: string;
  actor: AuditActor | null;
  target_type: string;
  target_id: string;
  ip_address: string | null;
  /** Already truncated to ~80 chars by the backend; ellipsis = truncated. */
  user_agent: string;
  success: boolean;
  metadata: Record<string, unknown>;
  /** ISO-8601 UTC, ends in `Z`. */
  created_at: string;
}

export interface AuditLogResponse {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  results: AuditRow[];
}

/**
 * Query params the React filter bar sends to `/api/v1/admin/audit/log`.
 * Each field is optional — omitted fields mean "don't filter on this column".
 */
export interface AuditFilters {
  action?: string;
  actor_email?: string;
  target_type?: string;
  /** `''` = either, `'true'` = success only, `'false'` = failed only. */
  success?: '' | 'true' | 'false';
  /** ISO date `YYYY-MM-DD`. */
  start_date?: string;
  /** ISO date `YYYY-MM-DD`. */
  end_date?: string;
  page?: number;
  page_size?: number;
}

/**
 * Choices shown in the action dropdown. Mirror of `AuditLog.ACTION_CHOICES`
 * (label_studio/users/models.py). Keep in sync when the backend taxonomy
 * grows in Phase 2.
 */
export const AUDIT_ACTION_CHOICES: ReadonlyArray<{ value: string; labelKey: string }> = [
  { value: '', labelKey: 'common.all' },
  { value: 'login_success', labelKey: 'admin.audit.action_login_success' },
  { value: 'login_fail', labelKey: 'admin.audit.action_login_fail' },
  { value: 'permission_change', labelKey: 'admin.audit.action_permission_change' },
  { value: 'delete', labelKey: 'admin.audit.action_delete' },
  { value: 'admin_action', labelKey: 'admin.audit.action_admin_action' },
] as const;

/**
 * Target-type dropdown. Only the values the Step 12.3 hooks actually emit.
 */
export const AUDIT_TARGET_TYPE_CHOICES: ReadonlyArray<{ value: string; label: string }> = [
  { value: '', label: '' },
  { value: 'User', label: 'User' },
  { value: 'Project', label: 'Project' },
  { value: 'Annotation', label: 'Annotation' },
  { value: 'Task', label: 'Task' },
] as const;
