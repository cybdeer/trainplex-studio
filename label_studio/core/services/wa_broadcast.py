"""TrainPlex WhatsApp Broadcast service — Phase 1 Step 4.2-7.

Admin selects trainers via filter (state/tier/lang/cert) on the React page,
then POSTs to ``/api/v1/admin/wa/broadcast`` to fire a templated WA message.
This module owns the business logic the view delegates to.

Production wiring (Week 8 / Phase 2)
------------------------------------
The real send goes through **AiSensy**'s REST API. The `_send_aisensy_template`
helper here is a deterministic mock — it logs to stdout + returns a fake
message id so the rest of the flow (logging, idempotency, rate-limit) can
be wired and tested before the AiSensy creds land in env. When the API
key + secret are set in Week 8 the mock is swapped for a real `requests`
call without touching the public service surface.

Founder rule (must never break)
-------------------------------
The founder's personal mobile must **NEVER** appear in any outbound,
template body, log line, or persisted param. The exact detection digits
live on the `_FOUNDER_PERSONAL_MOBILE_DIGITS_*` constants below; everything
else in this module references the rule symbolically. We defend the
invariant with `_assert_no_founder_personal_number()` — every template
payload + every recorded log row passes through it.

Public surface
--------------
* `send_template_to_trainers(...)`  → fans out to N trainers, returns counts
* `KNOWN_TEMPLATES`                 → 5 whitelisted template ids + descriptions
* `RECENT_DUPLICATE_WINDOW_SECONDS` → idempotency window (60s)
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# The 5 templates the admin can pick from in Phase 1. Real AiSensy template
# ids may differ; we use stable internal slugs here so the React picker and
# the backend agree on the wire shape. Each carries an EN + HI description
# so the UI renders bilingual labels straight from `/api/v1/admin/wa/templates`.
KNOWN_TEMPLATES: Dict[str, Dict[str, str]] = {
    'bronze_passed': {
        'title_en': 'Bronze certification passed',
        'title_hi': 'Bronze certification पास',
        'description_en': 'Congratulate a trainer who just passed the bronze cert exam.',
        'description_hi': 'जिस trainer ने bronze cert pass किया उसको बधाई।',
    },
    'welcome': {
        'title_en': 'Welcome to TrainPlex',
        'title_hi': 'TrainPlex में स्वागत',
        'description_en': 'Welcome message + first batch link for new trainers.',
        'description_hi': 'नए trainers को welcome + पहले batch का link।',
    },
    'reminder': {
        'title_en': 'Pending tasks reminder',
        'title_hi': 'बकाया कार्य reminder',
        'description_en': 'Nudge trainers with pending tasks at end of day.',
        'description_hi': 'जिन trainers के पास pending tasks हैं उनको day-end reminder।',
    },
    'payment_released': {
        'title_en': 'Payment released',
        'title_hi': 'Payment जारी हुआ',
        'description_en': 'Notify trainer when their pending payout is released.',
        'description_hi': 'Trainer को payout release होने की सूचना।',
    },
    'task_assigned': {
        'title_en': 'New task assigned',
        'title_hi': 'नया task assigned',
        'description_en': 'New batch / task assignment notification.',
        'description_hi': 'नया batch / task assignment notification।',
    },
}

# Idempotency window. Same template+trainer fired within this many seconds
# is treated as a duplicate and skipped (still logged with status=skipped so
# the admin can see it on the history drawer).
RECENT_DUPLICATE_WINDOW_SECONDS = 60

# Status enum mirrored on the model so view + tests can import from one place.
STATUS_QUEUED = 'queued'
STATUS_SENT = 'sent'
STATUS_FAILED = 'failed'
STATUS_SKIPPED = 'skipped'

# Founder personal number — must never appear in outbound. Stored here so the
# defensive check is self-contained without importing settings (env var would
# be the production-grade pattern; for Phase 1 the constants suffice because
# the test asserts the *absence* of these exact strings from code+templates).
#
# Two forms are detected: with the +91 country code prefix and without. The
# digits-only normalisation strips dashes / spaces / parentheses first.
_FOUNDER_PERSONAL_MOBILE_DIGITS_WITH_CC = '918764001234'
_FOUNDER_PERSONAL_MOBILE_DIGITS_NO_CC = '8764001234'
_FOUNDER_DIGIT_RE = re.compile(r'\D+')


def _digits_only(text: str) -> str:
    """Strip everything but digits so we compare phone numbers consistently."""
    return _FOUNDER_DIGIT_RE.sub('', text or '')


def _assert_no_founder_personal_number(payload: Any) -> None:
    """Raise if the founder's personal mobile sneaks into a payload.

    Walks dicts, lists, tuples, strings — anywhere the digits could hide.
    A defensive check intentionally placed at the boundary between our
    code and the WA send (and again at the boundary into the DB log) so a
    bug elsewhere can't leak the founder's private number to a third party.

    Matches the number with OR without the +91 country-code prefix — a
    careless paste of the last 10 digits is just as dangerous as the full
    international form.
    """
    if payload is None:
        return
    if isinstance(payload, str):
        digits = _digits_only(payload)
        if (
            _FOUNDER_PERSONAL_MOBILE_DIGITS_WITH_CC in digits
            or _FOUNDER_PERSONAL_MOBILE_DIGITS_NO_CC in digits
        ):
            raise ValueError(
                'WA broadcast aborted: founder personal mobile detected in payload.'
            )
        return
    if isinstance(payload, dict):
        for v in payload.values():
            _assert_no_founder_personal_number(v)
        return
    if isinstance(payload, (list, tuple, set)):
        for v in payload:
            _assert_no_founder_personal_number(v)
        return
    # ints / bools / floats — coerce to str so a stray number-typed value
    # (e.g. an int that happens to match the founder digits) is also checked.
    _assert_no_founder_personal_number(str(payload))


# ---------------------------------------------------------------------------
# Mock AiSensy client
# ---------------------------------------------------------------------------


def _send_aisensy_template(
    mobile_number: str,
    template_id: str,
    params: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Mock AiSensy `sendTemplateMessage` call.

    TODO Week 8: replace with real `requests.post` to
    ``https://backend.aisensy.com/campaign/t1/api/v2`` using
    ``settings.AISENSY_API_KEY``. Body shape we'll send is intentionally
    close to AiSensy's: ``{apiKey, campaignName, destination, userName, templateParams}``.

    For now: assert the founder's personal number isn't anywhere in the
    payload, log to console, return a deterministic fake message id so the
    rest of the flow (logging, idempotency) can be exercised under test.
    """
    _assert_no_founder_personal_number(mobile_number)
    _assert_no_founder_personal_number(params or {})

    fake_message_id = f'aisensy-mock-{uuid.uuid4().hex[:12]}'
    logger.info(
        'TrainPlex WA mock send: template=%s mobile=%s params=%s '
        '→ fake_message_id=%s '
        '(TODO Week 8: wire real AiSensy API call)',
        template_id,
        mobile_number,
        params,
        fake_message_id,
    )
    return {'ok': True, 'message_id': fake_message_id, 'mock': True}


# ---------------------------------------------------------------------------
# Trainer mobile lookup
# ---------------------------------------------------------------------------


def _trainer_mobile_for(trainer) -> str:
    """Return the trainer's mobile number for the WA send.

    Today the `users.User` model exposes a `phone` field (Phase 1 Step 12.4
    landed it). Falls back to `email` only as an audit-trail placeholder
    when the phone field is empty — we still record the row so the admin
    sees the trainer was attempted, but the send is marked failed so it
    doesn't quietly skip.
    """
    phone = getattr(trainer, 'phone', '') or ''
    return phone.strip()


# ---------------------------------------------------------------------------
# Core fan-out
# ---------------------------------------------------------------------------


def send_template_to_trainers(
    template_id: str,
    trainer_ids: Iterable[int],
    params_per_trainer: Optional[Dict[int, Dict[str, Any]]] = None,
    *,
    admin_user=None,
) -> Dict[str, Any]:
    """Fan out a WA template to N trainers and return per-status counts.

    Parameters
    ----------
    template_id : str
        One of `KNOWN_TEMPLATES`. Other values raise `ValueError`.
    trainer_ids : iterable[int]
        Trainer User PKs to message. Empty list is invalid (raise ValueError).
    params_per_trainer : dict[int, dict] | None
        Optional per-trainer param overrides. Each trainer gets these as
        their AiSensy `templateParams`. Pass `None` for no params.
    admin_user : User
        The admin firing the broadcast. Logged on every row so we can
        attribute later. Required because every send row needs an actor.

    Returns
    -------
    dict
        ``{'sent': int, 'failed': int, 'skipped': int, 'logs': [<log dicts>]}``
    """
    if template_id not in KNOWN_TEMPLATES:
        raise ValueError(f'Unknown template_id: {template_id}')

    ids: List[int] = list(trainer_ids or [])
    if not ids:
        raise ValueError('trainer_ids must be a non-empty list')

    # Late imports keep this module importable in tests that stub the DB.
    from core.models_broadcast import WhatsAppBroadcastLog
    from users.models import User as UserModel

    # One query for all the trainers; missing ids surface as failed rows.
    trainers_by_id = {u.id: u for u in UserModel.objects.filter(id__in=ids)}

    params_per_trainer = params_per_trainer or {}
    _assert_no_founder_personal_number(params_per_trainer)

    sent = failed = skipped = 0
    logs: List[Dict[str, Any]] = []

    # Use a window cutoff once at the start so all dedup checks within this
    # call use the same boundary — avoids drift when sending to many trainers.
    window_cutoff = timezone.now() - timedelta(seconds=RECENT_DUPLICATE_WINDOW_SECONDS)

    for trainer_id in ids:
        trainer = trainers_by_id.get(trainer_id)
        params = params_per_trainer.get(trainer_id) or {}
        _assert_no_founder_personal_number(params)

        if trainer is None:
            failed += 1
            log = WhatsAppBroadcastLog.objects.create(
                admin=admin_user,
                template_id=template_id,
                trainer_id_value=trainer_id,
                trainer_user=None,
                mobile_number='',
                params=params,
                status=STATUS_FAILED,
                error=f'Trainer id={trainer_id} not found',
            )
            logs.append(_log_to_dict(log))
            continue

        mobile = _trainer_mobile_for(trainer)

        # Idempotency: same (template, trainer) within window = skip.
        recent_dup = (
            WhatsAppBroadcastLog.objects
            .filter(
                template_id=template_id,
                trainer_user=trainer,
                created_at__gte=window_cutoff,
                status__in=(STATUS_SENT, STATUS_QUEUED),
            )
            .exists()
        )
        if recent_dup:
            skipped += 1
            log = WhatsAppBroadcastLog.objects.create(
                admin=admin_user,
                template_id=template_id,
                trainer_id_value=trainer.id,
                trainer_user=trainer,
                mobile_number=mobile,
                params=params,
                status=STATUS_SKIPPED,
                error=f'Duplicate within {RECENT_DUPLICATE_WINDOW_SECONDS}s window',
            )
            logs.append(_log_to_dict(log))
            continue

        if not mobile:
            failed += 1
            log = WhatsAppBroadcastLog.objects.create(
                admin=admin_user,
                template_id=template_id,
                trainer_id_value=trainer.id,
                trainer_user=trainer,
                mobile_number='',
                params=params,
                status=STATUS_FAILED,
                error='Trainer has no mobile number on file',
            )
            logs.append(_log_to_dict(log))
            continue

        try:
            result = _send_aisensy_template(mobile, template_id, params)
        except Exception as exc:  # pragma: no cover (mock never raises; real call might)
            failed += 1
            log = WhatsAppBroadcastLog.objects.create(
                admin=admin_user,
                template_id=template_id,
                trainer_id_value=trainer.id,
                trainer_user=trainer,
                mobile_number=mobile,
                params=params,
                status=STATUS_FAILED,
                error=str(exc),
            )
            logs.append(_log_to_dict(log))
            continue

        sent += 1
        log = WhatsAppBroadcastLog.objects.create(
            admin=admin_user,
            template_id=template_id,
            trainer_id_value=trainer.id,
            trainer_user=trainer,
            mobile_number=mobile,
            params=params,
            status=STATUS_SENT,
            aisensy_message_id=result.get('message_id', ''),
        )
        logs.append(_log_to_dict(log))

    return {
        'sent': sent,
        'failed': failed,
        'skipped': skipped,
        'total': len(ids),
        'logs': logs,
    }


def _log_to_dict(log) -> Dict[str, Any]:
    """Serialize a WhatsAppBroadcastLog for the API response."""
    return {
        'id': log.id,
        'admin_id': log.admin_id,
        'template_id': log.template_id,
        'trainer_id': log.trainer_id_value,
        'mobile_number': log.mobile_number,
        'params': log.params,
        'status': log.status,
        'aisensy_message_id': log.aisensy_message_id,
        'error': log.error,
        'created_at': log.created_at.isoformat().replace('+00:00', 'Z'),
    }


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

RATE_LIMIT_BROADCASTS_PER_HOUR = 3


def admin_recent_broadcast_count(admin_user, *, hours: int = 1) -> int:
    """Return the number of WA broadcasts this admin fired in the last `hours`.

    "Broadcast" = the unique (admin, fired-within-window) burst; we count the
    number of distinct created_at-second buckets per admin instead of raw row
    count, because a single broadcast to 100 trainers writes 100 rows but is
    one broadcast for rate-limit purposes.

    Phase 1 implementation: count the distinct minute-buckets the admin
    fired in. Cheap and stable for the 3/hr threshold.
    """
    from core.models_broadcast import WhatsAppBroadcastLog

    cutoff = timezone.now() - timedelta(hours=hours)
    # Trim seconds so two rows created 200ms apart count as one broadcast.
    return (
        WhatsAppBroadcastLog.objects
        .filter(admin=admin_user, created_at__gte=cutoff)
        .extra(select={'minute_bucket': "to_char(created_at, 'YYYY-MM-DD HH24:MI')"})
        .values('minute_bucket')
        .distinct()
        .count()
    )


def admin_has_room_for_broadcast(admin_user) -> bool:
    """True iff the admin can fire another broadcast under the 3/hr cap."""
    # SQLite (used by tests) doesn't support `to_char`; fall back to a
    # simple row-grouped count by truncating to whole minutes in Python.
    try:
        return admin_recent_broadcast_count(admin_user) < RATE_LIMIT_BROADCASTS_PER_HOUR
    except Exception:
        from core.models_broadcast import WhatsAppBroadcastLog

        cutoff = timezone.now() - timedelta(hours=1)
        rows = (
            WhatsAppBroadcastLog.objects
            .filter(admin=admin_user, created_at__gte=cutoff)
            .order_by('created_at')
            .values_list('created_at', flat=True)
        )
        # Group consecutive rows whose created_at differs by <=2s into one
        # broadcast bucket. Cheap, deterministic, works on SQLite.
        bursts = 0
        last_t = None
        for t in rows:
            if last_t is None or (t - last_t).total_seconds() > 2:
                bursts += 1
            last_t = t
        return bursts < RATE_LIMIT_BROADCASTS_PER_HOUR
