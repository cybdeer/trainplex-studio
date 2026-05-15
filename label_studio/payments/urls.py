"""TrainPlex payments URL routes — Phase 1 Step 6.4 + 4.2-5.

Mounted by ``core/urls.py`` via ``include('payments.urls')``.

Endpoints
---------
    GET  /api/v1/payments/wallet                       (trainer-only, self)
    GET  /api/v1/payments/payout-queue                 (admin-only)
    POST /api/v1/payments/payout-queue/<id>/retry      (admin-only)
    GET  /api/v1/admin/payment-status                  (admin-only)
"""

from django.urls import path

from payments.api import (
    AdminPaymentStatusAPI,
    AdminPayoutQueueAPI,
    AdminPayoutRetryAPI,
    TrainerWalletAPI,
)

urlpatterns = [
    path(
        'api/v1/payments/wallet',
        TrainerWalletAPI.as_view(),
        name='payments-trainer-wallet',
    ),
    path(
        'api/v1/payments/payout-queue',
        AdminPayoutQueueAPI.as_view(),
        name='payments-admin-payout-queue',
    ),
    path(
        'api/v1/payments/payout-queue/<int:payout_id>/retry',
        AdminPayoutRetryAPI.as_view(),
        name='payments-admin-payout-retry',
    ),
    path(
        'api/v1/admin/payment-status',
        AdminPaymentStatusAPI.as_view(),
        name='payments-admin-payment-status',
    ),
]
