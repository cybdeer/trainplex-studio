"""TrainPlex peer-review URL routes — Phase 1 Step 6.

Mounted by ``core/urls.py`` via ``include('peer_review.urls')``.
"""

from django.urls import path

from peer_review.api import (
    QADisputeResolveAPI,
    QADisputesListAPI,
    ReviewerQueueAPI,
    ReviewerSubmitReviewAPI,
)

urlpatterns = [
    path(
        'api/v1/reviewer/queue',
        ReviewerQueueAPI.as_view(),
        name='peer-review-reviewer-queue',
    ),
    path(
        'api/v1/reviewer/submit-review',
        ReviewerSubmitReviewAPI.as_view(),
        name='peer-review-reviewer-submit',
    ),
    path(
        'api/v1/qa/disputes',
        QADisputesListAPI.as_view(),
        name='peer-review-qa-disputes',
    ),
    path(
        'api/v1/qa/disputes/<int:dispute_id>/resolve',
        QADisputeResolveAPI.as_view(),
        name='peer-review-qa-dispute-resolve',
    ),
]
