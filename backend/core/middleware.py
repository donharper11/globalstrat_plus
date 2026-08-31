"""
Cross-cutting request middleware.

SessionHeartbeatMiddleware — keeps UserSession.last_seen_at fresh so the
instructor console can show who is logged in and for how long.

GamePauseGuardMiddleware — makes "pause" mean something. Pausing used to set
Game.status='paused' and nothing more; no student-facing endpoint read it, so
students played straight through a pause. Enforcing it here rather than on
each view means a new student-writable endpoint is covered by default instead
of having to remember to guard it.

TeamScopeGuardMiddleware — stops a student reaching another team's data. Some
40 views take game_id/team_id straight from the URL and had no permission
class at all, so any logged-in student could read (or write) any other team's
briefings, results, forecasts and communications by editing the id in the URL.
Guarding here covers every current and future team-scoped route by
construction, rather than relying on ~40 views each remembering IsTeamMember.

NOTE on identity in middleware: request.user is populated by Django's
AuthenticationMiddleware from the *session*, and this project authenticates
with DRF JWT inside the view — so request.user is anonymous here. Both guards
resolve the caller through core.utils.auth_context, which decodes the bearer
token itself when needed. Middleware that trusts request.user directly is dead
code that silently allows everything.
"""
import logging
from collections import OrderedDict

from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)

# Don't write more than once per this many seconds per session.
TOUCH_INTERVAL_SECONDS = 60

# In-process throttle cache: {session_key: last_write_monotonic}. Per gunicorn
# worker, which is fine — worst case each worker writes once per interval.
# Bounded because gunicorn workers are long-lived and this would otherwise
# grow by one entry per login for the life of the process.
_MAX_TRACKED_SESSIONS = 2048
_last_touch = OrderedDict()


def _remember_touch(key, now):
    """Record a write time, evicting the least recently used entry if full."""
    _last_touch[key] = now
    _last_touch.move_to_end(key)
    while len(_last_touch) > _MAX_TRACKED_SESSIONS:
        _last_touch.popitem(last=False)


class SessionHeartbeatMiddleware:
    """Touch last_seen_at for the requesting user's active session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._touch(request)
        except Exception as e:  # never break a request over telemetry
            logger.debug('Session heartbeat failed: %s', e)
        return response

    def _touch(self, request):
        import time

        path = request.path or ''
        if not path.startswith('/api/'):
            return
        # Login creates its own session row; don't race it.
        if path.endswith('/auth/login/'):
            return

        session_id = request.headers.get('X-Session-Id')
        user_id = request.headers.get('X-User-Id')

        if not session_id and not user_id:
            return

        now = time.monotonic()
        cache_key = session_id or f'u{user_id}'
        last = _last_touch.get(cache_key)
        if last is not None and (now - last) < TOUCH_INTERVAL_SECONDS:
            return

        from core.models.auth_models import UserSession

        session = None
        if session_id:
            session = UserSession.objects.filter(
                pk=session_id, logout_at__isnull=True,
            ).first()
        if session is None and user_id:
            # Fall back to the user's most recent open session.
            try:
                session = UserSession.objects.filter(
                    user_id=int(user_id), logout_at__isnull=True,
                ).order_by('-last_seen_at').first()
            except (TypeError, ValueError):
                return

        if session is None:
            return

        _remember_touch(cache_key, now)
        UserSession.objects.filter(pk=session.pk).update(
            last_seen_at=timezone.now(),
        )


# Paths a student may still write to while the game is paused: authentication
# and personal display preferences. Anything that changes game state must not
# be listed here.
PAUSE_EXEMPT_PREFIXES = (
    '/api/auth/',
    '/api/user/preferences/',
)

BLOCKING_GAME_STATUSES = {
    'paused': ('The game is paused by your instructor. '
               'No changes can be made right now.'),
    'completed': 'This game is complete. No further changes can be made.',
    'archived': 'This game has been archived. No further changes can be made.',
}


class GamePauseGuardMiddleware:
    """Reject student writes to a game that is paused, completed or archived."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            return None

        path = request.path or ''
        if not path.startswith('/api/'):
            return None
        if any(path.startswith(p) for p in PAUSE_EXEMPT_PREFIXES):
            return None

        try:
            return self._check(request, view_kwargs)
        except Exception as e:
            # A failure here must not take the API down; the per-view
            # permission checks still apply.
            logger.warning('Pause guard check failed for %s: %s', path, e)
            return None

    def _check(self, request, view_kwargs):
        from core.utils.auth_context import get_request_role, get_request_user_id

        role = get_request_role(request)
        if role is None:
            # Not authenticated — let the view's own permissions answer.
            return None
        if role in ('instructor', 'admin'):
            return None

        game_id = view_kwargs.get('game_id')
        if game_id is None:
            game_id = self._infer_game_id(get_request_user_id(request))
        if game_id is None:
            return None

        from core.models import Game
        game = Game.objects.filter(pk=game_id).only('status').first()
        if not game:
            return None

        message = BLOCKING_GAME_STATUSES.get(game.status)
        if not message:
            return None

        return JsonResponse(
            {'detail': message, 'game_status': game.status},
            status=403,
        )

    def _infer_game_id(self, user_id):
        """Resolve the game for routes that don't carry game_id in the URL."""
        if not user_id:
            return None
        from core.models import Enrollment, Game

        enrollment = Enrollment.objects.filter(
            user_id=user_id, is_active=True,
        ).exclude(team_id__isnull=True).first()
        if not enrollment:
            return None

        team_id = enrollment.team_id
        game = Game.objects.filter(teams__id=team_id).only('id').first()
        return game.id if game else None


# Team-scoped routes a student may reach for a team that is not theirs.
# Nothing today; kept explicit so an exemption is a deliberate act.
TEAM_SCOPE_EXEMPT_PREFIXES = ()


class TeamScopeGuardMiddleware:
    """Reject a student touching a team they are not a member of."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        team_id = view_kwargs.get('team_id')
        if team_id is None:
            return None

        path = request.path or ''
        if not path.startswith('/api/'):
            return None
        if any(path.startswith(p) for p in TEAM_SCOPE_EXEMPT_PREFIXES):
            return None

        try:
            return self._check(request, team_id)
        except Exception as e:
            # Never take the API down over this; the view's own permission
            # classes still apply.
            logger.warning('Team scope check failed for %s: %s', path, e)
            return None

    def _check(self, request, team_id):
        from core.utils.auth_context import get_request_role, get_request_user_id

        role = get_request_role(request)
        if role is None:
            # Not authenticated — let DRF answer with 401/403.
            return None
        if role in ('instructor', 'admin'):
            return None

        user_id = get_request_user_id(request)
        if user_id is None:
            return None

        if _is_team_member(user_id, team_id):
            return None

        return JsonResponse(
            {'detail': 'You do not have access to this team.'},
            status=403,
        )


def _is_team_member(user_id, team_id):
    """True if this user belongs to the team, via Enrollment or TeamMember."""
    from core.models import Enrollment
    from core.models.core import TeamMember

    try:
        team_id = int(team_id)
    except (TypeError, ValueError):
        return False

    if Enrollment.objects.filter(
        user_id=user_id, team_id=team_id, is_active=True,
    ).exists():
        return True
    return TeamMember.objects.filter(
        team_id=team_id, user_id=user_id,
    ).exists()


class GameScopeGuardMiddleware:
    """Refuse an instructor a game that is not theirs, by default.

    The student equivalent of this is `TeamScopeGuardMiddleware`, which has
    stood since a student could read a rival team by editing the URL. The
    instructor side had no equivalent: each view was expected to call
    `instructor_can_access_game` itself, three handoffs found views that did
    not, and the last scan found ten still open -- including the endpoint that
    returns another cohort's submitted decisions, their payload hashes, the
    actor and the request id.

    Default-deny: a game-scoped instructor route is guarded unless it is listed
    in `game_scope.EXEMPTIONS` with a reason, and a contract test fails when a
    new one is neither. The ownership rule itself is unchanged and is not
    restated here -- `instructor_can_access_game` remains the single
    definition, including its documented unowned-pilot behaviour.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        from core.services.game_scope import (game_id_from,
                                              route_requires_ownership)
        path = request.path or ''
        if not path.startswith('/api/'):
            return None
        match = getattr(request, 'resolver_match', None)
        route = getattr(match, 'route', None)
        if route is None or not route_requires_ownership(route):
            return None

        from core.utils.auth_context import get_request_role
        role = (get_request_role(request) or '').lower()
        if role == 'admin':
            return None
        if role != 'instructor':
            # Not an instructor: the view's own permission classes answer,
            # so an anonymous caller still gets 401 rather than this 403.
            return None

        game_id = game_id_from(match, path)
        if game_id is None:
            return None

        from core.models import Game
        from core.permissions import instructor_can_access_game
        game = Game.objects.filter(pk=game_id).first()
        if game is None:
            return None                       # the view answers 404 itself
        if instructor_can_access_game(request, game):
            return None
        return JsonResponse(
            {'error': 'This game belongs to another instructor.'}, status=403)


class SensitiveReadLogMiddleware:
    """Record every read of a team's raw decisions or of an audit payload.

    Matching is done on the resolved route pattern against
    `core.services.read_inventory`, not on a list of paths kept here. A view
    added later that serves decision rows appears in the inventory the moment
    it is registered, which fails the coverage test until it is either logged
    or exempted on the record — the same shape as the mutating-route boundary.

    Nothing about the response body is stored. The claim this table has to
    answer is "who looked at our decisions", and copying the decisions into a
    second table in order to investigate their disclosure would be a strange
    way to protect them. Tokens and headers are likewise never recorded.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._routes = None

    def _sensitive(self, route):
        if self._routes is None:
            from core.services.read_inventory import logged_route_categories
            self._routes = logged_route_categories()
        return self._routes.get(route)

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._record(request, response)
        except Exception as e:
            # A read that cannot be logged is still a read that happened; the
            # gap is visible in the log rather than as a 500 for the caller.
            logger.warning('Sensitive read logging failed for %s: %s',
                           getattr(request, 'path', '?'), e)
        return response

    def _record(self, request, response):
        match = getattr(request, 'resolver_match', None)
        if match is None or (request.method or '').upper() != 'GET':
            return
        category = self._sensitive(match.route)
        if category is None:
            return

        from core.models import SensitiveReadEvent
        from core.services.lifecycle import request_id_for
        from core.utils.auth_context import get_request_user_id

        status = getattr(response, 'status_code', 0)
        outcome = ('allowed' if status < 400
                   else 'denied' if status in (401, 403, 404) else 'error')
        user_id = None
        username = ''
        try:
            user_id = get_request_user_id(request)
            if user_id is not None:
                from core.models import User
                username = (User.objects.filter(pk=user_id)
                            .values_list('username', flat=True).first() or '')
        except Exception:
            # An unidentifiable caller is recorded as one, not dropped.
            pass

        SensitiveReadEvent.objects.create(
            actor_user_id=user_id,
            username=username,
            game_id_read=_as_int(match.kwargs.get('game_id')),
            team_id_read=_as_int(match.kwargs.get('team_id')),
            round_number_read=_as_int(
                match.kwargs.get('round_number')
                or request.GET.get('round_number')
                or request.GET.get('round')),
            category=category,
            route=match.route[:255],
            endpoint=(request.path or '')[:255],
            method='GET',
            status_code=status,
            outcome=outcome,
            request_id=request_id_for(request),
        )


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
