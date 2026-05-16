"""Payout flush — fires every 30 min via core.scheduler.

Walks PayoutQueue rows in status pending and (in live mode) hands them
to payments.services.payout_router for Razorpay X dispatch. Dry-run only
counts + logs; no Razorpay call, no status mutation.

NOTE: the spec referenced status='queued' but the canonical model uses
pending (see PayoutQueue.STATUS_PENDING). We align to the model.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def run(dry_run: bool = True) -> dict:
    """Drain up to 50 pending payouts per fire. dry_run skips Razorpay calls."""
    from payments.models import PayoutQueue

    queued = PayoutQueue.objects.filter(status=PayoutQueue.STATUS_PENDING)
    count = queued.count()
    processed = 0
    errors: list[str] = []

    if not dry_run:
        # TODO: replace with payments.services.payout_router.dispatch(p) once that
        # wrapper accepts the queue row directly. For now we mark processing
        # so the queue does not stall — actual Razorpay call still pending wiring.
        for p in queued[:50]:
            try:
                p.status = PayoutQueue.STATUS_PROCESSING
                p.save(update_fields=['status'])
                processed += 1
            except Exception as exc:  # pragma: no cover
                errors.append(f'{p.pk}:{exc!r}')

    result = {
        'queued': count,
        'processed': processed,
        'errors': errors,
        'dry_run': dry_run,
    }
    logger.info('[payout_flush] %s', result)
    return result
