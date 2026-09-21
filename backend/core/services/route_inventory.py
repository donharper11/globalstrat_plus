"""Which registered routes can move competition state, and what guards them.

Built from the URL conf outward, deliberately. The first version of this work
built its inventory by tracing the routes it knew about, and five registered
lifecycle endpoints were simply never looked at — so "every operator action is
on one boundary" was true of the routes that had been examined and false of the
application. An inventory that starts from `urls.py` cannot miss a route
because nobody thought of it.

A route is **lifecycle-mutating** when its view's source writes any model or
field that decides what a round resolves from: the game, the round, team
participation, submission lock state, event state. Every such route must either
go through `core.services.lifecycle.operator_action` (directly, or via an
engine entry point that takes the same lock) or appear in `EXEMPTIONS` with a
reason someone has reviewed.
"""
import ast
import inspect
import json
import pathlib
import re
import sys
import textwrap

from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver


INVENTORY_PATH = str(
    pathlib.Path(__file__).resolve().parent / 'route_inventory.json')

MUTATING_METHODS = ('post', 'put', 'patch', 'delete')

# Models whose rows decide what a round is resolved from.
LIFECYCLE_MODELS = (
    'Game', 'Round', 'Team', 'DecisionSubmission', 'EventInstance',
    'SCEventInstance', 'ActiveModifier', 'ResolutionManifest',
)

# Fields that carry lifecycle state, wherever they are assigned.
LIFECYCLE_FIELDS = (
    'status', 'deadline', 'decisions_locked', 'lock_reason', 'current_round',
    'participation_status', 'locked_at', 'closed_at', 'close_reason',
    'processed_at', 'processing_status', 'round_deadline', 'withdrawn_at',
)

_WRITE_PATTERNS = (
    re.compile(r'\b(?:%s)\.objects\.(?:create|update_or_create|get_or_create|'
               r'bulk_create)\b' % '|'.join(LIFECYCLE_MODELS)),
    re.compile(r'\b(?:%s)\.objects[^\n]*?\.(?:update|delete)\('
               % '|'.join(LIFECYCLE_MODELS)),
    re.compile(r'\.(?:%s)\s*=(?!=)' % '|'.join(LIFECYCLE_FIELDS)),
    # V2-112 moved the Game/Team/Round creates out of `GameCreateView` into
    # `core.services.game_creation.create_game`. This detector reads a view's
    # own source, so without this line the route that creates a whole game
    # would have been re-recorded as not lifecycle-mutating — the writes did
    # not stop, they only moved out of sight. A bare-name match is safe here
    # in the direction that matters: a false positive flags MORE routes.
    re.compile(r'\bcreate_game\('),
    # The same blind spot, found the same way. `GameDeleteView` removes a
    # game's rounds, teams, submissions and events through the module-level
    # helper `_delete_game_cascade`, so none of those deletes are in the view's
    # own source and the route was checked in as `lifecycle_mutating: false` --
    # never an unguarded offender, because it was never counted at all.
    re.compile(r'\b_delete_game_cascade\('),
)

# A bare `.save()` on a lifecycle row rewrites *every* column from whatever the
# in-memory copy held, so a view that merely re-saves a stale Round can undo a
# concurrent status or deadline change without ever assigning to those fields.
# That is a write whether or not the view meant it as one.
_SAVE_PATTERN = re.compile(r'\.save\(')
_MODEL_QUERY = re.compile(r'\b(?:%s)\.objects\b' % '|'.join(LIFECYCLE_MODELS))

# Calling one of these is calling the boundary: each takes the lifecycle lock
# itself, so a view that delegates to one is covered.
#
# The module is part of the marker, not decoration. Matching the bare name as a
# substring cannot tell `core.engine.advance_round.advance_round` from
# `core.services.round_engine.advance_round`: the legacy simulation-control view
# called the second, matched the marker written for the first, and was recorded
# `uses_boundary: true` — which is how an unguarded mutating route was counted
# as guarded. A marker counts only when the name resolves here.
_BOUNDARY_SYMBOLS = {
    'operator_action': ('core.services.lifecycle',),
    'lifecycle_view': ('core.services.lifecycle',),
    'lock_game_for_lifecycle': ('core.services.competition_locks',),
    'close_round': ('core.engine.advance_round',),
    'process_round': ('core.engine.advance_round',),
    'advance_to_next_round': ('core.engine.advance_round',),
    'advance_round': ('core.engine.advance_round',),
    # Student decision writes take the same advisory lock, shared.
    'lock_game_for_decision_write': ('core.services.competition_locks',),
}

# A view inherits the shared-lock guard by subclassing this mixin, so identity
# in the MRO settles it without reading any source.
_BOUNDARY_BASES = ('core.views.decisions.CompetitionDecisionWriteMixin',)


# Reviewed exemptions, keyed by view class so a route rename does not silently
# drop one. A view belongs here only when someone has read it and established
# that its writes cannot change what a round resolves from. The detector is
# deliberately blunt — it flags a lifecycle-model query next to any `.save()`,
# because a bare save rewrites every column — so the exemptions are where the
# judgement lives, and each has to say what was checked.
EXEMPTIONS = {
    'core.views.programs.ProgramViewSet':
        'Writes Program rows. It reaches Round.objects only through '
        'DecisionLockedMixin, which reads Round.decisions_locked to gate '
        'student writes and never assigns to it.',
    'core.views.core.UserViewSet':
        'Writes User rows and User.team. Reads Team.objects to resolve the '
        'assignment target; writes no round, game or participation field.',
    'core.views.scenario_views.GameCreateView':
        'Creates a new Game and its Rounds. There is no existing lifecycle for '
        'the new game to race, and no other game is touched.',
    'core.views.course.TeamManagementView':
        'Assigns enrollments to teams and renames teams. Writes Enrollment and '
        'Team.name; touches no round state and not participation_status.',
}


def _walk(resolver, prefix=''):
    for entry in resolver.url_patterns:
        if isinstance(entry, URLResolver):
            yield from _walk(entry, prefix + str(entry.pattern))
        elif isinstance(entry, URLPattern):
            yield prefix + str(entry.pattern), entry


def _view_source(view_class):
    """The class's own source plus its bases'.

    A view inherits its guard as often as it writes one — the decision write
    path takes the shared lock in a mixin's `dispatch` — so reading only the
    leaf class reports a guarded route as unguarded.
    """
    chunks = []
    for klass in view_class.__mro__:
        if klass.__module__.startswith(('django.', 'rest_framework.')):
            continue
        try:
            chunks.append(inspect.getsource(klass))
        except (OSError, TypeError):
            continue
    return '\n'.join(chunks)


def writes_lifecycle_state(source):
    if any(pattern.search(source) for pattern in _WRITE_PATTERNS):
        return True
    return bool(_SAVE_PATTERN.search(source) and _MODEL_QUERY.search(source))


def generic_lifecycle_writer(view_class):
    """True for a DRF model viewset whose model is a lifecycle model.

    `writes_lifecycle_state` reads source, and a bare `ModelViewSet` has none:
    its create, update and destroy are inherited from the framework, which
    `_view_source` deliberately skips. `TeamViewSet` was exactly that -- three
    lines, `fields = '__all__'` -- and let any instructor PATCH any team's
    cash or participation status while this inventory recorded the route as
    not lifecycle-mutating. Only routes that already have a mutating handler
    reach this, so a `ReadOnlyModelViewSet` is never flagged.
    """
    model = getattr(getattr(view_class, 'queryset', None), 'model', None)
    inherits_writes = any(
        callable(getattr(view_class, name, None))
        for name in ('create', 'update', 'partial_update', 'destroy'))
    return bool(model is not None and inherits_writes
                and model.__name__ in LIFECYCLE_MODELS)


def _local_import_bindings(tree):
    """`name -> module` for every `from X import y` in the parsed source.

    A view that takes the boundary inside a method imports it there, so the
    binding is in the class body rather than the module header.
    """
    bindings = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                bindings[alias.asname or alias.name] = node.module
    return bindings


def _marker_module(klass, name, local_bindings):
    """The module a marker name actually resolves to in `klass`, or None."""
    module = local_bindings.get(name)
    if module is not None:
        return module
    # Not imported in the class body: resolve it the way Python would, through
    # the defining module's globals.
    target = getattr(sys.modules.get(klass.__module__), name, None)
    return getattr(target, '__module__', None) if target is not None else None


def uses_boundary(view_class):
    """True when the view reaches the boundary through the symbol it names.

    Resolution, not text. A name counts only when it resolves to a module that
    takes the lifecycle lock, so a same-named function from another engine no
    longer certifies a route, and a marker that appears only in a comment or a
    docstring — where it is never an `ast.Name` — no longer counts at all.
    """
    for klass in view_class.__mro__:
        if f'{klass.__module__}.{klass.__qualname__}' in _BOUNDARY_BASES:
            return True
    for klass in view_class.__mro__:
        if klass.__module__.startswith(('django.', 'rest_framework.')):
            continue
        try:
            tree = ast.parse(textwrap.dedent(inspect.getsource(klass)))
        except (OSError, TypeError, SyntaxError):
            continue
        local = _local_import_bindings(tree)
        used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        for name in used & set(_BOUNDARY_SYMBOLS):
            if _marker_module(klass, name, local) in _BOUNDARY_SYMBOLS[name]:
                return True
    return False


def mutating_routes():
    """Every registered route with a mutating handler, from the URL conf."""
    routes = {}
    for route, entry in _walk(get_resolver()):
        callback = entry.callback
        view_class = getattr(callback, 'cls', None) or getattr(
            callback, 'view_class', None)
        if view_class is None:
            continue
        actions = getattr(callback, 'actions', None)
        if actions:
            methods = sorted(m for m in actions if m in MUTATING_METHODS)
        else:
            methods = sorted(m for m in MUTATING_METHODS
                             if callable(getattr(view_class, m, None)))
        if not methods:
            continue
        source = _view_source(view_class)
        key = f'{route}|{",".join(methods)}'
        routes[key] = {
            'route': route,
            'methods': methods,
            'view': f'{view_class.__module__}.{view_class.__qualname__}',
            'lifecycle_mutating': (writes_lifecycle_state(source)
                                   or generic_lifecycle_writer(view_class)),
            'uses_boundary': uses_boundary(view_class),
            'exempt': f'{view_class.__module__}.{view_class.__qualname__}'
                      in EXEMPTIONS,
        }
    return dict(sorted(routes.items()))


def unguarded_routes(routes=None):
    """Lifecycle-mutating routes that neither use the boundary nor are exempt."""
    routes = routes if routes is not None else mutating_routes()
    return {key: entry for key, entry in routes.items()
            if entry['lifecycle_mutating'] and not entry['uses_boundary']
            and not entry['exempt']}


def build_inventory():
    routes = mutating_routes()
    lifecycle = {k: v for k, v in routes.items() if v['lifecycle_mutating']}
    return {
        'total_mutating_routes': len(routes),
        'lifecycle_mutating_routes': len(lifecycle),
        'guarded': sum(1 for v in lifecycle.values() if v['uses_boundary']),
        'exempt': sum(1 for v in lifecycle.values()
                      if v['exempt'] and not v['uses_boundary']),
        'unguarded': len(unguarded_routes(routes)),
        'exemptions': dict(sorted(EXEMPTIONS.items())),
        'routes': routes,
    }


def load_inventory():
    return json.loads(pathlib.Path(INVENTORY_PATH).read_text(encoding='utf-8'))
