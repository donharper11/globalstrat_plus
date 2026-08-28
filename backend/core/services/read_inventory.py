"""Which registered routes can disclose a team's raw decisions or an audit payload.

Built from the URL conf and the model registry outward, for the same reason
`route_inventory` is: an inventory assembled by listing the endpoints somebody
remembered will always be complete with respect to the endpoints somebody
remembered. A team asking "who saw our Round 3 decisions?" is owed an answer
that covers every route the application actually serves.

A read route is **sensitive** when its view's source reads a model that stores
participant-written decisions (`category='decisions'`) or one of the append-only
audit records (`category='audit'`). Every sensitive route is logged by
`core.middleware.sensitive_reads.SensitiveReadLogMiddleware`, which matches on
the resolved route pattern, so a new view is covered the moment it is
registered. Routes that only mention such a model incidentally appear in
`EXEMPTIONS` with a reason someone has reviewed.
"""
import ast
import inspect
import json
import logging
import pathlib
import re
import sys

from django.apps import apps
from django.urls import get_resolver

from core.services.route_inventory import _view_source, _walk

INVENTORY_PATH = str(
    pathlib.Path(__file__).resolve().parent / 'read_inventory.json')

READ_METHODS = ('get',)
VIEWSET_READ_ACTIONS = ('list', 'retrieve')

# The append-only records themselves. Reading one of these discloses the audit
# payload, which is a stronger disclosure than reading the decision it records.
AUDIT_MODELS = ('DecisionAuditEvent', 'OperatorAuditEvent', 'ResolutionManifest')

# Views that name a decision or audit model but cannot disclose one. Keyed by
# `module.ClassName` so a rename is a review event rather than a silent
# re-exemption.
EXEMPTIONS = {
    'round_control.RoundControlView':
        'Reads OperatorAuditEvent only to count operator actions for the '
        'round-status block. No audit row, payload or decision is serialized; '
        'the lifecycle boundary already records the writes it reports.',
}


def decision_models():
    """Every registered model that stores a participant-written decision.

    Taken from the app registry rather than a hand-kept list: `DecisionTalent`,
    `SourcingDecision` and the legacy `programs.Decision` are all decisions a
    team submitted, and all three arrived in the codebase at different times.
    """
    names = set()
    for model in apps.get_models():
        name = model.__name__
        if name in AUDIT_MODELS:
            continue
        if name.startswith('Decision') or name.endswith('Decision'):
            names.add(name)
    return tuple(sorted(names))


def _read_methods(callback, view_class):
    actions = getattr(callback, 'actions', None)
    if actions:
        return tuple(sorted({http for http, action in actions.items()
                             if action in VIEWSET_READ_ACTIONS}))
    return tuple(m for m in READ_METHODS if callable(getattr(view_class, m, None)))


def _models_read(source, names):
    return tuple(sorted({n for n in names if _mentions(source, n)}))


def _mentions(source, name):
    """Whole-identifier match.

    A substring test flags `DecisionLockedMixin` and `DecisionStatusView` as
    reads of the `Decision` model, which puts two views that serve no decision
    rows on a list whose value depends on every row being real.
    """
    return re.search(r'\b%s\b' % re.escape(name), source) is not None


def _helper_source(view_class):
    """Module-level helpers the view calls, by name.

    `RoundControlView` reads `OperatorAuditEvent` inside a module function
    rather than in the class body. Reading only the class would report the
    route as touching no audit record, which is how an inventory built from
    the wrong unit of code misses the endpoint it exists to find.
    """
    chunks = []
    seen = set()
    for klass in view_class.__mro__:
        module = sys.modules.get(klass.__module__)
        if module is None or klass.__module__.startswith(
                ('django.', 'rest_framework.')):
            continue
        try:
            class_source = inspect.getsource(klass)
            module_source = inspect.getsource(module)
        except (OSError, TypeError):
            continue
        try:
            tree = ast.parse(module_source)
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            key = (klass.__module__, node.name)
            if key in seen or not _mentions(class_source, node.name):
                continue
            seen.add(key)
            chunks.append(ast.get_source_segment(module_source, node) or '')
    return '\n'.join(chunks)


def sensitive_routes():
    """Every registered read route that can disclose decisions or audit rows."""
    names = decision_models()
    rows = []
    for route, entry in _walk(get_resolver()):
        callback = entry.callback
        view_class = (getattr(callback, 'cls', None)
                      or getattr(callback, 'view_class', None))
        if view_class is None:
            continue
        methods = _read_methods(callback, view_class)
        if not methods:
            continue
        source = _view_source(view_class) + '\n' + _helper_source(view_class)
        audit = _models_read(source, AUDIT_MODELS)
        decisions = _models_read(source, names)
        if not audit and not decisions:
            continue
        key = f'{view_class.__module__.rsplit(".", 1)[-1]}.{view_class.__name__}'
        rows.append({
            'route': route,
            'view': key,
            'methods': list(methods),
            'category': 'audit' if audit else 'decisions',
            'models': list(audit + decisions),
            'exempt_reason': EXEMPTIONS.get(key, ''),
            'logged': key not in EXEMPTIONS,
        })
    rows.sort(key=lambda row: (row['route'], row['view']))
    return rows


def logged_routes():
    """The route patterns the middleware must record a read event for.

    Read from the generated file rather than rebuilt. Rebuilding reads and
    parses the source of every registered view, which measured 6.3 seconds —
    a cost the first student to open a decision page in each worker process
    would otherwise have paid.

    The file is not trusted blindly. The URL conf is walked, which is cheap
    because it reads no source, and if the number of registered routes has
    moved since the file was written then the file is stale and the live scan
    runs instead. That covers the drift that actually happens — a route added
    or removed without regenerating the inventory — and the guard test covers
    the rest.
    """
    try:
        inventory = load_inventory()
        recorded = inventory.get('url_conf_route_count')
        live = registered_route_count()
        if recorded is not None and recorded == live:
            return {row['route'] for row in inventory['routes'] if row['logged']}
        logging.getLogger(__name__).warning(
            'read_inventory.json is stale (%s routes recorded, %s registered); '
            'rebuilding. Run manage.py dump_read_inventory.', recorded, live)
    except (OSError, ValueError, KeyError) as error:
        logging.getLogger(__name__).warning(
            'read_inventory.json unusable (%s); rebuilding from the URL conf.',
            error)
    return {row['route'] for row in sensitive_routes() if row['logged']}


def registered_route_count():
    """How many routes the URL conf serves. Cheap: no source is read."""
    return sum(1 for _ in _walk(get_resolver()))


def build_inventory():
    rows = sensitive_routes()
    return {
        'decision_models': list(decision_models()),
        # Recorded so the middleware can trust the generated file without
        # rebuilding it. See `logged_routes()`.
        'url_conf_route_count': registered_route_count(),
        'audit_models': list(AUDIT_MODELS),
        'total_sensitive_routes': len(rows),
        'audit_routes': sum(1 for r in rows if r['category'] == 'audit'),
        'decision_routes': sum(1 for r in rows if r['category'] == 'decisions'),
        'logged': sum(1 for r in rows if r['logged']),
        'exempt': sum(1 for r in rows if not r['logged']),
        'routes': rows,
    }


def load_inventory():
    return json.loads(
        pathlib.Path(INVENTORY_PATH).read_text(encoding='utf-8'))
