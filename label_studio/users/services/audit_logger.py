"""Audit-log service (Phase 1 Step 12.3).

High-level helpers for writing rows into ``users.AuditLog``. Use these
instead of calling ``AuditLog.objects.create`` directly — they:

- Apply consistent field naming for ``target_type`` / ``target_id``.
- Coerce ``target_id`` to ``str`` so UUID + int PKs both fit.
- Truncate ``user_agent`` to 1 KB so a malicious header can't bloat the table.
- Swallow any DB error so audit-log writes never break the caller flow.

All writes are best-effort. If the audit table is unreachable (e.g. the
table doesn't exist yet during a fresh migration), the helper logs a
warning and returns ``None`` rather than re-raising.
"""

import logging
from typing import Any, Optional

from users.models import AuditLog

logger = logging.getLogger(__name__)

# Cap user-agent storage to prevent log bloat from pathological UAs.
_UA_MAX_LEN = 1024


def _safe_create(**fields) -> Optional[AuditLog]:
    """Wrap ``AuditLog.objects.create`` so a DB failure never propagates."""
    try:
        return AuditLog.objects.create(**fields)
    except Exception:  # noqa: BLE001  (intentional — audit must not break callers)
        logger.exception('Failed to write AuditLog row (action=%s)', fields.get('action'))
        return None


def _normalize_ua(ua: Optional[str]) -> str:
    if not ua:
        return ''
    return ua[:_UA_MAX_LEN]


def log_login(user, ip: Optional[str], ua: Optional[str], success: bool) -> Optional[AuditLog]:
    """Record a login attempt.

    Args:
        user: ``User`` instance for a successful login, OR ``None`` /
              an unsaved stub for a failed login where the email didn't
              match a known account.
        ip: Client IP address, or ``None`` if unknown.
        ua: ``User-Agent`` header value, or ``None``.
        success: ``True`` for success, ``False`` for failure.
    """
    action = AuditLog.ACTION_LOGIN_SUCCESS if success else AuditLog.ACTION_LOGIN_FAIL
    return _safe_create(
        user=user if (user and getattr(user, 'pk', None)) else None,
        action=action,
        target_type='User',
        target_id=str(user.pk) if (user and getattr(user, 'pk', None)) else '',
        ip_address=ip,
        user_agent=_normalize_ua(ua),
        success=success,
        metadata={},
    )


def log_permission_change(
    actor,
    target,
    old_role: str,
    new_role: str,
    ip: Optional[str] = None,
) -> Optional[AuditLog]:
    """Record an RBAC role change on ``target`` performed by ``actor``."""
    return _safe_create(
        user=actor if (actor and getattr(actor, 'pk', None)) else None,
        action=AuditLog.ACTION_PERMISSION_CHANGE,
        target_type='User',
        target_id=str(target.pk) if (target and getattr(target, 'pk', None)) else '',
        ip_address=ip,
        success=True,
        metadata={
            'old_role': old_role,
            'new_role': new_role,
            'target_email': getattr(target, 'email', '') if target else '',
        },
    )


def log_delete(
    actor,
    target_type: str,
    target_id: Any,
    ip: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional[AuditLog]:
    """Record a destructive delete of a domain object."""
    return _safe_create(
        user=actor if (actor and getattr(actor, 'pk', None)) else None,
        action=AuditLog.ACTION_DELETE,
        target_type=target_type or '',
        target_id=str(target_id) if target_id is not None else '',
        ip_address=ip,
        success=True,
        metadata=metadata or {},
    )


def log_admin_action(
    actor,
    action_name: str,
    metadata: Optional[dict] = None,
    ip: Optional[str] = None,
) -> Optional[AuditLog]:
    """Record a generic admin action (data export, settings change, etc.).

    ``action_name`` is stored inside ``metadata['action_name']`` so the
    coarse ``AuditLog.action`` column stays drawable in a single index.
    """
    enriched = dict(metadata or {})
    enriched['action_name'] = action_name
    return _safe_create(
        user=actor if (actor and getattr(actor, 'pk', None)) else None,
        action=AuditLog.ACTION_ADMIN_ACTION,
        target_type='',
        target_id='',
        ip_address=ip,
        success=True,
        metadata=enriched,
    )


__all__ = [
    'log_login',
    'log_permission_change',
    'log_delete',
    'log_admin_action',
]
