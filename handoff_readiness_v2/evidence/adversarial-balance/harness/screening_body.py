"""Stage 2 — cheap sensitivity screening.

Every exposed numeric dimension at its legal minimum and a documented maximum,
every categorical dimension at each legal category, each against the documented
baseline, on one fixed scenario and seed.

Two design choices worth stating, because they bound what the numbers mean.

**Probes share a resolution.** Each round runs one control team on the baseline
and the remaining teams each deviating in exactly one field. Market share is
zero-sum, so a probe's measured effect includes competitive coupling with the
other probes in its round. That is acceptable for screening — a genuinely flat
dimension still reads flat — and anything responsive is escalated to an
isolated sweep where the coupling is removed. The alternative, one resolution
per probe, costs an order of magnitude more for a question this stage is not
asking.

**"Legal maximum" for an unbounded money field is the team's cash.** Several
fields have no declared ceiling, so their true legal maximum is the column's
storage limit — around 10^13. Screening every money field there would report
the same finding for all of them, that spending a trillion dollars bankrupts a
firm with $60m, and would drown any real cliff. The screen uses the largest
value the team could actually fund; the storage limit is probed separately, once,
as a boundary case.
"""
import json
import time
from decimal import Decimal as D

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.utils import timezone

import baseline as BASE  # noqa: E402  (injected onto sys.path by the runner)

SCREEN_SEED = 'crv2-06-screen-1'
CASH = D('60000000')

# Dimensions that are not balance dimensions. Recorded rather than screened, so
# the count of "not screened" is explicit instead of implied by absence.
NOT_SCREENED = {
    'reference': 'a foreign key naming which product, market, platform or '
                 'feature the row is about. Which entity a decision targets is '
                 'a strategy choice for Stage 3 search, not a magnitude with a '
                 'response curve.',
    'json': 'free-form structure. `campaign_focus_feature_ids` is already '
            'bounded by its 1-3 length rule and covered as a cross-row control; '
            'the rest carry channel detail rather than a scalar.',
    'text': 'a name or note. No effect on scoring.',
}


def probe_plan(inventory):
    """Every (decision type, field, label, value) the screen will run."""
    plan = []
    for decision_type, info in sorted(inventory['decision_types'].items()):
        for field, entry in sorted(info['fields'].items()):
            kind = entry['kind']
            if kind in NOT_SCREENED:
                plan.append({'decision_type': decision_type, 'field': field,
                             'kind': kind, 'label': 'not_screened',
                             'value': None, 'reason': NOT_SCREENED[kind]})
                continue
            if kind == 'numeric':
                declared = entry.get('declared', {})
                low = declared.get('min_value')
                # The floor is now zero for every protected field; for the rest
                # the declared minimum stands.
                minimum = 0 if low is None or low < 0 else low
                plan.append({'decision_type': decision_type, 'field': field,
                             'kind': kind, 'label': 'legal_minimum',
                             'value': minimum})
                high = declared.get('max_value')
                maximum = high if (high is not None and high < 10 ** 12) else int(CASH)
                plan.append({'decision_type': decision_type, 'field': field,
                             'kind': kind, 'label': 'funded_maximum',
                             'value': maximum})
            elif kind == 'choice':
                for choice in entry.get('declared', {}).get('choices', [])[:6]:
                    plan.append({'decision_type': decision_type, 'field': field,
                                 'kind': kind, 'label': f'category:{choice}',
                                 'value': choice})
            elif kind == 'boolean':
                for value in (True, False):
                    plan.append({'decision_type': decision_type, 'field': field,
                                 'kind': kind, 'label': f'boolean:{value}',
                                 'value': value})
    return plan


# Which model each screenable decision type writes, and how to reach its rows.
MODEL_FOR = {
    'budget': ('core.models.decisions', 'DecisionBudgetAllocation'),
    'esg': ('core.models.decisions', 'DecisionESG'),
    'financing': ('core.models.decisions', 'DecisionFinancing'),
    'marketing': ('core.models.decisions', 'DecisionMarketing'),
    'talent': ('core.models.talent', 'DecisionTalent'),
}


def model_for(decision_type):
    import importlib
    entry = MODEL_FOR.get(decision_type)
    if entry is None:
        return None
    module, name = entry
    return getattr(importlib.import_module(module), name)


def apply_probe(submission, probe):
    """Set one field on one team's baseline. Returns True if it was applied."""
    model = model_for(probe['decision_type'])
    if model is None:
        return False
    rows = list(model.objects.filter(submission=submission).order_by('pk'))
    if not rows:
        if probe['decision_type'] == 'financing':
            from core.models.decisions import DecisionFinancing
            rows = [DecisionFinancing.objects.create(submission=submission)]
        else:
            return False
    row = rows[0]
    if not hasattr(row, probe['field']):
        return False
    value = probe['value']
    field = row._meta.get_field(probe['field'])
    if field.get_internal_type() in ('DecimalField',):
        value = D(str(value))
    elif field.get_internal_type() in ('IntegerField', 'SmallIntegerField',
                                       'PositiveIntegerField', 'BigIntegerField'):
        value = int(value)
    setattr(row, probe['field'], value)
    row.save(update_fields=[probe['field']])
    return True


def outcome(team, round_number):
    from core.models import RoundResultFinancials, RoundResultPerformanceIndex
    fin = (RoundResultFinancials.objects
           .filter(team=team, round_number=round_number).order_by('-id').first())
    idx = (RoundResultPerformanceIndex.objects
           .filter(team=team, round_number=round_number).order_by('-id').first())
    if fin is None:
        return None
    return {
        'total_revenue': str(fin.total_revenue),
        'net_income': str(fin.net_income),
        'cash_closing': str(fin.cash_closing),
        'index_value': str(idx.index_value) if idx else None,
    }


def run(inventory, max_probes=None, verbose=True):
    """Screen the plan in batches, one control team per resolution."""
    from core.engine.advance_round import _run_phase_1
    from core.models import DecisionSubmission, Game, Round, Team

    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('screen-owner', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)

    plan = probe_plan(inventory)
    screenable = [p for p in plan if p['label'] != 'not_screened']
    if max_probes:
        screenable = screenable[:max_probes]

    results = []
    started = time.time()
    batch_index = 0
    position = 0

    while position < len(screenable):
        batch_index += 1
        call_command('setup_test_game', verbosity=0)
        game = Game.objects.order_by('-id').first()
        rnd = Round.objects.filter(
            game=game, round_number=game.current_round).first()
        teams = list(Team.objects.filter(game=game).order_by('id'))
        control, probes_teams = teams[0], teams[1:]

        subs = {}
        for team in teams:
            sub, _ = DecisionSubmission.objects.get_or_create(
                team=team, round=rnd, defaults={'status': 'draft'})
            BASE.build(sub, team)
            subs[team.id] = sub

        batch = screenable[position:position + len(probes_teams)]
        assigned = {}
        for team, probe in zip(probes_teams, batch):
            if apply_probe(subs[team.id], probe):
                assigned[team.id] = probe
            else:
                probe['applied'] = False
        position += len(batch)

        for sub in subs.values():
            sub.status = 'locked'
            sub.locked_at = timezone.now()
            sub.save(update_fields=['status', 'locked_at'])

        error = None
        try:
            _run_phase_1(game.id)
        except Exception as exc:  # a refused round is itself a screening result
            error = f'{type(exc).__name__}: {exc}'

        control_outcome = None if error else outcome(control, rnd.round_number)
        for team_id, probe in assigned.items():
            team = next(t for t in teams if t.id == team_id)
            probe_outcome = None if error else outcome(team, rnd.round_number)
            record = dict(probe)
            record.update({
                'applied': True,
                'batch': batch_index,
                'game': game.id,
                'team': team_id,
                'resolution_error': error,
                'control': control_outcome,
                'probe': probe_outcome,
            })
            if control_outcome and probe_outcome:
                record['delta'] = {
                    key: str(D(probe_outcome[key]) - D(control_outcome[key]))
                    for key in ('total_revenue', 'net_income', 'cash_closing')
                    if probe_outcome.get(key) and control_outcome.get(key)
                }
                record['responsive'] = any(
                    abs(D(v)) > D('1') for v in record['delta'].values())
            else:
                record['responsive'] = None
            results.append(record)
        for probe in batch:
            if probe.get('applied') is False:
                results.append(dict(probe, batch=batch_index,
                                    reason='no baseline row to vary'))
        if verbose:
            print(f'  batch {batch_index}: {len(assigned)} probes'
                  f'{" — " + error if error else ""}', flush=True)

    return {
        'seed': SCREEN_SEED,
        'baseline': 'load_demo scripted defaults; see harness/baseline.py',
        'elapsed_seconds': round(time.time() - started, 1),
        'planned': len(plan),
        'screened': len([r for r in results if r.get('applied')]),
        'not_screened': [p for p in plan if p['label'] == 'not_screened'],
        'batches': batch_index,
        'results': results,
    }
