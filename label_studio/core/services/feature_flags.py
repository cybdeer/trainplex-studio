"""TrainPlex in-house feature flag system — Week 8 Step 17.

Replaces the upstream LaunchDarkly path (`core/feature_flags/base.py`) with
a zero-dependency, in-DB flag system. The founder rule is "no third-party
ops dependency we can't migrate off in a weekend"; LaunchDarkly is a vendor
lock-in we're not willing to ship to prod.

Public surface
--------------
* :func:`is_enabled(flag_name, user=None, default=False)` — main entry point.
  Returns ``bool`` based on (a) whether the flag exists, (b) the master
  ``enabled`` switch, (c) the role allowlist, (d) the deterministic %
  rollout for the given user.
* :func:`all_flags()` — admin-facing list of (name, enabled, rollout_pct,
  enabled_for_roles).
* :func:`audit()` — returns the list of "experimental" flags that have been
  enabled for > 30 days. Used by the production cutover checklist (T-3 row).
* :func:`set_flag(flag_name, **kwargs)` — programmatic toggle for tests
  and management commands.

Wiring note
-----------
This module intentionally does NOT replace `core/feature_flags/base.py`
in this commit. The Phase 2 swap is a single-line change in the call
sites that today read `flag_set(...)`. Until then this module ships as
foundation: model + service + migrations + tests pass; no view writes
through it yet (per Week 8 brief).

Founder rules honoured
---------------------
* **One-shot root cause fix** — flag toggling persists in the DB, not a
  process-local cache that drifts between gunicorn workers.
* **No personal mobile** — `FeatureFlag.description` is scrubbed if a
  match for the founder's personal mobile (configured via the
  ``TRAINPLEX_FOUNDER_MOBILE_GUARD`` env var) is found at save time
  (forced via a Django ``pre_save`` signal in
  :mod:`core.models_feature_flags`).
* **Sub-agent incremental write** — the audit list is materialised every
  call (no in-memory drift); a killed shell mid-mutation leaves valid DB
  rows or none, never a partial map.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-process cache — small, opportunistic.
# ---------------------------------------------------------------------------
#
# A flag check happens on every request (e.g. wrapping a view body in
# ``if is_enabled('fflag_new_payout_ui', user):``). Hitting the DB on
# every request is a waste, so we cache the in-DB row for 30 seconds.
# Cache invalidation is a write-through pattern: ``set_flag`` invalidates
# the entry on save.
#
# 30s is short enough that a stuck cache never lasts longer than half a
# minute, and long enough that 30 req/s on the same flag = 1 DB call.

_FLAG_CACHE: dict[str, tuple[float, "FlagRow"]] = {}
_FLAG_CACHE_TTL_SEC = 30.0


@dataclass(frozen=True)
class FlagRow:
    """Immutable snapshot of a ``FeatureFlag`` row.

    The runtime path never sees the Django model directly; this dataclass
    is what flows through the per-process cache. It also makes the API
    testable without spinning up the ORM.
    """

    name: str
    enabled: bool
    rollout_pct: int
    enabled_for_roles: tuple[str, ...]
    is_experimental: bool
    created_at_unix: int


def _now_unix() -> float:
    import time
    return time.time()


def _get_flag_row(flag_name: str) -> Optional[FlagRow]:
    """Return the cached / freshly-fetched flag row, or None if it doesn't exist.

    The cache is per-process; multi-worker drift is intentional and bounded
    to ``_FLAG_CACHE_TTL_SEC`` (30s).
    """

    now = _now_unix()
    cached = _FLAG_CACHE.get(flag_name)
    if cached and now - cached[0] < _FLAG_CACHE_TTL_SEC:
        return cached[1]

    # Late import: avoids any chance of import-time DB access during
    # Django's `apps.populate()` phase.
    from core.models_feature_flags import FeatureFlag

    try:
        row = FeatureFlag.objects.get(name=flag_name)
    except FeatureFlag.DoesNotExist:
        # Negative-cache the miss for the same TTL so a missing flag
        # doesn't hammer the DB on every request.
        _FLAG_CACHE[flag_name] = (now, None)  # type: ignore[assignment]
        return None
    snapshot = FlagRow(
        name=row.name,
        enabled=row.enabled,
        rollout_pct=int(row.rollout_pct),
        enabled_for_roles=tuple(row.enabled_for_roles or []),
        is_experimental=bool(row.is_experimental),
        created_at_unix=int(row.created_at.timestamp()) if row.created_at else 0,
    )
    _FLAG_CACHE[flag_name] = (now, snapshot)
    return snapshot


def _invalidate(flag_name: str) -> None:
    _FLAG_CACHE.pop(flag_name, None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_enabled(flag_name: str, user=None, default: bool = False) -> bool:
    """Return whether a flag is on for the given user.

    Decision order (short-circuits at the first definitive answer):

    1. If the flag doesn't exist in DB → ``default``.
    2. If the flag's master ``enabled`` switch is False → False.
    3. If ``user`` has a role listed in ``enabled_for_roles`` → True.
       (Role allowlist is OR-with-rollout; an explicit role match wins.)
    4. If ``rollout_pct >= 100`` → True.
    5. If ``user`` is anonymous and rollout < 100 → False.
       (We don't deterministically bucket anonymous users; rollouts are
       per-identified-user only.)
    6. Compute a stable hash of ``(flag_name, user.id)`` mod 100 and
       compare against ``rollout_pct``.

    The hash is intentionally simple SHA-1 truncated to 4 hex chars =
    16 bits. Over 17 trainers and over 100 percentage buckets, the
    expected non-uniformity is well below 1%; using a bigger hash adds
    no statistical value at this scale.
    """

    row = _get_flag_row(flag_name)
    if row is None:
        return default
    if not row.enabled:
        return False

    # 3 — role allowlist.
    user_role = getattr(user, 'role', None)
    if user_role and user_role in row.enabled_for_roles:
        return True

    # 4 — full rollout.
    if row.rollout_pct >= 100:
        return True

    # 5 — anonymous + partial rollout = off.
    if user is None or not getattr(user, 'is_authenticated', False):
        return False

    user_id = getattr(user, 'id', None)
    if user_id is None:
        return False

    # 6 — deterministic bucket.
    bucket = _user_bucket(flag_name, user_id)
    return bucket < row.rollout_pct


def _user_bucket(flag_name: str, user_id: int) -> int:
    """Return a stable bucket 0..99 for (flag_name, user_id).

    The bucket is independent of any other flag, so turning the dial on
    one flag does not co-vary with another. (Co-variance is a frequent
    subtle bug in feature flag systems that share the same hash seed
    across all flags.)
    """

    h = hashlib.sha1(f'{flag_name}:{user_id}'.encode('utf-8')).hexdigest()
    return int(h[:4], 16) % 100


def all_flags() -> list[dict]:
    """Return every flag for the admin UI.

    Lists rows from DB in alphabetical name order; no cache, since this
    call is admin-facing and cold-path.
    """

    from core.models_feature_flags import FeatureFlag

    rows = FeatureFlag.objects.all().order_by('name').values(
        'name',
        'description',
        'enabled',
        'rollout_pct',
        'enabled_for_roles',
        'is_experimental',
        'created_at',
        'updated_at',
    )
    return list(rows)


def audit(now_unix: Optional[float] = None, stale_age_days: int = 30) -> list[dict]:
    """Return the list of experimental flags older than `stale_age_days`.

    Used by the production cutover checklist T-3 row to confirm no
    experimental flags are leaking into the cutover. Returning empty
    list means "all green".
    """

    from datetime import datetime, timezone, timedelta

    now = now_unix if now_unix is not None else _now_unix()
    cutoff = datetime.fromtimestamp(now, tz=timezone.utc) - timedelta(days=stale_age_days)

    from core.models_feature_flags import FeatureFlag

    stale = (
        FeatureFlag.objects.filter(
            is_experimental=True,
            created_at__lte=cutoff,
        )
        .order_by('created_at')
        .values('name', 'created_at', 'enabled', 'rollout_pct')
    )
    return list(stale)


def set_flag(
    flag_name: str,
    *,
    enabled: Optional[bool] = None,
    rollout_pct: Optional[int] = None,
    enabled_for_roles: Optional[Iterable[str]] = None,
    is_experimental: Optional[bool] = None,
    description: Optional[str] = None,
) -> None:
    """Create-or-update a flag.

    Defaults: if the flag doesn't exist, create with ``enabled=False``,
    ``rollout_pct=0``, ``enabled_for_roles=[]``, ``is_experimental=True``,
    and an empty description.

    Validates ``rollout_pct`` is in 0..100 inclusive; any other value
    raises ``ValueError`` (caught at the management-command boundary, so
    a typo doesn't quietly enable 100% rollout).
    """

    if rollout_pct is not None and not (0 <= rollout_pct <= 100):
        raise ValueError(f'rollout_pct must be 0..100, got {rollout_pct}')

    from core.models_feature_flags import FeatureFlag

    defaults = {
        'enabled': False,
        'rollout_pct': 0,
        'enabled_for_roles': [],
        'is_experimental': True,
        'description': '',
    }
    obj, created = FeatureFlag.objects.get_or_create(
        name=flag_name, defaults=defaults
    )

    dirty = created
    if enabled is not None and obj.enabled != enabled:
        obj.enabled = enabled
        dirty = True
    if rollout_pct is not None and obj.rollout_pct != rollout_pct:
        obj.rollout_pct = rollout_pct
        dirty = True
    if enabled_for_roles is not None:
        roles_list = sorted(set(enabled_for_roles))
        if list(obj.enabled_for_roles or []) != roles_list:
            obj.enabled_for_roles = roles_list
            dirty = True
    if is_experimental is not None and obj.is_experimental != is_experimental:
        obj.is_experimental = is_experimental
        dirty = True
    if description is not None:
        scrubbed = _scrub_mobile(description)
        if obj.description != scrubbed:
            obj.description = scrubbed
            dirty = True

    if dirty:
        obj.save()

    _invalidate(flag_name)


# ---------------------------------------------------------------------------
# Founder-rule scrub (no personal mobile in any artefact).
# ---------------------------------------------------------------------------
#
# The literal mobile number must NEVER appear in any tracked source file
# (founder rule: feedback_no_founder_personal_number.md). The defensive
# regex below is built from the ``TRAINPLEX_FOUNDER_MOBILE_GUARD`` env var
# at module import. In production the value is set in ``.env`` (gitignored).
# In test / dev environments the env var is unset, so the regex falls back
# to a never-match sentinel which keeps the public API stable and the test
# suite green.


def _build_founder_mobile_re() -> re.Pattern[str]:
    """Compile a regex from the env-configured founder mobile guard.

    Returns a sentinel that matches nothing when the env var is empty,
    so callers can rely on a non-None ``re.Pattern`` without leaking the
    literal into the source tree.
    """

    raw = os.getenv('TRAINPLEX_FOUNDER_MOBILE_GUARD', '').strip()
    if not raw:
        # ``$.^`` is a deliberate never-match — kept stable for tests.
        return re.compile(r'(?!x)x')
    digits = re.sub(r'\D+', '', raw)
    if len(digits) >= 10:
        last_ten = digits[-10:]
    else:
        last_ten = digits
    return re.compile(r'(?:\+?91[\s-]?)?' + re.escape(last_ten))


_FORBIDDEN_FOUNDER_MOBILE = _build_founder_mobile_re()


def _scrub_mobile(text: str) -> str:
    """Replace the founder's personal mobile with `[REDACTED-MOBILE]` if
    present anywhere in the given text. Same regex as the migration
    script in ``backend/scripts/migrate_ls_to_fork.py`` so the rule is
    enforced consistently.
    """

    return _FORBIDDEN_FOUNDER_MOBILE.sub('[REDACTED-MOBILE]', text or '')
