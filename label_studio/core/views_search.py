"""TrainPlex Admin Global Search (Cmd+K) endpoint — Phase 2 WAVE-19 real-data wiring.

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
admin/founder only.

Phase 2 wiring
--------------
Real Django ORM. Postgres path uses ``SearchVector`` + ``SearchQuery``
against the GIN indexes from migration ``0006_fulltext_search_indexes``.
SQLite path (dev / Label-Studio default backend) falls back to chained
``icontains`` filters — the GIN index does not exist on SQLite but the
``htx_user`` row count is small enough that an icontains scan returns in
<10ms.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db import connection
from django.db.models import Q, Value
from django.db.models.functions import Concat
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.decorators import require_role

# Hard cap so a malicious / buggy caller can't ask for half the table
# from a single keystroke (palette debounces 300ms — multiple in-flight
# would otherwise hammer the API).
_MAX_RESULTS = 50

# Per-scope cap when ``scope=all`` — keeps any single scope from
# starving the others on a broad term ("hindi" matches projects + tasks).
_PER_SCOPE_CAP = 10

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


def _is_postgres() -> bool:
    """True iff the active DB connection is Postgres.

    Used to gate ``SearchVector`` / ``SearchQuery`` — those APIs require
    the ``django.contrib.postgres`` machinery and won't run on SQLite.
    """
    return connection.vendor == 'postgresql'


# ---------------------------------------------------------------------------
# Per-scope search implementations.
#
# Each ``_search_<scope>`` returns a list of shaped dicts (no ``_search``
# helper field). Functions are independent so a ``scope=trainers`` call
# only hits ``htx_user`` — no waste.
# ---------------------------------------------------------------------------


def _search_trainers(needle: str, limit: int) -> List[Dict[str, Any]]:
    """Search ``users.User`` rows where ``role='trainer'``.

    Postgres: ``SearchVector(first_name, last_name, email)`` + ``SearchQuery``
    SQLite:   chained ``icontains`` on first_name | last_name | email | username
    """
    from users.models import User

    qs = User.objects.filter(role='trainer')

    if _is_postgres():
        # ``django.contrib.postgres.search`` is only importable on a
        # Postgres-enabled install; import lazily so a SQLite dev box
        # never trips the ImportError.
        from django.contrib.postgres.search import SearchQuery, SearchVector

        vector = SearchVector('first_name', 'last_name', 'email', 'username', config='simple')
        query = SearchQuery(needle, config='simple', search_type='plain')
        qs = qs.annotate(search=vector).filter(search=query)
    else:
        qs = qs.filter(
            Q(first_name__icontains=needle)
            | Q(last_name__icontains=needle)
            | Q(email__icontains=needle)
            | Q(username__icontains=needle)
        )

    out: List[Dict[str, Any]] = []
    for u in qs.order_by('-id')[:limit]:
        full = (f'{u.first_name} {u.last_name}').strip() or u.username or u.email
        state = (getattr(u, 'state', '') or '').strip()
        subtitle_parts = [s for s in (state, u.email) if s]
        out.append({
            'type': 'trainer',
            'id': u.id,
            'title': full,
            'subtitle': ' · '.join(subtitle_parts),
            'url': f'/admin/trainers/{u.id}',
        })
    return out


def _search_admins_and_other_users(needle: str, limit: int) -> List[Dict[str, Any]]:
    """Search non-trainer users (admin, reviewer, qa_lead, etc.).

    Surfaced alongside trainers on the ``trainers`` and ``all`` scopes so
    Vinod / other admins are findable in the palette — otherwise an admin
    searching their own name would get zero results.
    """
    from users.models import User

    qs = User.objects.exclude(role='trainer')

    if _is_postgres():
        from django.contrib.postgres.search import SearchQuery, SearchVector

        vector = SearchVector('first_name', 'last_name', 'email', 'username', config='simple')
        query = SearchQuery(needle, config='simple', search_type='plain')
        qs = qs.annotate(search=vector).filter(search=query)
    else:
        qs = qs.filter(
            Q(first_name__icontains=needle)
            | Q(last_name__icontains=needle)
            | Q(email__icontains=needle)
            | Q(username__icontains=needle)
        )

    out: List[Dict[str, Any]] = []
    for u in qs.order_by('-id')[:limit]:
        full = (f'{u.first_name} {u.last_name}').strip() or u.username or u.email
        role = (u.role or 'user').strip()
        out.append({
            'type': 'trainer',  # palette uses one row class; role lives in subtitle
            'id': u.id,
            'title': full,
            'subtitle': f'{role} · {u.email}',
            'url': f'/admin/trainers/{u.id}',
        })
    return out


def _search_projects(needle: str, limit: int) -> List[Dict[str, Any]]:
    """Search ``projects.Project`` rows on title + description."""
    from projects.models import Project

    qs = Project.objects.all()

    if _is_postgres():
        from django.contrib.postgres.search import SearchQuery, SearchVector

        vector = SearchVector('title', 'description', config='simple')
        query = SearchQuery(needle, config='simple', search_type='plain')
        qs = qs.annotate(search=vector).filter(search=query)
    else:
        qs = qs.filter(
            Q(title__icontains=needle) | Q(description__icontains=needle)
        )

    out: List[Dict[str, Any]] = []
    for p in qs.order_by('-id')[:limit]:
        title = (p.title or f'Project #{p.id}').strip()
        out.append({
            'type': 'project',
            'id': p.id,
            'title': title,
            'subtitle': (p.description or '')[:80],
            'url': f'/admin/projects/{p.id}',
        })
    return out


def _search_submissions(needle: str, limit: int) -> List[Dict[str, Any]]:
    """Search annotations by id or by completed_by user name/email.

    Submissions are ``tasks.Annotation`` rows. The corpus the founder
    cares about is "who annotated what" — so we expose annotator email
    + project title in the subtitle.
    """
    from tasks.models import Annotation

    qs = Annotation.objects.select_related('completed_by', 'task', 'task__project')

    # Try numeric id match first ("1023" → Annotation#1023)
    needle_clean = needle.strip()
    id_qs = None
    if needle_clean.lstrip('#').isdigit():
        id_qs = qs.filter(id=int(needle_clean.lstrip('#')))

    if _is_postgres():
        from django.contrib.postgres.search import SearchQuery, SearchVector

        vector = SearchVector(
            'completed_by__first_name',
            'completed_by__last_name',
            'completed_by__email',
            'task__project__title',
            config='simple',
        )
        query = SearchQuery(needle, config='simple', search_type='plain')
        text_qs = qs.annotate(search=vector).filter(search=query)
    else:
        text_qs = qs.filter(
            Q(completed_by__first_name__icontains=needle)
            | Q(completed_by__last_name__icontains=needle)
            | Q(completed_by__email__icontains=needle)
            | Q(task__project__title__icontains=needle)
        )

    if id_qs is not None:
        # Union ids first then text matches — annotator hits second.
        combined = list(id_qs[:limit]) + list(text_qs.exclude(pk__in=id_qs.values_list('pk', flat=True))[:limit])
    else:
        combined = list(text_qs.order_by('-id')[:limit])

    out: List[Dict[str, Any]] = []
    for a in combined[:limit]:
        annotator = ''
        if a.completed_by_id:
            annotator = (
                f'{a.completed_by.first_name} {a.completed_by.last_name}'.strip()
                or a.completed_by.email
                or a.completed_by.username
            )
        proj_title = ''
        if a.task_id and a.task.project_id:
            proj_title = (a.task.project.title or '').strip()
        subtitle = ' · '.join([s for s in (annotator, proj_title) if s])
        out.append({
            'type': 'submission',
            'id': a.id,
            'title': f'Submission #{a.id}',
            'subtitle': subtitle,
            'url': f'/admin/submissions/{a.id}',
        })
    return out


def _search_audit_logs(needle: str, limit: int) -> List[Dict[str, Any]]:
    """Search ``users.AuditLog`` by action + actor email."""
    from users.models import AuditLog

    qs = AuditLog.objects.select_related('user')

    if _is_postgres():
        from django.contrib.postgres.search import SearchQuery, SearchVector

        vector = SearchVector('action', 'user__email', config='simple')
        query = SearchQuery(needle, config='simple', search_type='plain')
        qs = qs.annotate(search=vector).filter(search=query)
    else:
        qs = qs.filter(
            Q(action__icontains=needle) | Q(user__email__icontains=needle)
        )

    out: List[Dict[str, Any]] = []
    for log in qs.order_by('-id')[:limit]:
        actor = (log.user.email if log.user_id and log.user else 'system')
        out.append({
            'type': 'audit',
            'id': log.id,
            'title': f'{log.action} by {actor}',
            'subtitle': str(getattr(log, 'created_at', '') or ''),
            'url': f'/admin/audit?id={log.id}',
        })
    return out


def _search_tasks(needle: str, limit: int) -> List[Dict[str, Any]]:
    """Search ``tasks.Task`` by id or by project title.

    Task ``data`` is JSON — the GIN index in migration 0006 covers
    ``data::text``. On SQLite we fall back to id-only + project-title
    text match (no JSON FTS on SQLite without extensions).
    """
    from tasks.models import Task

    qs = Task.objects.select_related('project')

    needle_clean = needle.strip().lstrip('#')
    id_qs = qs.filter(id=int(needle_clean))[:limit] if needle_clean.isdigit() else qs.none()

    if _is_postgres():
        from django.contrib.postgres.search import SearchQuery, SearchVector

        vector = SearchVector('project__title', config='simple')
        # ``data::text`` cannot be expressed via SearchVector easily without
        # a custom expression; rely on the GIN index from migration 0006
        # for project title + leave deeper JSON search for Phase 3.
        query = SearchQuery(needle, config='simple', search_type='plain')
        text_qs = qs.annotate(search=vector).filter(search=query)
    else:
        text_qs = qs.filter(project__title__icontains=needle)

    combined = list(id_qs) + list(text_qs.exclude(pk__in=id_qs.values_list('pk', flat=True))[:limit])

    out: List[Dict[str, Any]] = []
    for t in combined[:limit]:
        proj_title = ''
        if t.project_id and t.project:
            proj_title = (t.project.title or '').strip()
        out.append({
            'type': 'task',
            'id': t.id,
            'title': f'Task #{t.id}',
            'subtitle': proj_title,
            'url': f'/admin/tasks/{t.id}',
        })
    return out


def _search(q: str, scope: str) -> List[Dict[str, Any]]:
    """Dispatch to the per-scope searchers and merge under the global cap.

    Empty needle → ``[]`` so the frontend "recent searches placeholder"
    flow doesn't bounce.
    """
    needle = (q or '').strip()
    if not needle:
        return []

    results: List[Dict[str, Any]] = []
    remaining = _MAX_RESULTS

    if scope in ('trainers', 'all'):
        cap = _PER_SCOPE_CAP if scope == 'all' else remaining
        trainer_hits = _search_trainers(needle, cap)
        # Plus non-trainer users so admin (Vinod) and reviewers are findable
        # when searching by name. Combined under one scope budget.
        other_hits = _search_admins_and_other_users(needle, max(0, cap - len(trainer_hits)))
        results.extend(trainer_hits + other_hits)
        remaining = _MAX_RESULTS - len(results)
        if scope == 'trainers':
            return results[:_MAX_RESULTS]

    if scope in ('projects', 'all') and remaining > 0:
        cap = _PER_SCOPE_CAP if scope == 'all' else remaining
        results.extend(_search_projects(needle, cap))
        remaining = _MAX_RESULTS - len(results)
        if scope == 'projects':
            return results[:_MAX_RESULTS]

    if scope in ('submissions', 'all') and remaining > 0:
        cap = _PER_SCOPE_CAP if scope == 'all' else remaining
        results.extend(_search_submissions(needle, cap))
        remaining = _MAX_RESULTS - len(results)
        if scope == 'submissions':
            return results[:_MAX_RESULTS]

    if scope in ('audit_logs', 'all') and remaining > 0:
        cap = _PER_SCOPE_CAP if scope == 'all' else remaining
        results.extend(_search_audit_logs(needle, cap))
        remaining = _MAX_RESULTS - len(results)
        if scope == 'audit_logs':
            return results[:_MAX_RESULTS]

    if scope in ('tasks', 'all') and remaining > 0:
        cap = _PER_SCOPE_CAP if scope == 'all' else remaining
        results.extend(_search_tasks(needle, cap))

    return results[:_MAX_RESULTS]


class AdminGlobalSearchAPI(APIView):
    """Admin-only Cmd+K command palette search.

    Returns a flat JSON array (max 50) across trainers, projects,
    submissions, audit logs and tasks. Scope filter narrows to one type.

    Phase 2 WAVE-19: real Django ORM. Postgres uses ``SearchVector`` /
    ``SearchQuery`` against the GIN indexes from migration
    ``0006_fulltext_search_indexes``; SQLite dev / Label-Studio default
    falls back to chained ``icontains`` filters.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=['Admin'],
        summary='Global Cmd+K command palette search',
        description=(
            'Admin-only instant search across trainers, projects, '
            'submissions, audit logs and tasks. Returns up to 50 results. '
            'Empty `q` returns []. Postgres path uses GIN indexes from '
            'migration 0006; SQLite path falls back to icontains.'
        ),
        parameters=[
            OpenApiParameter(
                'q',
                str,
                description='Search term (case-insensitive substring or FTS lexeme).',
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
        return Response(_search(q, scope), status=200)
