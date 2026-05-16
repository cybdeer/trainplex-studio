"""TrainPlex payments — payout provider selector (Wave-19 W2-PAYOUT).

Single switch point between Razorpay (deprecated rollback-only) and
ShivGateway (active). The router, webhook, cron flush, and admin retry
all import the active provider's functions from here — never from a
concrete handler — so flipping ``TRAINPLEX_PAYOUT_PROVIDER`` (one env
var) is the complete swap.

Provider contract
-----------------
Every handler module must expose these names with the same signatures:

    send_payout(payout_queue_entry, *, force_mock_failure=False, dry_run=None) -> PayoutQueue
    mark_sent(payout_id, external_id) -> PayoutQueue
    mark_failed(payout_id, error) -> PayoutQueue
    retry_payout(payout_id) -> Optional[PayoutQueue]
    process_webhook_event(event) -> dict
    verify_webhook_signature(*, body, signature, secret) -> bool

Founder rule (MEMORY.md → feedback_no_founder_personal_number.md): no
personal mobile in payloads. Both handlers identify trainers by queue
reference id, never by free-text contact.
"""

from __future__ import annotations

import logging
import os
from types import ModuleType

logger = logging.getLogger(__name__)


def _resolve_provider() -> ModuleType:
    """Return the active provider module. Defaults to ShivGateway.

    Resolved at call time (not import time) so a test setting
    ``TRAINPLEX_PAYOUT_PROVIDER`` via ``override_settings``-style env
    monkey-patch can flip without a module reload.
    """
    name = (os.getenv('TRAINPLEX_PAYOUT_PROVIDER') or 'shivgateway').strip().lower()
    if name == 'razorpay':
        # Rollback-only path. Kept for emergency revert if ShivGateway
        # has a production outage before the founder confirms creds.
        from payments.services import razorpay_handler
        return razorpay_handler
    if name == 'shivgateway':
        from payments.services import shivgateway_handler
        return shivgateway_handler
    logger.error(
        'payments.payout_provider unknown provider=%r, falling back to shivgateway',
        name,
    )
    from payments.services import shivgateway_handler
    return shivgateway_handler


def send_payout(payout_queue_entry, **kwargs):
    return _resolve_provider().send_payout(payout_queue_entry, **kwargs)


def mark_sent(payout_id, external_id):
    return _resolve_provider().mark_sent(payout_id, external_id)


def mark_failed(payout_id, error):
    return _resolve_provider().mark_failed(payout_id, error)


def retry_payout(payout_id):
    return _resolve_provider().retry_payout(payout_id)


def process_webhook_event(event):
    return _resolve_provider().process_webhook_event(event)


def verify_webhook_signature(*, body, signature, secret):
    return _resolve_provider().verify_webhook_signature(
        body=body, signature=signature, secret=secret,
    )


def active_provider_name() -> str:
    """Surface the active provider name for logs / health endpoints."""
    return (os.getenv('TRAINPLEX_PAYOUT_PROVIDER') or 'shivgateway').strip().lower()
