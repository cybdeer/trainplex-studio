"""Monthly summary report — fires on day-1 09:00 IST via core.scheduler.

Computes prior-month submissions / active trainers / revenue and returns
a payload. Tonight (dry_run=True by default) it only logs; no email is sent.
TODO: once a send_monthly_summary email wrapper exists, wire it under the
not dry_run branch — same pattern as core.services.daily_report_email.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def run(dry_run: bool = True) -> dict:
    """Build last-month summary. dry_run skips side-effects (email send)."""
    # Lazy imports — Django apps may not be ready at module import time
    # (scheduler is a separate management command process).
    from django.db.models import Sum
    from tasks.models import Annotation
    from users.models import User

    today = datetime.utcnow().date()
    month_start = today.replace(day=1)
    last_month_end = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    submissions = Annotation.objects.filter(
        created_at__date__range=[last_month_start, last_month_end]
    ).count()

    active_trainers = User.objects.filter(
        role='trainer',
        last_login__date__range=[last_month_start, last_month_end],
    ).count()

    # PaymentHold revenue — guarded because the table can be empty
    # in fresh staging environments.
    try:
        from payments.models import PaymentHold
        agg = (PaymentHold.objects
               .filter(created_at__date__range=[last_month_start, last_month_end])
               .aggregate(t=Sum('amount_inr')))
        revenue = agg.get('t') or 0
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning('[monthly_summary] revenue calc skipped: %s', exc)
        revenue = 0

    payload = {
        'month': last_month_start.strftime('%Y-%m'),
        'submissions': submissions,
        'active_trainers': active_trainers,
        'revenue_inr': float(revenue) if revenue else 0.0,
        'generated_at': datetime.utcnow().isoformat(),
        'dry_run': dry_run,
    }
    logger.info('[monthly_summary] payload=%s dry_run=%s', payload, dry_run)

    if not dry_run:
        # TODO: email founder via core.services.daily_report_email.send_email_template
        # equivalent. For tonight's roll-out we deliberately stay dry_run=True so
        # we don't double-send on first cron fire after deploy.
        logger.warning('[monthly_summary] live-mode requested but no sender wrapper yet')

    return payload
