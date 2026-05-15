"""TrainPlex Admin Submissions Preview endpoint — Phase 1 Step 4.2-9.

Founder spot-check tool. Admin ek click pe recent 10 submissions ka sample
dekhe — image / answer preview + 3 reviewer scores — random fraud / quality
sweep super easy ho jaaye.

Endpoint
--------
    GET /api/v1/admin/submissions/preview

Query params (all optional)
---------------------------
    limit       — int, default 10, hard-capped at 50
    project_id  — int filter (silent-ignored on garbage)
    trainer_id  — int filter (silent-ignored on garbage)
    status      — one of submitted / under_review / approved / rejected
                  (silent-ignored on garbage)

Response
--------
    {
      "as_of": "ISO-8601 Z",
      "limit": int,
      "filters": {applied filters echoed back, empties omitted},
      "submissions": [SubmissionPreview, ...]
    }

`SubmissionPreview` keys: ``id``, ``project_id``, ``trainer``
(``{id, name, role}``), ``task_preview`` (≤200 chars or thumb URL),
``answer_preview`` (≤200 chars), ``reviewer_scores`` (list of 3
``{reviewer_id, score, agreed}`` entries), ``created_at`` (ISO-8601 Z),
``status``.

Phase 1 caveats
---------------
* No real submissions table exists in the fork yet (real schema lands in
  Phase 2 / Step 8). This view returns deterministic MOCK data via
  ``_get_mock_submissions_preview()``. Frontend can build/test against a
  stable shape; real DB wiring is a swap-in at one call site.
* The mock dataset has 24 entries so a `limit=50` request still returns
  meaningfully more rows than the default 10 — exercises the cap path.
* Reviewer scores are always a 3-element list so the 3-dot consensus
  visualizer renders without conditional branching.

TODO Step 4.2-9 / Phase 2 (Step 8): REPLACE ``_get_mock_submissions_preview``
with a real ``Submission.objects.filter(...).order_by('-created_at')`` query
once the submissions schema lands. Output shape is pinned by tests so the
swap is contract-safe.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.decorators import require_role

# Caps so a malicious caller can't ask for half the table in one shot.
_LIMIT_DEFAULT = 10
_LIMIT_MAX = 50

# Allow-list — anything outside is silently dropped so a typo / stray query
# param can't accidentally widen the filter surface.
_VALID_STATUSES = {'submitted', 'under_review', 'approved', 'rejected'}


def _coerce_positive_int(value: Any, default: int, hard_max: Optional[int] = None) -> int:
    """Coerce a string/int to a positive int with default + cap.

    Negative / non-numeric / zero values fall back to ``default``. Values
    above ``hard_max`` clamp (not error) — saves a 400 for a typo.
    """
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    if hard_max is not None and parsed > hard_max:
        return hard_max
    return parsed


# ---------------------------------------------------------------------------
# MOCK dataset — 24 recent submissions across 3 projects, 6 trainers.
#
# Stable shape; deterministic IDs and timestamps relative to "now" so admins
# can verify ordering / limit / filter behaviour against the same payload
# every time. Phase 2 swap replaces this with a DB query of identical shape.
# ---------------------------------------------------------------------------

# 6 trainers spread across roles + states. Role is included so the UI can
# colour-code trainer vs reviewer in the same list (a "rejected" submission
# might surface a reviewer's verdict, useful for spot-checking reviewer
# behaviour too).
_MOCK_TRAINERS: List[Dict[str, Any]] = [
    {'id': 101, 'name': 'Geeta P.', 'role': 'trainer'},
    {'id': 102, 'name': 'Sunil M.', 'role': 'trainer'},
    {'id': 103, 'name': 'Anil K.', 'role': 'trainer'},
    {'id': 104, 'name': 'Rekha S.', 'role': 'trainer'},
    {'id': 105, 'name': 'Vikas T.', 'role': 'trainer'},
    {'id': 106, 'name': 'Priya N.', 'role': 'trainer'},
]

# 3 reviewers (used in the 3-reviewer consensus list on every submission).
_MOCK_REVIEWERS: List[int] = [201, 202, 203]

# A handful of representative task previews — strings get truncated, image
# URLs surface as thumbnails on the frontend. Mock URLs deliberately point
# at a hosted placeholder so devs / e2e tests can render without a real
# storage backend.
_TASK_PREVIEWS: List[str] = [
    'https://placehold.co/120x120/png?text=KYC+1',
    'https://placehold.co/120x120/png?text=KYC+2',
    'Driver licence photo — reflective sticker visible',
    'Identify the language: "नमस्ते, आज मौसम बहुत अच्छा है।"',
    'https://placehold.co/120x120/png?text=Aadhaar',
    'Transcribe the audio clip (15s, Bhojpuri farmer voice).',
    'https://placehold.co/120x120/png?text=PAN',
    'Voter ID photo — back side, hindi address visible',
]

_ANSWER_PREVIEWS: List[str] = [
    '{"first_name": "Geeta", "last_name": "Patel", "dob": "1992-05-15"}',
    '{"language": "Hindi", "confidence": 0.92}',
    'मैं किसान हूँ, मेरी फसल अच्छी हुई इस साल।',
    '{"holder_name": "Sunil Mishra", "doc_number": "ABCDE1234F"}',
    'I am a farmer, my crop yield was good this year.',
    '{"reflective_sticker": true, "issue_date": "2019-08-22"}',
    '{"first_name": "Anil", "last_name": "Kumar", "dob": "1985-01-30"}',
    '{"holder_name": "Rekha Sharma", "doc_number": "FGHIJ5678K"}',
]

# Project IDs the mock submissions are spread across. 3 distinct projects
# (one each for KYC OCR, language ID, voice transcription) lets the
# `project_id` filter be exercised end-to-end.
_MOCK_PROJECT_IDS: List[int] = [501, 502, 503]


def _get_mock_submissions_preview() -> List[Dict[str, Any]]:
    """Return the deterministic 24-item mock dataset.

    Entries are pre-sorted newest-first (by ``created_at``) so the view
    doesn't have to re-sort — matches what the real query will deliver via
    ``.order_by('-created_at')``.

    The 3 reviewer scores per entry are chosen to exercise every possible
    consensus pattern (3/3 agreed, 2/3 agreed, 1/3 agreed, 0/3 agreed)
    across the dataset so the 3-dot visualizer has every state covered.
    """
    base_time = datetime.now(timezone.utc)
    rows: List[Dict[str, Any]] = []

    # Deterministic spread: 24 entries, each 12 minutes apart starting from
    # "now" going backwards in time. Status / project / trainer rotate so a
    # `limit=10` cut still surfaces a mix.
    statuses = ['submitted', 'under_review', 'approved', 'rejected']
    # 4 consensus patterns (counts of agreed reviewers out of 3) cycled so
    # admin sees every variant in the first ~12 rows.
    agree_patterns = [
        (True, True, True),       # 3/3 — clean
        (True, True, False),      # 2/3 — minor noise
        (True, False, False),     # 1/3 — likely wrong
        (False, False, False),    # 0/3 — disagreement (high-severity)
    ]

    for i in range(24):
        trainer = _MOCK_TRAINERS[i % len(_MOCK_TRAINERS)]
        project_id = _MOCK_PROJECT_IDS[i % len(_MOCK_PROJECT_IDS)]
        status = statuses[i % len(statuses)]
        task_preview = _TASK_PREVIEWS[i % len(_TASK_PREVIEWS)]
        answer_preview = _ANSWER_PREVIEWS[i % len(_ANSWER_PREVIEWS)]
        pattern = agree_patterns[i % len(agree_patterns)]

        # Reviewer scores: 3 entries, score in {0,1} for the visualization;
        # ``agreed`` mirrors that for symmetry with the agree/disagree i18n
        # keys the frontend renders.
        reviewer_scores = [
            {
                'reviewer_id': _MOCK_REVIEWERS[r],
                'score': 1 if pattern[r] else 0,
                'agreed': bool(pattern[r]),
            }
            for r in range(3)
        ]

        rows.append(
            {
                'id': 9000 + i,
                'project_id': project_id,
                'trainer': {
                    'id': trainer['id'],
                    'name': trainer['name'],
                    'role': trainer['role'],
                },
                'task_preview': task_preview[:200],
                'answer_preview': answer_preview[:200],
                'reviewer_scores': reviewer_scores,
                'created_at': (base_time - timedelta(minutes=12 * i)).isoformat().replace(
                    '+00:00', 'Z'
                ),
                'status': status,
            }
        )

    return rows


# ---------------------------------------------------------------------------
# GET /api/v1/admin/submissions/preview
# ---------------------------------------------------------------------------


class AdminSubmissionsPreviewAPI(APIView):
    """Admin-only spot-check view over the most-recent N submissions.

    Returns 403 for non-admin authenticated users; 401 (or 403, depending
    on auth class) for unauthenticated.

    See module docstring for the response contract.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Admin submissions preview',
        description=(
            'Recent submissions sample (default 10, cap 50) so admin can '
            'spot-check task / answer / reviewer scores at a glance. '
            'Filters: project_id, trainer_id, status. Admin role only. '
            'NOTE: Phase 1 returns deterministic mock data; real DB wiring '
            'is a swap-in at one call site (Phase 2 / Step 8).'
        ),
        parameters=[
            OpenApiParameter(
                name='limit', type=int, default=_LIMIT_DEFAULT,
                description=f'Max rows to return. Default {_LIMIT_DEFAULT}, hard cap {_LIMIT_MAX}.',
            ),
            OpenApiParameter(
                name='project_id', type=int, required=False,
                description='Filter by project id (silent-ignored on garbage).',
            ),
            OpenApiParameter(
                name='trainer_id', type=int, required=False,
                description='Filter by trainer (User) id (silent-ignored on garbage).',
            ),
            OpenApiParameter(
                name='status', type=str, required=False,
                description=(
                    'Filter by submission status — one of: '
                    'submitted / under_review / approved / rejected '
                    '(silent-ignored on anything else).'
                ),
            ),
        ],
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        # ---- limit (clamp, never 400 for a typo) ----
        limit = _coerce_positive_int(
            request.query_params.get('limit'),
            default=_LIMIT_DEFAULT,
            hard_max=_LIMIT_MAX,
        )

        # ---- filters (silent-ignore on garbage) ----
        filters_echo: Dict[str, Any] = {}

        rows = _get_mock_submissions_preview()

        project_id_raw = request.query_params.get('project_id')
        if project_id_raw:
            try:
                pid = int(project_id_raw)
                rows = [r for r in rows if r['project_id'] == pid]
                filters_echo['project_id'] = pid
            except (TypeError, ValueError):
                pass

        trainer_id_raw = request.query_params.get('trainer_id')
        if trainer_id_raw:
            try:
                tid = int(trainer_id_raw)
                rows = [r for r in rows if r['trainer']['id'] == tid]
                filters_echo['trainer_id'] = tid
            except (TypeError, ValueError):
                pass

        status_q = (request.query_params.get('status') or '').strip().lower()
        if status_q in _VALID_STATUSES:
            rows = [r for r in rows if r['status'] == status_q]
            filters_echo['status'] = status_q

        # ---- enforce limit (cap is already applied by _coerce_positive_int) ----
        rows = rows[:limit]

        return Response(
            {
                'as_of': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'limit': limit,
                'filters': filters_echo,
                'submissions': rows,
            },
            status=200,
        )
