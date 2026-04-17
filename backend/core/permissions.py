"""
Role-based permissions for the GlobalStrat simulation.

Since we use a simple username-based auth (no Django auth / tokens),
the caller must pass an X-User-Id header so the backend can look up
the user's role.  The frontend stores user_id in localStorage after
login and attaches it to every request via an axios interceptor.
"""
from rest_framework.permissions import BasePermission
from core.models import User


def _get_role(request):
    """Return the lowercased role for the requesting user, or None."""
    # First, check JWT-authenticated user
    if hasattr(request, 'user') and hasattr(request.user, 'role') and request.user.is_authenticated:
        return (request.user.role or '').lower()
    # Fallback to legacy X-User-Id header
    user_id = request.headers.get('X-User-Id') or request.query_params.get('user_id')
    if not user_id:
        return None
    try:
        user = User.objects.get(user_id=int(user_id))
        return (user.role or '').lower()
    except (User.DoesNotExist, ValueError, TypeError):
        return None


class IsInstructor(BasePermission):
    """Allow only Instructor or Admin roles."""
    message = 'Instructor or Admin access required.'

    def has_permission(self, request, view):
        role = _get_role(request)
        return role in ('instructor', 'admin')


class IsInstructorOrReadOnly(BasePermission):
    """
    Anyone can read (GET, HEAD, OPTIONS).
    Only Instructor/Admin can write (POST, PUT, PATCH, DELETE).
    """
    message = 'Instructor or Admin access required for write operations.'

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        role = _get_role(request)
        return role in ('instructor', 'admin')
