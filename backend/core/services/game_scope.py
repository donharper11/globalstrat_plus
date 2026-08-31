"""Which routes are game-scoped instructor routes, and who may reach them.

Three separate handoffs found the same defect: a view declared `IsInstructor`,
which checks the caller's role and nothing else, and any instructor account
could then read or act on any cohort by changing the game id in the URL.
V2-007's rework fixed one endpoint, CRV2-07's authorization FAIL fixed another,
and CRV2-08's scan found ten more still open. Fixing the eleventh view the same
way would leave the twelfth.

So ownership is enforced once, at a boundary every game-scoped instructor route
passes through, and this module decides which routes those are. The inventory
is built from the registered URL patterns rather than from a hand-kept list, so
a route added tomorrow is covered the day it is registered, and a route that
must not be covered has to say so here with a reason.

Role authentication and game ownership stay distinct: `IsInstructor` answers
"is this an instructor", this boundary answers "is this their game".
"""
import re

from django.urls import URLPattern, URLResolver, get_resolver

# Routes that carry a game id and are reached by instructors, but must not be
# ownership-scoped. Each entry needs a reason that survives review; "it only
# returns reference data" is not one unless the response genuinely cannot
# differ between cohorts.
EXEMPTIONS = {}

# Views whose permission classes name an instructor role. Both spellings exist:
# `core.permissions.IsInstructor` and a second class of the same name in
# `core.views.decisions`, which is why this matches on the name.
_INSTRUCTOR_PERMISSION_NAMES = ('IsInstructor', 'IsInstructorOrAdmin')


def _iter_patterns(resolver=None, prefix=''):
    resolver = resolver or get_resolver()
    for entry in resolver.url_patterns:
        if isinstance(entry, URLResolver):
            yield from _iter_patterns(entry, prefix + str(entry.pattern))
        elif isinstance(entry, URLPattern):
            yield prefix + str(entry.pattern), entry


def _view_class(pattern):
    callback = pattern.callback
    return getattr(callback, 'cls', getattr(callback, 'view_class', None))


def _requires_instructor(view_class):
    if view_class is None:
        return False
    for permission in getattr(view_class, 'permission_classes', []) or []:
        if getattr(permission, '__name__', '') in _INSTRUCTOR_PERMISSION_NAMES:
            return True
    return False


_CACHE = None


def game_scoped_instructor_routes(refresh=False):
    """Every registered route that names a game.

    Returns `{route: {'view': 'module.Class', 'methods': [...],
    'exempt': bool, 'exempt_reason': str}}`.

    Cached: this walks every registered URL pattern, and the guard consults it
    on each request. The URL conf does not change within a process.
    """
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    routes = {}
    for route, pattern in _iter_patterns():
        if 'game_id' not in route:
            continue
        # Every route naming a game, not only those that already declare an
        # instructor permission. The first version of this filtered on
        # `permission_classes` containing IsInstructor, and missed
        # /instructor/alerts/ -- which declares no permission classes at all,
        # was therefore never inventoried, never guarded, and went on
        # disclosing another cohort's alerts. An inventory that asks views
        # whether they are protected can only ever find the protected ones.
        #
        # The guard only acts on instructor callers, so student routes that
        # name a game are unaffected; those are the team boundary's business.
        view_class = _view_class(pattern)
        methods = sorted(
            m.upper() for m in ('get', 'post', 'put', 'patch', 'delete')
            if view_class is not None and hasattr(view_class, m))
        name = (f'{view_class.__module__.rsplit(".", 1)[-1]}.{view_class.__name__}'
                if view_class is not None else str(pattern.callback))
        routes[route] = {
            'view': name,
            'declares_instructor_permission': _requires_instructor(view_class),
            'methods': methods,
            'exempt': route in EXEMPTIONS,
            'exempt_reason': EXEMPTIONS.get(route, ''),
        }
    _CACHE = routes
    return routes


def route_requires_ownership(route):
    """True when this resolved route pattern must be ownership-checked."""
    if route in EXEMPTIONS:
        return False
    return route in game_scoped_instructor_routes()


_GAME_ID_RE = re.compile(r'games/(\d+)/')


def game_id_from(match, path):
    value = (match.kwargs or {}).get('game_id') if match else None
    if value is None:
        found = _GAME_ID_RE.search(path or '')
        value = found.group(1) if found else None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
