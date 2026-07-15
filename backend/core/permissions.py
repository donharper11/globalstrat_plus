"""
Role-based permissions for the GlobalStrat simulation.

Identity comes from the signed JWT issued at login (see core.authentication).
An earlier version trusted an unverified X-User-Id header / ?user_id= param,
which allowed anyone to act as any user; see core.utils.auth_context.
"""
from rest_framework.permissions import BasePermission

from core.utils.auth_context import get_request_role


def _get_role(request):
    """Return the lowercased role for the authenticated caller, or None."""
    return get_request_role(request)


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


class GameIsNotPaused(BasePermission):
    """
    Block student writes while the instructor has paused the game.

    Pausing previously only set Game.status='paused' — nothing read it, so
    students could keep playing through a pause. Instructors are exempt so
    they can still administer a paused game.
    """
    message = 'The game is paused by your instructor. No changes can be made right now.'

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        if _get_role(request) in ('instructor', 'admin'):
            return True

        game_id = view.kwargs.get('game_id')
        if not game_id:
            return True

        from core.models import Game
        game = Game.objects.filter(pk=game_id).only('status').first()
        if not game:
            return True

        if game.status == 'paused':
            return False
        if game.status in ('completed', 'archived'):
            self.message = f'This game is {game.status}. No further changes can be made.'
            return False
        return True
