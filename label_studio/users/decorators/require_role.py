"""TrainPlex RBAC decorator: require_role.

Enforce role-based access control on DRF view methods.

Usage:
    from users.decorators import require_role

    class MyView(APIView):
        @require_role(['admin', 'qa_lead'])
        def post(self, request):
            ...
"""

from functools import wraps

from rest_framework.exceptions import PermissionDenied


def require_role(allowed_roles):
    """
    Decorator: require user to have one of allowed_roles.
    Use on DRF views: @require_role(['admin', 'qa_lead'])
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Login required")
            if request.user.role not in allowed_roles:
                raise PermissionDenied(
                    f'Required role: {", ".join(allowed_roles)}. Your role: {request.user.role}'
                )
            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator
