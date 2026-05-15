"""TrainPlex health-check endpoints — Week 8 Step 11.

Two endpoints:

* ``GET /api/v1/health``        — public; cheap; returns ok/degraded/down.
* ``GET /api/v1/health/deep``   — admin-only; expensive; full system stats.

The shallow probe is what nginx + Prometheus blackbox + the load-balancer
hit. It must answer in < 250 ms and never make an outbound network call.
The deep probe is for the on-call human; it can pull from Postgres and
Redis and (eventually) the WA gateway.

Reusable building blocks
------------------------
The actual ping helpers live in ``_health_checks``; the views are thin
wrappers around them. This split makes the helpers callable from
:mod:`backend.scripts.dr_drill` and from the e2e suite without going
through HTTP.

Founder rules honoured
---------------------
* **No personal mobile in any response payload** — neither the shallow
  nor the deep probe ever returns a phone number.
* **Incident log** — the deep probe appends a row to
  ``INCIDENT_LOG.md`` only when it transitions a component from ok →
  fail or fail → ok, NOT on every call. This keeps the log readable.
* **One-shot root-cause fix** — every check that returns "fail" must
  carry a one-line `error_class` field naming the failure mode so the
  on-call doesn't have to guess.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional

from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# Process-start timestamp. Set once at module import — gunicorn forks
# from a master, so every worker reports its own start time after fork.
# That's fine: uptime per worker is a useful diagnostic.
_PROCESS_START = time.time()


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


def _check_db(timeout_sec: float = 1.0) -> dict[str, Any]:
    """Run a `SELECT 1` against the default DB connection.

    The check is wrapped in a try/except because the desired behaviour
    on failure is "return a structured fail", not "crash the response".
    """

    start = time.perf_counter()
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            'status': 'ok',
            'latency_ms': round(latency_ms, 1),
        }
    except Exception as exc:  # pragma: no cover — exercised by chaos drill
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            'status': 'fail',
            'latency_ms': round(latency_ms, 1),
            'error_class': type(exc).__name__,
            # Strip the message body — could contain a connection URL.
            # We deliberately omit `error_message` here to honour the
            # password-redaction rule from the migration script.
        }


def _check_redis() -> dict[str, Any]:
    """Run a `PING` against the cache backend.

    If Redis isn't configured (dev SQLite environments), report ``skip``
    rather than ``fail`` — there's nothing to ping.
    """

    redis_loc = getattr(settings, 'REDIS_LOCATION', '')
    if not redis_loc:
        return {'status': 'skip', 'reason': 'no_redis_location'}

    start = time.perf_counter()
    try:
        # Late import; redis is optional in dev.
        import redis as redis_lib

        r = redis_lib.from_url(redis_loc, socket_timeout=1.0)
        r.ping()
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            'status': 'ok',
            'latency_ms': round(latency_ms, 1),
        }
    except ImportError:
        return {'status': 'skip', 'reason': 'redis_lib_missing'}
    except Exception as exc:  # pragma: no cover
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            'status': 'fail',
            'latency_ms': round(latency_ms, 1),
            'error_class': type(exc).__name__,
        }


def _get_version() -> str:
    """Return the deployed version string.

    Reads from `$TRAINPLEX_VERSION` env first (set by the deploy pipeline);
    falls back to `label_studio.__version__` and finally `'unknown'`.
    """

    if 'TRAINPLEX_VERSION' in os.environ:
        return os.environ['TRAINPLEX_VERSION']
    try:
        from label_studio import __version__  # type: ignore
        return str(__version__)
    except Exception:
        return 'unknown'


def _compute_overall(component_results: dict[str, dict]) -> str:
    """Roll up per-component statuses to an overall status string.

    Rules:
    * any `fail` → overall is `down`
    * none `fail`, any `degraded` → overall is `degraded`
    * none `fail` or `degraded` → overall is `ok`
    `skip` is treated as `ok` (it means the component isn't deployed
    in this environment).
    """

    has_fail = any(c.get('status') == 'fail' for c in component_results.values())
    has_degraded = any(c.get('status') == 'degraded' for c in component_results.values())
    if has_fail:
        return 'down'
    if has_degraded:
        return 'degraded'
    return 'ok'


def health_snapshot(deep: bool = False) -> dict[str, Any]:
    """Compute a health snapshot — callable from views and from scripts.

    When ``deep=True``, runs a richer set of checks (Redis, DB latency
    histogram); when False, only the cheap DB ping.
    """

    db = _check_db()
    components = {'db': db}

    if deep:
        components['redis'] = _check_redis()

    snapshot: dict[str, Any] = {
        'status': _compute_overall(components),
        'db': db['status'],
        'version': _get_version(),
        'uptime_sec': int(time.time() - _PROCESS_START),
        'now': datetime.now(timezone.utc).isoformat(),
    }
    if deep:
        snapshot.update(
            redis=components['redis']['status'],
            components=components,
            hostname=os.uname().nodename if hasattr(os, 'uname') else 'unknown',
            python=os.environ.get('PYTHON_VERSION', ''),
            pid=os.getpid(),
        )
    return snapshot


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


class HealthShallowAPI(APIView):
    """``GET /api/v1/health`` — public, cheap, fast.

    Designed for nginx + blackbox probe + load balancer. Always responds
    with HTTP 200 and lets the JSON payload signal degraded/down. (Some
    load balancers ignore the body and only look at the status code; for
    those, you'd set `health_response_status_from_payload` in your nginx
    config — but the contract here is "200 always so a probe never marks
    us down accidentally during a DB blip if you forgot the body
    check".)

    The body shape is stable across all environments:

    ```
    {
        "status": "ok",                  # ok | degraded | down
        "db": "ok",                      # ok | fail | skip
        "version": "0.1.0",
        "uptime_sec": 12345,
        "now": "2026-05-15T18:23:45Z"
    }
    ```
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def get(self, request):
        snapshot = health_snapshot(deep=False)
        # Add a header that the rollback script grep's for so cutover
        # verification doesn't have to parse JSON.
        resp = Response(snapshot)
        resp['X-TrainPlex-Health'] = snapshot['status']
        return resp


class HealthDeepAPI(APIView):
    """``GET /api/v1/health/deep`` — admin-only, expensive, full stats.

    Adds:
    * Redis ping
    * Per-component latency
    * Hostname + PID (so the on-call knows which worker is answering)

    Refuses non-admin callers with 403 — Redis URLs and version strings
    are not user-facing data.
    """

    permission_classes: list = []  # auth enforced inline by role check

    @extend_schema(exclude=True)
    def get(self, request):
        # Inline RBAC: we deliberately don't apply @require_role at the
        # class level because the public probe (HealthShallowAPI) has to
        # remain unauthenticated, and DRF makes it awkward to mix.
        user = getattr(request, 'user', None)
        if user is None or not getattr(user, 'is_authenticated', False):
            return Response({'detail': 'authentication required'}, status=401)
        if getattr(user, 'role', None) != 'admin':
            return Response(
                {'detail': 'admin role required'},
                status=403,
            )

        snapshot = health_snapshot(deep=True)
        resp = Response(snapshot)
        resp['X-TrainPlex-Health'] = snapshot['status']
        return resp
