"""TrainPlex payments Django app.

Phase 1 Step 6.4 + Step 1.4-G. Builds the Payment Release Flow tied to
the 3-reviewer consensus emitted by ``peer_review``:

* Trainer submits task → ``PaymentHold`` opens (status=held, amount frozen).
* 3 reviewers assigned (off the existing ``peer_review`` flow).
* Consensus computed by ``peer_review.services.consensus_engine``.
* 2+/3 agree (``approved`` / ``flagged``) → release hold + queue payout.
* 1/3 (``dispute``) → hold remains + QA flag.
* 0/3 (``rejected``) → hold refunded + trainer notified.

The signal-handler in ``payments/signals.py`` listens for the
``ConsensusResult.post_save`` and dispatches via
``payments.services.payout_router.on_consensus_computed``.

Phase 1 status
--------------
* Razorpay X is MOCKED (``payments.services.razorpay_handler``) — the real
  network call lands Phase 2 with prod credentials. No ``razorpay-python``
  dependency is added yet.
* All endpoints role-gated via ``users.decorators.require_role``; the
  trainer wallet endpoint is self-only (a trainer cannot fetch another
  trainer's balance).
"""

default_app_config = 'payments.apps.PaymentsConfig'
