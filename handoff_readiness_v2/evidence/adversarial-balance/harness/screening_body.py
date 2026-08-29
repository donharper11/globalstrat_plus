"""Stage 2 — sensitivity screening by same-game transactional counterfactual.

Every dimension is measured by resolving the same game, the same round and the
same team twice from one frozen checkpoint: once on the documented baseline and
once with exactly one decision dimension changed. Both roll back, so the second
run starts from the identical state the first did.

The harness refuses to produce evidence unless three self-tests pass first:
a baseline against an identical baseline must give a delta of exactly zero, a
known responsive field must move, and a field the engine never reads must not.
Two of those are there because the previous version of this screen reported
every dimension as responsive and I believed it.

Output that is entirely flat or entirely responsive is refused as well. Either
shape means the instrument is not discriminating, whatever the numbers say.
"""
import json
import time
from decimal import Decimal as D

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.utils import timezone

import baseline as BASE
import counterfactual as CF

SCREEN_SEED = 'crv2-06-screen-2-counterfactual'
CASH = D('60000000')

NOT_SCREENED = {
    'reference': 'a foreign key naming which product, market, platform or '
                 'feature the row is about. Which entity a decision targets is '
                 'a strategy choice for Stage 3 search, not a magnitude with a '
                 'response curve.',
    'json': 'free-form structure. `campaign_focus_feature_ids` is bounded by '
            'its 1-3 length rule and covered as a cross-row control; the rest '
            'carry channel detail rather than a scalar.',
    'text': 'a name or note. No effect on scoring.',
}

# Decision types whose only dimensions are references — which target the row
# names — and are therefore covered by the `reference` rule rather than needing
# a baseline row of their own.
REFERENCE_ONLY_TYPES = {'acquisitions', 'event-responses'}

MODEL_FOR = {
    'budget': ('core.models.decisions', 'DecisionBudgetAllocation'),
    'esg': ('core.models.decisions', 'DecisionESG'),
    'financing': ('core.models.decisions', 'DecisionFinancing'),
    'marketing': ('core.models.decisions', 'DecisionMarketing'),
    'talent': ('core.models.talent', 'DecisionTalent'),
    'rd': ('core.models.decisions', 'DecisionRDInvestment'),
    'plants': ('core.models.decisions', 'DecisionPlant'),
    'partnerships': ('core.models.decisions', 'DecisionPartnership'),
    'market-entry': ('core.models.decisions', 'DecisionMarketEntry'),
    'platforms': ('core.models.decisions', 'DecisionPlatformDevelopment'),
    'products': ('core.models.decisions', 'DecisionProductCreate'),
    'product-retires': ('core.models.decisions', 'DecisionProductRetire'),
}

# Every decision type the plan can screen must resolve to a model here, or its
# probes land nowhere and the coverage gate refuses the run. Checked at import
# rather than discovered ten minutes into a screen.
def _assert_model_map_covers_plan():
    from core.views.decisions import _TYPE_MAP
    missing = sorted(set(_TYPE_MAP) - set(MODEL_FOR) - REFERENCE_ONLY_TYPES)
    if missing:
        raise AssertionError(
            f'MODEL_FOR has no entry for {missing}; their probes cannot be '
            f'applied and the screen would refuse to write evidence')


def probe_plan(inventory):
    plan = []
    for decision_type, info in sorted(inventory['decision_types'].items()):
        for field, entry in sorted(info['fields'].items()):
            kind = entry['kind']
            if kind in NOT_SCREENED:
                plan.append({'decision_type': decision_type, 'field': field,
                             'kind': kind, 'label': 'not_screened',
                             'value': None, 'reason': NOT_SCREENED[kind]})
                continue
            declared = entry.get('declared', {})
            if kind == 'numeric':
                low = declared.get('min_value')
                minimum = 0 if low is None or low < 0 else low
                plan.append({'decision_type': decision_type, 'field': field,
                             'kind': kind, 'label': 'legal_minimum',
                             'value': str(minimum)})
                column_max = None
                digits, places = declared.get('max_digits'), declared.get('decimal_places')
                if digits is not None:
                    column_max = D(10) ** (digits - (places or 0)) - (
                        D(10) ** -(places or 0))
                declared_max = declared.get('max_value')
                candidates = [c for c in (declared_max, column_max, CASH)
                              if c is not None]
                maximum = min(D(str(c)) for c in candidates)
                plan.append({'decision_type': decision_type, 'field': field,
                             'kind': kind, 'label': 'funded_maximum',
                             'value': str(maximum)})
            elif kind == 'choice':
                for choice in declared.get('choices', [])[:6]:
                    plan.append({'decision_type': decision_type, 'field': field,
                                 'kind': kind, 'label': f'category:{choice}',
                                 'value': choice})
    return plan


def model_for(decision_type):
    import importlib
    entry = MODEL_FOR.get(decision_type)
    if entry is None:
        return None
    module, name = entry
    return getattr(importlib.import_module(module), name)


def coerce(row, field, value):
    django_field = row._meta.get_field(field)
    kind = django_field.get_internal_type()
    if kind == 'DecimalField':
        return D(str(value))
    if kind in ('IntegerField', 'SmallIntegerField', 'PositiveIntegerField',
                'BigIntegerField', 'PositiveSmallIntegerField'):
        return int(D(str(value)))
    return value


def apply_probe(submission, probe):
    model = model_for(probe['decision_type'])
    if model is None:
        return False
    rows = list(model.objects.filter(submission=submission).order_by('pk'))
    if not rows:
        return False
    row = rows[0]
    if not hasattr(row, probe['field']):
        return False
    setattr(row, probe['field'], coerce(row, probe['field'], probe['value']))
    row.save(update_fields=[probe['field']])
    return True


def prepare(game, rnd, teams, probe=None, capture=None):
    """Write every team's baseline, then apply at most one probe. Idempotent."""
    from core.models import DecisionSubmission
    applied = False
    for team in teams:
        sub, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=rnd, defaults={'status': 'draft'})
        BASE.build(sub, team)
        optional = BASE.build_optional(sub, team)
        if capture is not None and not capture:
            capture.update(optional)
        if probe is not None and team.id == probe['_team_id']:
            applied = apply_probe(sub, probe)
        sub.status = 'locked'
        sub.locked_at = timezone.now()
        sub.save(update_fields=['status', 'locked_at'])
    return applied


def self_test(game, rnd, teams, subject):
    """Three controls. Evidence is refused unless all three hold."""
    from core.models import DecisionSubmission

    checks = {}
    first = CF.evaluate(game, rnd, subject, lambda: prepare(game, rnd, teams))
    second = CF.evaluate(game, rnd, subject, lambda: prepare(game, rnd, teams))
    identical = CF.delta(first, second)
    checks['baseline_vs_identical_baseline_is_zero'] = {
        'passed': CF.is_zero(identical), 'delta': identical}

    # A field the engine reads, at a value that must change the outcome.
    def responsive():
        prepare(game, rnd, teams)
        from core.models.decisions import DecisionMarketing
        sub = DecisionSubmission.objects.get(team=subject, round=rnd)
        for row in DecisionMarketing.objects.filter(submission=sub):
            row.production_volume = 0
            row.save(update_fields=['production_volume'])

    moved = CF.delta(first, CF.evaluate(game, rnd, subject, responsive))
    checks['known_responsive_field_moves'] = {
        'passed': not CF.is_zero(moved),
        'field': 'marketing.production_volume -> 0', 'delta': moved}

    # A field no engine module reads.
    def inert():
        prepare(game, rnd, teams)
        sub = DecisionSubmission.objects.get(team=subject, round=rnd)
        sub.team_notes = 'flat control for the screening self-test'
        sub.save(update_fields=['team_notes'])

    flat = CF.delta(first, CF.evaluate(game, rnd, subject, inert))
    checks['known_flat_field_does_not_move'] = {
        'passed': CF.is_zero(flat),
        'field': 'DecisionSubmission.team_notes', 'delta': flat}

    checks['all_passed'] = all(c['passed'] for c in checks.values()
                               if isinstance(c, dict) and 'passed' in c)
    return checks, first


def run(inventory, max_probes=None, verbose=True):
    from core.models import Game, Round, Team

    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('screen-owner', 'a@e.com', 'x')
    _assert_model_map_covers_plan()
    call_command('load_all_scenarios', verbosity=0)
    call_command('setup_test_game', verbosity=0)

    game = Game.objects.order_by('-id').first()
    rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    subject = teams[0]

    started = time.time()
    checks, baseline_metrics = self_test(game, rnd, teams, subject)
    if verbose:
        for name, check in checks.items():
            if isinstance(check, dict):
                print(f"  {'ok ' if check['passed'] else 'BAD'} {name}", flush=True)
    if not checks['all_passed']:
        return {'self_tests': checks, 'aborted': 'self-tests failed',
                'seed': SCREEN_SEED}

    plan = probe_plan(inventory)
    screenable = [p for p in plan if p['label'] != 'not_screened']
    if max_probes:
        screenable = screenable[:max_probes]

    # Which decision types this scenario can express, and the rule where it
    # cannot. Captured from a throwaway preparation inside the checkpoint.
    availability = {}
    CF.evaluate(game, rnd, subject,
                lambda: prepare(game, rnd, teams, capture=availability))

    results = []
    for index, probe in enumerate(screenable, 1):
        decision_type = probe['decision_type']
        limit = availability.get(decision_type)
        if decision_type in REFERENCE_ONLY_TYPES:
            results.append(dict(probe, applied=False, status='unreachable',
                                rule='this decision type exposes only reference '
                                     'dimensions, covered by the reference rule'))
            continue
        if limit is not None and not limit['built']:
            results.append(dict(probe, applied=False, status='unreachable',
                                rule=limit['rule']))
            continue

        probe = dict(probe, _team_id=subject.id)
        applied = {'value': False}

        def mutate(probe=probe, applied=applied):
            applied['value'] = prepare(game, rnd, teams, probe)

        try:
            metrics = CF.evaluate(game, rnd, subject, mutate)
        except AssertionError as error:
            results.append(dict(probe, applied=False, status='error',
                                error=f'checkpoint violated: {error}'))
            break
        record = dict(probe)
        record.pop('_team_id', None)
        if not applied['value']:
            # Not a scenario limit — the type was buildable and the field still
            # did not take. That is a harness gap, and it stops evidence.
            record.update({'applied': False, 'status': 'not_applied',
                           'reason': 'the decision type was available but the '
                                     'probe did not reach a row'})
        else:
            deltas = CF.delta(baseline_metrics, metrics)
            record.update({'applied': True, 'metrics': metrics,
                           'delta': deltas,
                           'moved': not CF.is_zero(deltas),
                           'status': 'moved' if not CF.is_zero(deltas) else 'flat'})
        results.append(record)
        if verbose and index % 10 == 0:
            print(f'  {index}/{len(screenable)} probes', flush=True)

    applied_results = [r for r in results if r.get('applied')]
    moved = [r for r in applied_results if r.get('moved')]
    unreachable = [r for r in results if r.get('status') == 'unreachable']
    not_applied = [r for r in results if r.get('status') == 'not_applied']
    errors = [r for r in results if r.get('status') == 'error']

    discriminating = 0 < len(moved) < len(applied_results)
    covered = not not_applied and not errors

    return {
        'seed': SCREEN_SEED,
        'method': 'same-game transactional counterfactual; team compared only '
                  'with itself from one frozen checkpoint',
        'baseline': 'load_demo scripted defaults; see harness/baseline.py',
        'self_tests': checks,
        'baseline_metrics': baseline_metrics,
        'decision_type_availability': availability,
        'context': CF.context_identity(game, rnd),
        'subject_team': subject.id,
        'elapsed_seconds': round(time.time() - started, 1),
        'planned': len(plan),
        'screened': len(applied_results),
        'moved': len(moved),
        'flat': len(applied_results) - len(moved),
        'unreachable': len(unreachable),
        'not_applied': len(not_applied),
        'errors': len(errors),
        'discriminating': discriminating,
        'coverage_complete': covered,
        'not_screened': [p for p in plan if p['label'] == 'not_screened'],
        'results': results,
    }
