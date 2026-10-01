"""Role checks used on every protected view.

- Not logged in  -> redirected to the login page.
- Wrong role     -> 403 "Access denied" page.
"""
from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Decorator for function-based views: @role_required(Role.STAFF, Role.ADMIN)."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not request.user.has_role(*roles):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


class RoleRequiredMixin(AccessMixin):
    """Mixin for class-based views: set `allowed_roles = [Role.CUSTOMER]`."""

    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()  # redirects to login
        if not request.user.has_role(*self.allowed_roles):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
