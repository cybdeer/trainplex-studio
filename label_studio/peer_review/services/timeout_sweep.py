"""Review timeout sweep — fires every 60 min via core.scheduler.

Walks ReviewAssignment rows still in pending past their 48h cutoff
and (in live mode) flips them to expired. Per peer_review.models the
canonical timeout state is STATUS_EXPIRED — the spec said 'auto_released'
but that status does not exist in the schema, so we align to the model.

Per plan Step 6.2 a single-reviewer auto-release path can be layered on
top later; for tonight's roll-out we only mark expired so the queue does
not stall.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def run(dry_run: bool = True) -> dict:
    """Expire stale reviews older than 48h. dry_run skips writes."""
    from peer_review.models import ReviewAssignment

    cutoff = datetime.utcnow() - timedelta(hours=48)
    stale = ReviewAssignment.objects.filter(
        status=ReviewAssignment.STATUS_PENDING,
        assigned_at__lt=cutoff,
    )
    count = stale.count()
    auto_decided = 0
    errors: list[str] = []

    if not dry_run:
        for ra in stale[:100]:
            try:
                ra.status = ReviewAssignment.STATUS_EXPIRED
                ra.save(update_fields=['status'])
                auto_decided += 1
            except Exception as exc:  # pragma: no cover
                errors.append(f'{ra.pk}:{exc!r}')

    result = {
        'stale': count,
        'auto_decided': auto_decided,
        'errors': errors,
        'dry_run': dry_run,
    }
    logger.info('[timeout_sweep] %s', result)
    return result
