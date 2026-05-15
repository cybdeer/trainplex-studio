"""TrainPlex payments — signal handlers.

Phase 1 Step 6.4. Wires ``peer_review.ConsensusResult.post_save`` to
``payments.services.payout_router.on_consensus_computed``.

Why post_save (not pre_save):
    The router needs the persisted row, including the ``status`` flip the
    consensus engine just made. Hooking pre_save would race the same
    transaction the engine itself is inside of.

Why not modify peer_review:
    Per the Step 6.4 brief — we must NOT touch peer_review code. Signal
    connection is the clean dependency-inversion: peer_review emits, we
    listen. peer_review remains independently testable.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from peer_review.models import ConsensusResult

logger = logging.getLogger(__name__)


@receiver(
    post_save,
    sender=ConsensusResult,
    dispatch_uid='payments.on_consensus_post_save',
)
def _on_consensus_post_save(sender, instance, created, **kwargs):
    """Route every ConsensusResult save into the payout router.

    Idempotent on the router side — re-saves for an already-resolved hold
    are no-ops. Wrapped in a try/except so a payments-side bug never
    rolls back the consensus row itself.
    """
    # Local import keeps the signal module light + avoids early-load
    # cycles when Django boots.
    from payments.services.payout_router import on_consensus_computed

    try:
        on_consensus_computed(instance)
    except Exception as exc:  # pragma: no cover  (defensive)
        # We never let a payments-side exception roll back the consensus
        # save — the consensus row is the source of truth for peer_review.
        logger.exception(
            'payments.signals.on_consensus_post_save error task_id=%s err=%s',
            getattr(instance, 'task_id', None), exc,
        )
