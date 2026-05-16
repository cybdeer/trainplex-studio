"""TrainPlex RBAC decorator: require_role.

Enforce role-based access control on DRF view methods.

Usage:
    from users.decorators import require_role

    class MyView(APIView):
        @require_role(["admin", "qa_lead"])
        def post(self, request):
            ...

Admin / superuser auto-bypass: per TrainPlex policy admin has access to
every role-gated endpoint (read + write). Superuser additionally bypasses
authentication checks for ops/diagnostic flows.

Tonight-only trainer allowlist (WAVE-19, 2026-05-16)
----------------------------------------------------
The ``/trainer/batch`` landing surface is gated behind a tiny allowlist
(ceo email + admin/superuser) until the founder green-lights wider
rollout. The helper ``_trainer_gate_open`` is consumed by
``tasks.api_batch.TrainerBatchAPI`` and friends so other trainer
endpoints continue to work for the rest of the dogfood cohort.

The allowlist is overridable at runtime via the
``TRAINPLEX_TRAINER_ALLOWLIST`` env var (comma-separated emails). The
default keeps the ceo + founder addresses open so view-testing never
gets locked out.
"""

import os
from functools import wraps

from rest_framework.exceptions import PermissionDenied


# --------------------------------------------------------------------------
# Trainer batch allowlist (tonight only)
# --------------------------------------------------------------------------

_DEFAULT_ALLOWLIST = "ceo@cybdeer.com,vk.vinodparihar1@gmail.com"

_TRAINER_ALLOWLIST = {
    e.strip().lower()
    for e in os.getenv("TRAINPLEX_TRAINER_ALLOWLIST", _DEFAULT_ALLOWLIST).split(",")
    if e.strip()
}


def _trainer_gate_open(user) -> bool:
    """Return True when ``user`` may see the trainer batch landing.

    Admin / superuser always pass — they need it to view-test. Everyone
    else must match the allowlist by email (case-insensitive).
    """
    if getattr(user, "is_superuser", False):
        return True
    if getattr(user, "role", None) == "admin":
        return True
    email = (getattr(user, "email", "") or "").lower()
    return email in _TRAINER_ALLOWLIST


# --------------------------------------------------------------------------
# Standard role decorator
# --------------------------------------------------------------------------


def require_role(allowed_roles):
    """
    Decorator: require user to have one of allowed_roles, OR be admin/superuser.

    Admin and Django superusers ALWAYS pass — TrainPlex policy treats admin
    as the union of all role privileges (trainer/reviewer/qa_lead). This
    lets the founder view-test every endpoint without role-juggling.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Login required")

            # Admin / superuser auto-bypass (root-fix for view-testing + ops)
            if getattr(request.user, "is_superuser", False):
                return view_func(self, request, *args, **kwargs)
            if getattr(request.user, "role", None) == "admin":
                return view_func(self, request, *args, **kwargs)

            if request.user.role not in allowed_roles:
                joined = ", ".join(allowed_roles)
                raise PermissionDenied(
                    f"Required role: {joined}. Your role: {request.user.role}"
                )
            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator
