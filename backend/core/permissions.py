"""
Role-based permissions for the GlobalStrat simulation.

Identity comes from the signed JWT issued at login (see core.authentication).
An earlier version trusted an unverified X-User-Id header / ?user_id= param,
which allowed anyone to act as any user; see core.utils.auth_context.
"""
from rest_framework.permissions import BasePermission

from core.utils.auth_context import get_request_role


def _say(request, key):
    """A refusal sentence in the caller's language.

    A DRF permission's `message` is the `detail` of the 403 it causes. These
    were class-level English literals; DRF builds a fresh permission object for
    every request, so setting it per request is safe.
    """
    from core.utils.participant_messages import (
        language_for_request, participant_message)
    return participant_message(key, language=language_for_request(request))


def _get_role(request):
    """Return the lowercased role for the authenticated caller, or None."""
    return get_request_role(request)


class IsInstructor(BasePermission):
    """Allow only Instructor or Admin roles."""

    def has_permission(self, request, view):
        self.message = _say(request, 'instructor_access_required')
        role = _get_role(request)
        return role in ('instructor', 'admin')


class IsInstructorOrReadOnly(BasePermission):
    """
    Any authenticated user can read (GET, HEAD, OPTIONS).
    Only Instructor/Admin can write (POST, PUT, PATCH, DELETE).

    Reads used to return True unconditionally, which meant "anyone" literally
    — including anonymous callers, since this permission short-circuits the
    project default. /api/teams/ served every team's cash position, debt and
    equity to the open internet. A read now still requires a login.
    """

    def has_permission(self, request, view):
        self.message = _say(request, 'instructor_write_required')
        role = _get_role(request)
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            # Authenticated, any role.
            return role is not None
        return role in ('instructor', 'admin')


def instructor_can_access_game(request, game):
    """Whether this instructor may read a specific game's data.

    `IsInstructor` only checks the role, so any instructor could read any
    game. Narrative job metadata carries a model name, an endpoint and error
    text, so it is scoped to the cohort that owns the game.

    Ownership follows the rule already used for student accounts: a game
    belongs to the instructor who owns the course behind its section, and a
    course with no `instructor_id` is unowned and visible to any instructor.
    Course.instructor_id is genuinely NULL for the live pilot cohort, so
    scoping strictly to owned courses would hide those games from everyone.
    """
    role = (get_request_role(request) or '').lower()
    if role == 'admin':
        return True
    if role != 'instructor':
        return False

    from core.models.course import Course, Section

    section = Section.objects.filter(section_id=game.section_id).first()
    if section is None:
        return True                     # no cohort recorded: unowned
    course = Course.objects.filter(course_id=section.course_id).first()
    if course is None or course.instructor_id is None:
        return True                     # unowned course: any instructor
    # Identity comes from the same helper the role check uses, which reads the
    # verified JWT and falls back to it when `request.user` is not populated.
    # This previously read `request.user.user_id` directly, which is only set
    # once DRF authentication has run inside the view -- so the rule returned
    # False for the rightful owner when called from the middleware boundary
    # that now enforces it for every game-scoped instructor route.
    from core.utils.auth_context import get_request_user_id
    return get_request_user_id(request) == course.instructor_id


def instructor_can_access_course(request, course):
    """Whether this caller may read or change a course and what hangs off it.

    The same rule as `instructor_can_access_game`, asked of the course itself
    because the roster, team-assignment, course and section routes name no
    game: an admin always; a course with no `instructor_id` is the shared pilot
    cohort and any instructor may work in it; otherwise only its instructor of
    record.
    """
    role = (get_request_role(request) or '').lower()
    if role == 'admin':
        return True
    if role != 'instructor':
        return False
    if course is None or course.instructor_id is None:
        return True
    from core.utils.auth_context import get_request_user_id
    return get_request_user_id(request) == course.instructor_id


def instructor_can_access_section(request, section):
    """`instructor_can_access_course`, reached from a section."""
    from core.models.course import Course
    course = None
    if section is not None:
        course = Course.objects.filter(course_id=section.course_id).first()
    return instructor_can_access_course(request, course)


class GameIsNotPaused(BasePermission):
    """
    Block student writes while the instructor has paused the game.

    Pausing previously only set Game.status='paused' — nothing read it, so
    students could keep playing through a pause. Instructors are exempt so
    they can still administer a paused game.
    """

    def has_permission(self, request, view):
        self.message = _say(request, 'game_paused')
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
            self.message = _say(request, 'game_finished')
            return False
        return True
