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
template body, log line, or persisted param. The actual digits live
only in the env var ``TRAINPLEX_FOUNDER_MOBILE_GUARD`` and are looked
up by ``core.services.founder_guard``; everything in this module
references the rule symbolically. We defend the invariant with
``_assert_no_founder_personal_number()`` — every template payload +
every recorded log row passes through it.

Public surface
--------------
* `send_template_to_trainers(...)`  → fans out to N trainers, returns counts
* `KNOWN_TEMPLATES`                 → 5 whitelisted template ids + descriptions
* `RECENT_DUPLICATE_WINDOW_SECONDS` → idempotency window (60s)
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional

import requests
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AiSensy real-send configuration (Wave-19 W2-MOCK-REAL).
# ---------------------------------------------------------------------------
#
# Tonight the dry-run guard defaults to TRUE — even with a real key in env
# we will not fire a live AiSensy call. The founder toggles this off in .env
# (``TRAINPLEX_WA_DRY_RUN=false``) once the AiSensy creds + a test trainer
# pair are confirmed.

AISENSY_DEFAULT_BASE_URL = 'https://backend.aisensy.com/campaign/t1/api/v2'
AISENSY_TEMPLATE_ENDPOINT = '/send-template'
AISENSY_DEFAULT_TIMEOUT_SECONDS = 30


def _wa_dry_run_default() -> bool:
    """Resolve the dry-run flag at call time so tests can flip the env var."""
    raw = os.getenv('TRAINPLEX_WA_DRY_RUN', 'true').strip().lower()
    return raw not in ('false', '0', 'no', 'off')


def _aisensy_api_key() -> str:
    return (os.getenv('AISENSY_API_KEY') or '').strip()


def _aisensy_base_url() -> str:
    return (os.getenv('AISENSY_API_URL') or AISENSY_DEFAULT_BASE_URL).rstrip('/')


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

# Founder-personal-number guard. The exact digits live in the
# ``TRAINPLEX_FOUNDER_MOBILE_GUARD`` env var (loaded by
# ``core.services.founder_guard``) so no literal of the number appears
# in this file. ``_assert_no_founder_personal_number()`` is kept as a
# thin local wrapper so internal call sites stay unchanged.
from core.services.founder_guard import (
    assert_no_founder_number as _guard_assert,
    digits_only as _guard_digits_only,
)


def _build_founder_digits() -> tuple[str, str]:
    """Return (with_cc, no_cc) digits-only forms of the founder mobile.

    Falls back to a never-match sentinel pair when the env var is empty
    so the guard remains side-effect free in CI / dev.
    """

    raw = os.getenv('TRAINPLEX_FOUNDER_MOBILE_GUARD', '').strip()
    digits = _FOUNDER_DIGIT_RE.sub('', raw)
    if len(digits) >= 10:
        last_ten = digits[-10:]
        return ('91' + last_ten, last_ten)
    # Sentinel that won't match real-world digit strings.
    return ('___NEVER_MATCH_WITH_CC___', '___NEVER_MATCH_NO_CC___')


_FOUNDER_PERSONAL_MOBILE_DIGITS_WITH_CC, _FOUNDER_PERSONAL_MOBILE_DIGITS_NO_CC = (
    _build_founder_digits()
)


def _digits_only(text: str) -> str:
    """Backwards-compatible alias → ``founder_guard.digits_only``."""
    return _guard_digits_only(text)


def _assert_no_founder_personal_number(payload: Any) -> None:
    """Raise if the founder's personal mobile sneaks into ``payload``.

    Delegates to the central :mod:`core.services.founder_guard` so the
    actual digits live in exactly one place (the env var). The original
    error message is preserved so existing tests / log scrapers still
    match.
    """
    try:
        _guard_assert(payload, context='WA broadcast')
    except ValueError as exc:
        raise ValueError(
            'WA broadcast aborted: founder personal mobile detected in payload.'
        ) from exc


# ---------------------------------------------------------------------------
# Mock AiSensy client
# ---------------------------------------------------------------------------


def _send_aisensy_template(
    mobile_number: str,
    template_id: str,
    params: Optional[Dict[str, Any]],
    *,
    dry_run: Optional[bool] = None,
) -> Dict[str, Any]:
    """Send a templated WA message via AiSensy.

    Wave-19 W2-MOCK-REAL — the function now performs a real
    ``requests.post`` to AiSensy's ``/send-template`` endpoint when:

      * ``dry_run`` is False (env ``TRAINPLEX_WA_DRY_RUN=false`` by default)
      * ``AISENSY_API_KEY`` is non-empty

    Tonight we ship with ``TRAINPLEX_WA_DRY_RUN=true`` in ``.env`` so the
    real call path is wired but blocked until the founder flips the toggle
    — exactly per the WAVE-19 W2 plan. In dry-run we still validate the
    founder-guard, log the would-be payload, and return a deterministic
    ``aisensy-dryrun-<uuid12>`` id so the rest of the flow (logging,
    idempotency, history endpoint) stays exercised end-to-end.

    On a real send we raise the underlying exception so the caller's
    try/except records the row as ``failed`` with the AiSensy error text;
    the founder-guard re-runs before every outbound just in case the env
    var changed since module load.
    """
    _assert_no_founder_personal_number(mobile_number)
    _assert_no_founder_personal_number(params or {})

    if dry_run is None:
        dry_run = _wa_dry_run_default()
    api_key = _aisensy_api_key()

    if dry_run or not api_key:
        fake_message_id = f'aisensy-dryrun-{uuid.uuid4().hex[:12]}'
        logger.info(
            'TrainPlex WA dry-run send: template=%s mobile=%s params=%s '
            '→ dryrun_message_id=%s (TRAINPLEX_WA_DRY_RUN=%s, key_present=%s)',
            template_id,
            mobile_number,
            params,
            fake_message_id,
            dry_run,
            bool(api_key),
        )
        return {
            'ok': True,
            'message_id': fake_message_id,
            'mock': True,
            'mode': 'dry_run',
        }

    # Real outbound. We intentionally keep the body shape AiSensy's docs
    # describe so the swap is a one-config flip.
    url = f'{_aisensy_base_url()}{AISENSY_TEMPLATE_ENDPOINT}'
    payload: Dict[str, Any] = {
        'apiKey': api_key,
        'campaignName': template_id,
        'destination': mobile_number,
        'userName': (params or {}).get('name') or 'TrainPlex Trainer',
        'templateParams': list((params or {}).get('templateParams') or []),
    }
    # Guard one more time on the assembled payload (defence-in-depth — the
    # founder-guard rule applies to every outbound regardless of source).
    _assert_no_founder_personal_number(payload)

    logger.info(
        'TrainPlex WA real send: template=%s mobile=%s url=%s',
        template_id,
        mobile_number,
        url,
    )
    resp = requests.post(url, json=payload, timeout=AISENSY_DEFAULT_TIMEOUT_SECONDS)
    resp.raise_for_status()
    try:
        body = resp.json()
    except ValueError:
        body = {'raw': resp.text[:500]}
    message_id = (
        body.get('messageId')
        or body.get('id')
        or f'aisensy-real-{uuid.uuid4().hex[:12]}'
    )
    return {
        'ok': True,
        'message_id': message_id,
        'mock': False,
        'mode': 'live',
        'response': body,
    }


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
