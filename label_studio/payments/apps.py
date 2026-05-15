"""TrainPlex payments Django app config — Phase 1 Step 6.4 + 1.4-G."""

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = 'payments'
    verbose_name = 'TrainPlex Payments'

    def ready(self):
        # Register the consensus → payout signal handler. Import lives
        # inside ``ready()`` so Django doesn't pull the handler module
        # before app-registry initialisation (which would import models
        # before they're loaded). The handler itself is a no-op when the
        # ConsensusResult row has no matching PaymentHold (e.g. peer-review
        # tests that don't open a hold).
        from payments import signals  # noqa: F401
