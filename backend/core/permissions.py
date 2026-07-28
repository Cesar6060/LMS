"""Cross-app permission classes (app-specific ones live in courses/permissions.py)."""

from rest_framework import permissions

from core.demo import require_not_demo


class NotDemoAccountForWrites(permissions.BasePermission):
    """Deny unsafe methods for the shared demo account.

    For class-based views we can't edit method-by-method — currently the
    dj-rest-auth UserDetailsView shadow at /api/auth/user/. Function-based
    views call core.demo.require_not_demo directly at their write branches
    instead. Raises (rather than returns False) so the response body is the
    standard demo_blocked contract, not DRF's default detail-only shape.
    """

    def has_permission(self, request, view):
        if request.method not in permissions.SAFE_METHODS:
            require_not_demo(request.user)
        return True
