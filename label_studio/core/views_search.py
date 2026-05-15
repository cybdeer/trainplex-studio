"""TrainPlex Admin Global Search (Cmd+K) endpoint — Phase 1 Step 14.

Founder + admin ke liye Cmd+K command palette. Ek hi search box me trainer,
project, submission, audit log, task — sab kuch instant search ho jaaye.

Endpoint
--------
    GET /api/v1/admin/search?q=<term>&scope=<scope>

Query params
------------
- ``q``        — search term. Empty / whitespace-only returns ``[]`` (NOT 400)
                  so the frontend's "open Cmd+K → empty input → show recent
                  searches placeholder" flow doesn't bounce.
- ``scope``    — one of ``submissions``, ``trainers``, ``projects``,
                  ``audit_logs``, ``tasks``, ``all`` (default). Unknown
                  scope falls back to ``all`` rather than 400 — silent ignore
                  keeps a typo'd palette state usable.

Response
--------
Flat JSON array, max 50 results across all scopes (hard-cap). Each entry::

    {
      "type": "trainer" | "project" | "submission" | "audit" | "task",
      "id": <int>,
      "title": "<short label rendered in palette row>",
      "subtitle": "<secondary metadata line>",
      "url": "<frontend route the palette will navigate to>"
    }

Access control
--------------
@require_role(['admin']) — every other role gets a 403. The palette is
admin/founder only. Trainer/reviewer/qa_lead do not need a cross-table
search; their work is scoped to their own queue.

Phase 1 status
--------------
MOCK data — returns a deterministic seed across all scopes so the
frontend can build/test against a stable shape. The Postgres FTS
GIN indexes are created by migration ``core/migrations/0006_fulltext_search_indexes.py``
but this view does NOT yet query them. Real ``to_tsvector`` search lands
in Phase 2 once the submissions / projects / tasks schema is in place.

TODO Phase 2: REPLACE ``_search_mock_dataset()`` with the real query
flow:
    1. Pivot per ``scope`` to the right table.
    2. Use Django ``SearchVector`` / ``SearchQuery`` (Postgres) or
       ``icontains`` chain (SQLite fallback for dev).
    3. UNION ALL across scopes when ``scope=all``.
    4. ``LIMIT 50`` total (per-scope quota + global cap).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.decorators import require_role

# Hard cap so a malicious / buggy caller can't ask for half the table
# from a single keystroke (palette debounces 300ms — multiple in-flight
# would otherwise hammer the API).
_MAX_RESULTS = 50

# Valid scope allow-list. Anything outside silently falls back to
# ``all`` — saves a 400 on a stray query-string drift.
_VALID_SCOPES = {
    'submissions',
    'trainers',
    'projects',
    'audit_logs',
    'tasks',
    'all',
}


def _normalize_scope(raw: Optional[str]) -> str:
    """Coerce a raw scope query-param to a known scope.

    Empty / None / unknown values fall back to ``all`` so a typo doesn't
    explode the palette.
    """
    if not raw:
        return 'all'
    lowered = raw.strip().lower()
    if lowered in _VALID_SCOPES:
        return lowered
    return 'all'


# ---------------------------------------------------------------------------
# MOCK dataset
#
# Stable, deterministic seed across all 5 result types. Each block is
# pre-shaped so the frontend can build the palette UI against the final
# JSON contract. Phase 2 swap-in replaces ``_search_mock_dataset()`` with
# a real query — output shape stays identical.
#
# Indian names + states are deliberately chosen so an admin testing the
# palette with ``q=Geeta`` / ``q=Rajasthan`` / ``q=Hindi`` immediately sees
# meaningful hits.
# ---------------------------------------------------------------------------

_MOCK_TRAINERS: List[Dict[str, Any]] = [
    {
        'type': 'trainer',
        'id': 5,
        'title': 'Geeta Parihar',
        'subtitle': 'Rajasthan · Bronze · Hindi',
        'url': '/admin/trainers/5',
        # internal search corpus — joined with title/subtitle in the matcher
        '_search': 'geeta parihar rajasthan bronze hindi trainer',
    },
    {
        'type': 'trainer',
        'id': 7,
        'title': 'Sunil Mishra',
        'subtitle': 'UP · Silver · Hindi, Bhojpuri',
        'url': '/admin/trainers/7',
        '_search': 'sunil mishra up silver hindi bhojpuri trainer',
    },
    {
        'type': 'trainer',
        'id': 12,
        'title': 'Anil Kumar',
        'subtitle': 'Bihar · Gold · Hindi, Maithili',
        'url': '/admin/trainers/12',
        '_search': 'anil kumar bihar gold hindi maithili trainer',
    },
    {
        'type': 'trainer',
        'id': 19,
        'title': 'Rekha Sharma',
        'subtitle': 'MP · Silver · Hindi',
        'url': '/admin/trainers/19',
        '_search': 'rekha sharma mp silver hindi trainer',
    },
    {
        'type': 'trainer',
        'id': 23,
        'title': 'Vikas Tomar',
        'subtitle': 'Haryana · Bronze · Hindi, Haryanvi',
        'url': '/admin/trainers/23',
        '_search': 'vikas tomar haryana bronze hindi haryanvi trainer',
    },
    {
        'type': 'trainer',
        'id': 31,
        'title': 'Priya Nair',
        'subtitle': 'Kerala · Gold · Malayalam, English',
        'url': '/admin/trainers/31',
        '_search': 'priya nair kerala gold malayalam english trainer',
    },
]

_MOCK_PROJECTS: List[Dict[str, Any]] = [
    {
        'type': 'project',
        'id': 12,
        'title': 'Hindi NER',
        'subtitle': 'Active · 487/500 tasks',
        'url': '/admin/projects/12',
        '_search': 'hindi ner named entity recognition active 487 500 tasks',
    },
    {
        'type': 'project',
        'id': 14,
        'title': 'KYC OCR Batch May 2026',
        'subtitle': 'Active · 1240/2000 tasks',
        'url': '/admin/projects/14',
        '_search': 'kyc ocr batch may 2026 active 1240 2000 tasks',
    },
    {
        'type': 'project',
        'id': 18,
        'title': 'Bhojpuri voice transcription',
        'subtitle': 'Active · 320/500 tasks',
        'url': '/admin/projects/18',
        '_search': 'bhojpuri voice transcription active 320 500 tasks audio',
    },
    {
        'type': 'project',
        'id': 22,
        'title': 'Aadhaar card classification',
        'subtitle': 'Paused · 80/300 tasks',
        'url': '/admin/projects/22',
        '_search': 'aadhaar card classification paused 80 300 tasks ocr',
    },
    {
        'type': 'project',
        'id': 27,
        'title': 'Marathi sentiment',
        'subtitle': 'Active · 150/200 tasks',
        'url': '/admin/projects/27',
        '_search': 'marathi sentiment active 150 200 tasks language',
    },
]

_MOCK_SUBMISSIONS: List[Dict[str, Any]] = [
    {
        'type': 'submission',
        'id': 1023,
        'title': 'Submission #1023',
        'subtitle': 'Geeta · 2h ago · Hindi NER',
        'url': '/admin/submissions/1023',
        '_search': 'submission 1023 geeta hindi ner 2h ago approved',
    },
    {
        'type': 'submission',
        'id': 1031,
        'title': 'Submission #1031',
        'subtitle': 'Sunil · 1h ago · KYC OCR',
        'url': '/admin/submissions/1031',
        '_search': 'submission 1031 sunil kyc ocr 1h ago under review',
    },
    {
        'type': 'submission',
        'id': 1042,
        'title': 'Submission #1042',
        'subtitle': 'Anil · 30m ago · Bhojpuri voice',
        'url': '/admin/submissions/1042',
        '_search': 'submission 1042 anil bhojpuri voice 30m ago approved',
    },
    {
        'type': 'submission',
        'id': 1055,
        'title': 'Submission #1055',
        'subtitle': 'Rekha · 15m ago · Hindi NER',
        'url': '/admin/submissions/1055',
        '_search': 'submission 1055 rekha hindi ner 15m ago rejected',
    },
    {
        'type': 'submission',
        'id': 1067,
        'title': 'Submission #1067',
        'subtitle': 'Priya · 5m ago · Marathi sentiment',
        'url': '/admin/submissions/1067',
        '_search': 'submission 1067 priya marathi sentiment 5m ago submitted',
    },
]

_MOCK_AUDIT_LOGS: List[Dict[str, Any]] = [
    {
        'type': 'audit',
        'id': 991,
        'title': 'login_success by ceo@cybdeer.com',
        'subtitle': '15 May 2026 16:25 · IP 192.168.1.5',
        'url': '/admin/audit?id=991',
        '_search': 'login success ceo cybdeer admin 192.168.1.5 16:25 15 may',
    },
    {
        'type': 'audit',
        'id': 988,
        'title': 'permission_change by ceo@cybdeer.com',
        'subtitle': '15 May 2026 15:10 · target=User:7 (trainer→reviewer)',
        'url': '/admin/audit?id=988',
        '_search': 'permission change ceo cybdeer trainer reviewer user 7 role change',
    },
    {
        'type': 'audit',
        'id': 985,
        'title': 'delete by ceo@cybdeer.com',
        'subtitle': '15 May 2026 14:50 · target=Project:11',
        'url': '/admin/audit?id=985',
        '_search': 'delete ceo cybdeer project 11 hard delete',
    },
    {
        'type': 'audit',
        'id': 980,
        'title': 'login_fail by unknown@x.com',
        'subtitle': '15 May 2026 12:00 · IP 10.0.0.7',
        'url': '/admin/audit?id=980',
        '_search': 'login fail unknown failed 10.0.0.7 12:00 15 may attack',
    },
]

_MOCK_TASKS: List[Dict[str, Any]] = [
    {
        'type': 'task',
        'id': 7001,
        'title': 'Task #7001',
        'subtitle': 'Hindi NER · "नमस्ते भारत"',
        'url': '/admin/tasks/7001',
        '_search': 'task 7001 hindi ner namaste bharat label',
    },
    {
        'type': 'task',
        'id': 7012,
        'title': 'Task #7012',
        'subtitle': 'KYC OCR · Aadhaar front',
        'url': '/admin/tasks/7012',
        '_search': 'task 7012 kyc ocr aadhaar front card image',
    },
    {
        'type': 'task',
        'id': 7025,
        'title': 'Task #7025',
        'subtitle': 'Bhojpuri voice · 15s clip',
        'url': '/admin/tasks/7025',
        '_search': 'task 7025 bhojpuri voice 15s clip audio transcription',
    },
]


# Scope → mock-dataset lookup so the scope filter is a one-line dispatch.
_SCOPE_DATASETS: Dict[str, List[Dict[str, Any]]] = {
    'trainers': _MOCK_TRAINERS,
    'projects': _MOCK_PROJECTS,
    'submissions': _MOCK_SUBMISSIONS,
    'audit_logs': _MOCK_AUDIT_LOGS,
    'tasks': _MOCK_TASKS,
}


def _row_matches(row: Dict[str, Any], needle: str) -> bool:
    """Cheap case-insensitive substring match against the row's search corpus.

    Search corpus = ``_search`` + ``title`` + ``subtitle`` — the corpus is
    pre-lowercased at module-load time conceptually, but we lower at query
    time so the seed dict above stays human-readable.

    Phase 2 swap: replace this with a Postgres ``SearchVector`` lookup on
    the GIN indexes from migration 0006.
    """
    corpus = ' '.join(
        [
            (row.get('_search') or '').lower(),
            (row.get('title') or '').lower(),
            (row.get('subtitle') or '').lower(),
        ]
    )
    return needle in corpus


def _shape_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Strip the internal ``_search`` field before serializing.

    Frontend only needs ``type``, ``id``, ``title``, ``subtitle``, ``url``.
    """
    return {
        'type': row['type'],
        'id': row['id'],
        'title': row['title'],
        'subtitle': row['subtitle'],
        'url': row['url'],
    }


def _search_mock_dataset(q: str, scope: str) -> List[Dict[str, Any]]:
    """Run the mock search and return up to ``_MAX_RESULTS`` rows.

    TODO Phase 2: REPLACE with a Postgres FTS query (see module docstring).
    Output shape is pinned by the tests so the swap is contract-safe.
    """
    needle = q.strip().lower()
    if not needle:
        # Empty needle → no results. Frontend uses this to show "recent
        # searches" / placeholder copy instead.
        return []

    # Pick which datasets to scan.
    if scope == 'all':
        datasets: List[List[Dict[str, Any]]] = list(_SCOPE_DATASETS.values())
    else:
        datasets = [_SCOPE_DATASETS.get(scope, [])]

    matches: List[Dict[str, Any]] = []
    for ds in datasets:
        for row in ds:
            if _row_matches(row, needle):
                matches.append(_shape_row(row))
                if len(matches) >= _MAX_RESULTS:
                    # Global cap reached — bail out of both loops.
                    return matches

    return matches


class AdminGlobalSearchAPI(APIView):
    """Admin-only Cmd+K command palette search.

    Returns a flat JSON array (max 50) across trainers, projects,
    submissions, audit logs and tasks. Scope filter narrows to one type.

    NOTE: returns mock data in Phase 1 (Week 4). Real Postgres FTS
    powered by the GIN indexes in migration ``0006_fulltext_search_indexes``
    lands in Phase 2 / Step 8.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Global Cmd+K command palette search',
        description=(
            'Admin-only instant search across trainers, projects, '
            'submissions, audit logs and tasks. Returns up to 50 results. '
            'Empty `q` returns []. Phase 1 returns mock data; real Postgres '
            'FTS lands in Phase 2 (GIN indexes created by migration 0006).'
        ),
        parameters=[
            OpenApiParameter(
                'q',
                str,
                description='Search term (case-insensitive substring).',
            ),
            OpenApiParameter(
                'scope',
                str,
                description=(
                    'One of submissions, trainers, projects, audit_logs, '
                    'tasks, all (default).'
                ),
            ),
        ],
    )
    @require_role(['admin'])
    def get(self, request, *args, **kwargs):
        q = request.query_params.get('q') or ''
        scope = _normalize_scope(request.query_params.get('scope'))

        results = _search_mock_dataset(q, scope)
        return Response(results, status=200)
