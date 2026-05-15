"""TrainPlex payments services — payout_router, razorpay_handler, wallet.

The three modules form a clean separation:

* ``payout_router`` — consensus event handler. Knows nothing about Razorpay;
  delegates the network call to ``razorpay_handler``.
* ``razorpay_handler`` — payout dispatch + retry + status confirmation.
  Mocked in Phase 1 (no ``razorpay-python`` dep yet).
* ``wallet`` — read-only balance / held-balance / recent-transactions
  queries used by the trainer wallet endpoint.
"""
