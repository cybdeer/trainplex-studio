"""TrainPlex peer-review app — Phase 1 Step 6.

Houses the 3-reviewer consensus engine + dispute resolution flow.

Tables (see ``peer_review/models.py``):
* ``htx_review_assignment`` — one row per (task, reviewer) reviewer-side row.
* ``htx_review`` — the reviewer's actual verdict (score / agreement / comment).
* ``htx_consensus_result`` — aggregate 3-reviewer outcome per task.
* ``htx_dispute`` — escalation row when consensus is split.

Endpoints (see ``peer_review/api.py``):
* GET  /api/v1/reviewer/queue
* POST /api/v1/reviewer/submit-review
* GET  /api/v1/qa/disputes
* POST /api/v1/qa/disputes/<id>/resolve

All endpoints enforce ``users.decorators.require_role`` (reviewer / qa_lead).
"""

default_app_config = 'peer_review.apps.PeerReviewConfig'
