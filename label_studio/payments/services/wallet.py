"""TrainPlex payments — wallet read-side queries.

Phase 1 Step 6.4. Used by the trainer wallet API + dashboard widget.

All functions are pure-read; mutation happens via ``payout_router``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import List

from django.db.models import Sum
from django.utils import timezone

from payments.models import PaymentHold, WalletTransaction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_balance(user) -> Decimal:
    """Current wallet balance for ``user`` in INR.

    Phase 1: snapshot from the latest WalletTransaction row — populated by
    the payout_router on every release / payout / refund. Falls back to
    zero when the trainer has no ledger history yet.
    """
    if user is None or not getattr(user, 'id', None):
        return Decimal('0')
    latest = (
        WalletTransaction.objects.filter(user=user)
        .order_by('-created_at', '-id')
        .first()
    )
    if latest is None:
        return Decimal('0')
    return latest.balance_after_inr


def get_held_balance(user) -> Decimal:
    """Sum of every PaymentHold currently in `held` for ``user``.

    Different from ``get_balance`` — the held bucket is money that exists
    but is not yet spendable. Surfaced to the trainer so the "₹X awaiting
    review" line in the wallet UI is accurate.
    """
    if user is None or not getattr(user, 'id', None):
        return Decimal('0')
    agg = (
        PaymentHold.objects.filter(trainer=user, status=PaymentHold.STATUS_HELD)
        .aggregate(total=Sum('amount_inr'))
    )
    return agg['total'] or Decimal('0')


def get_recent_transactions(user, limit: int = 30) -> List[WalletTransaction]:
    """Return the most-recent ``limit`` WalletTransaction rows for ``user``.

    Capped at 100 server-side so a malicious / malformed client query
    can't pull the whole ledger in one shot.
    """
    if user is None or not getattr(user, 'id', None):
        return []
    capped = max(1, min(int(limit or 30), 100))
    return list(
        WalletTransaction.objects.filter(user=user)
        .order_by('-created_at', '-id')[:capped]
    )


def get_month_earnings(user, since: 'datetime | None' = None) -> Decimal:
    """Sum of ``release`` ledger rows for ``user`` since ``since``.

    Defaults to the first of the current calendar month (server timezone).
    Used by the trainer dashboard widget's "This month earnings" card.
    """
    if user is None or not getattr(user, 'id', None):
        return Decimal('0')
    if since is None:
        now = timezone.now()
        since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    agg = (
        WalletTransaction.objects.filter(
            user=user,
            txn_type=WalletTransaction.TYPE_RELEASE,
            created_at__gte=since,
        )
        .aggregate(total=Sum('amount_inr'))
    )
    return agg['total'] or Decimal('0')


def compute_trainer_balance(user) -> Decimal:
    """Recompute the balance from the ledger sum (not the snapshot).

    Defensive fallback for ledger-corruption checks — released - paid.
    Used internally by the wallet API as a sanity assert + by tests.
    """
    if user is None or not getattr(user, 'id', None):
        return Decimal('0')
    released = (
        WalletTransaction.objects.filter(
            user=user, txn_type=WalletTransaction.TYPE_RELEASE,
        ).aggregate(total=Sum('amount_inr'))['total'] or Decimal('0')
    )
    paid = (
        WalletTransaction.objects.filter(
            user=user, txn_type=WalletTransaction.TYPE_PAYOUT,
        ).aggregate(total=Sum('amount_inr'))['total'] or Decimal('0')
    )
    return released - paid
