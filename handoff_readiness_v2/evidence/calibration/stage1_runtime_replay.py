#!/usr/bin/env python3
"""Resolve a disposable ten-round field and export Stage 1 demand evidence.

This is deliberately a runner, not the independent calculation.  It invokes
the real resolver in an isolated database and records its delivered Bass inputs
and outputs.  ``independent_bass.py`` consumes the resulting JSON separately;
that comparison imports no engine code.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

from generic_adaptive_policy import normalize_policy


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
BACKEND = REPO / 'backend'
HARNESS = REPO / 'handoff_readiness_v2' / 'evidence' / 'adversarial-balance' / 'harness'
MARKER = '---STAGE1-RUNTIME-JSON---'
SCENARIOS = {
    'consumer_electronics_2026': 'Consumer Electronics 2026',
    'clean_energy_tech_2026': 'Clean Energy Technology 2026',
    'media_entertainment_2026': 'Global Media & Entertainment 2026',
}

LEGACY_POLICY_SPECS = {
    'baseline': {},
    'price_plus_10': {'price_multiplier': 1.10},
    'promotion_plus_50': {'promotion_multiplier': 1.50},
    'production_plus_25': {'production_multiplier': 1.25},
    'sales_team_plus_50': {'sales_staff_multiplier': 1.50},
}
POLICY_SPEC_KEYS = frozenset({
    'price_multiplier', 'promotion_multiplier', 'production_multiplier',
    'sales_staff_multiplier', 'new_debt', 'debt_repayment', 'new_equity',
    'environmental_investment', 'social_investment',
})


def parse_policy_spec(raw):
    """Parse one measurement-only decision policy, rejecting silent typos."""
    if not raw:
        return {}
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f'invalid policy JSON: {exc}') from exc
    if not isinstance(spec, dict):
        raise ValueError('policy spec must be a JSON object')
    unknown = sorted(set(spec) - POLICY_SPEC_KEYS)
    if unknown:
        raise ValueError('unknown policy spec field(s): ' + ', '.join(unknown))
    normalised = {}
    for key, value in sorted(spec.items()):
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f'{key} must be a non-negative number')
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{key} must be a non-negative number') from exc
        if number < 0:
            raise ValueError(f'{key} must be a non-negative number')
        normalised[key] = number
    return normalised

LEGACY_TABLES = r'''
from django.apps import apps
from django.db import connection
existing = set(connection.introspection.table_names())
models = [m for m in apps.get_models() if not m._meta.managed]
for model in models:
    model._meta.managed = True
with connection.schema_editor() as editor:
    for model in models:
        if model._meta.db_table not in existing:
            editor.create_model(model)
for model in models:
    model._meta.managed = False
'''


BODY = r'''
import json
import math
import sys
from decimal import Decimal
from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command

sys.path.insert(0, {harness!r})
import baseline as BASE
sys.path.insert(0, {calibration!r})
import generic_adaptive_policy as GAP

if not DjangoUser.objects.filter(is_superuser=True).exists():
    DjangoUser.objects.create_superuser('stage1-owner', 'stage1@example.com', 'x')
call_command('load_all_scenarios', verbosity=0)

from core.models import (Game, Round, Team, LeaderboardEntry,
                         RoundResultAIAdoption, RoundResultDemandReconciliation,
                         RoundResultFinancials, RoundResultPerformanceIndex,
                         RoundResultProductDemand, RoundResultProductMarket)
from core.models.scenario import Scenario
from core.engine.advance_round import _run_phase_1, advance_to_next_round
from django.utils import timezone

scenario = Scenario.objects.get(name={scenario_name!r})
# Company names are drawn by an unseeded random.shuffle, so without this the
# roster differs between runs.  Names do not affect any outcome -- profiles are
# assigned by team creation index -- but pinning them makes a run reproducible
# and lets two runs be compared row for row.
if {name_seed!r} is not None:
    import random
    random.seed({name_seed!r})
if {home_markets!r} or {teams} != 4:
    call_command('initialize_game', scenario=scenario.id, teams={teams},
                 name='CRV2-11 parity replay', home_markets={home_markets!r})
else:
    call_command('setup_test_game', scenario=scenario.id, verbosity=0)
game = Game.objects.order_by('-id').first()
teams = list(Team.objects.filter(game=game).order_by('id'))
rows = []
team_rounds = []
product_rounds = []
product_demand_rounds = []
decision_rounds = []
adaptive_policy_trace = []
policy_spec = json.loads({policy_spec_json!r})
adaptive_policy = json.loads({adaptive_policy_json!r})

for expected_round in range(1, {rounds} + 1):
    assert game.current_round == expected_round, (game.current_round, expected_round)
    rnd = Round.objects.get(game=game, round_number=expected_round)
    for team in teams:
        from core.models import DecisionSubmission
        sub, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=rnd, defaults={{'status': 'draft'}})
        BASE.build(sub, team)
        if {adaptive_production!r} and expected_round > 1:
            from core.models.decisions import DecisionMarketing
            for marketing in (DecisionMarketing.objects.filter(submission=sub)
                              .order_by('team_product_id', 'market_id')):
                prior = RoundResultProductMarket.objects.filter(
                    game=game, round_number=expected_round - 1, team=team,
                    team_product=marketing.team_product, market=marketing.market,
                ).first()
                if prior is not None:
                    marketing.production_volume = max(
                        1, math.ceil(float(prior.units_sold) * 1.10))
                    marketing.demand_estimate = int(marketing.production_volume * 1.20)
                    marketing.save(update_fields=['production_volume', 'demand_estimate'])
        if team.id == teams[{subject_team_index}].id and adaptive_policy:
            from core.models.decisions import DecisionMarketing
            subject_marketing = (DecisionMarketing.objects.filter(submission=sub)
                                 .order_by('team_product_id', 'market_id'))
            prior_financials = None
            if expected_round > 1:
                prior_financials = RoundResultFinancials.objects.get(
                    game=game, round_number=expected_round - 1, team=team)
            for marketing in subject_marketing:
                baseline_volume = marketing.production_volume
                baseline_price = marketing.retail_price
                baseline_staff = marketing.sales_team_count
                prior_payload = None
                if expected_round > 1:
                    prior_result = RoundResultProductMarket.objects.get(
                        game=game, round_number=expected_round - 1, team=team,
                        team_product=marketing.team_product,
                        market=marketing.market)
                    prior_demands = RoundResultProductDemand.objects.filter(
                        game=game, round_number=expected_round - 1, team=team,
                        team_product=marketing.team_product,
                        market=marketing.market)
                    prior_payload = {{
                        'produced': float(prior_result.units_produced),
                        'sold': float(prior_result.units_sold),
                        'unsold': float(prior_result.units_unsold),
                        'lost_demand': sum(
                            float(row.lost_demand) for row in prior_demands),
                    }}
                finances = {{
                    'cash': float(prior_financials.cash_closing)
                            if prior_financials else 0.0,
                    'debt_to_equity': float(prior_financials.debt_to_equity)
                                      if prior_financials else 0.0,
                }}
                feedback = GAP.decide(
                    baseline_volume=baseline_volume,
                    baseline_price=baseline_price,
                    baseline_staff=baseline_staff,
                    prior=prior_payload,
                    finances=finances,
                    parameters=adaptive_policy)
                marketing.production_volume = feedback['production_volume']
                marketing.demand_estimate = int(
                    marketing.production_volume * 1.20)
                marketing.retail_price = baseline_price * Decimal(
                    str(feedback['price_factor']))
                marketing.sales_team_count = feedback['sales_staff']
                marketing.save()
                adaptive_policy_trace.append({{
                    'round': expected_round,
                    'team': team.name,
                    'starter_profile': team.firm_starter_profile.profile_name,
                    'product': marketing.team_product.name,
                    'market': marketing.market.code,
                    'prior': prior_payload,
                    'prior_finances': finances,
                    'decision': feedback,
                }})
        if team.id == teams[{subject_team_index}].id and policy_spec:
            from core.models.decisions import (DecisionESG, DecisionFinancing,
                                               DecisionMarketing)
            for marketing in (DecisionMarketing.objects.filter(submission=sub)
                              .order_by('team_product_id', 'market_id')):
                if 'price_multiplier' in policy_spec:
                    marketing.retail_price *= Decimal(
                        str(policy_spec['price_multiplier']))
                if 'promotion_multiplier' in policy_spec:
                    marketing.promotion_budget *= Decimal(
                        str(policy_spec['promotion_multiplier']))
                if 'production_multiplier' in policy_spec:
                    marketing.production_volume = math.ceil(
                        float(marketing.production_volume)
                        * policy_spec['production_multiplier'])
                    marketing.demand_estimate = int(marketing.production_volume * 1.20)
                if 'sales_staff_multiplier' in policy_spec:
                    marketing.sales_team_count = math.ceil(
                        marketing.sales_team_count
                        * policy_spec['sales_staff_multiplier'])
                marketing.save()
            financing_fields = ('new_debt', 'debt_repayment', 'new_equity')
            if any(field in policy_spec for field in financing_fields):
                financing, _ = DecisionFinancing.objects.get_or_create(
                    submission=sub)
                for field in financing_fields:
                    if field in policy_spec:
                        setattr(financing, field,
                                Decimal(str(policy_spec[field])))
                financing.save()
            esg_fields = ('environmental_investment', 'social_investment')
            if any(field in policy_spec for field in esg_fields):
                esg, _ = DecisionESG.objects.get_or_create(submission=sub)
                for field in esg_fields:
                    if field in policy_spec:
                        setattr(esg, field, Decimal(str(policy_spec[field])))
                esg.save()
        sub.status = 'locked'
        sub.locked_at = timezone.now()
        sub.save(update_fields=['status', 'locked_at'])

        from core.models.decisions import (DecisionESG, DecisionFinancing,
                                           DecisionMarketing)
        marketing_rows = list(DecisionMarketing.objects.filter(
            submission=sub).order_by('team_product_id', 'market_id'))
        financing = DecisionFinancing.objects.filter(submission=sub).first()
        esg = DecisionESG.objects.filter(submission=sub).first()
        price_total = sum((row.retail_price for row in marketing_rows), Decimal('0'))
        decision_rounds.append({{
            'round': expected_round,
            'team': team.name,
            'starter_profile': team.firm_starter_profile.profile_name,
            'marketing_row_count': len(marketing_rows),
            'average_retail_price': str(
                price_total / len(marketing_rows) if marketing_rows else 0),
            'promotion_budget_total': str(sum(
                (row.promotion_budget for row in marketing_rows), Decimal('0'))),
            'production_volume_total': sum(
                row.production_volume for row in marketing_rows),
            'sales_staff_total': sum(
                row.sales_team_count for row in marketing_rows),
            'new_debt': str(financing.new_debt if financing else 0),
            'debt_repayment': str(financing.debt_repayment if financing else 0),
            'new_equity': str(financing.new_equity if financing else 0),
            'environmental_investment': str(
                esg.environmental_investment if esg else 0),
            'social_investment': str(esg.social_investment if esg else 0),
        }})

    context = _run_phase_1(game.id)
    effective_population = {{
        segment_id: state.effective_population
        for segment_id, state in context.segments.items()
        if state.segment_def.segment_type == 'customer'
    }}
    reconciliations = (RoundResultDemandReconciliation.objects
                       .filter(game=game, round_number=expected_round)
                       .select_related('segment', 'market').order_by(
                           'market__code', 'segment__name'))
    for rec in reconciliations:
        ai_take = sum((item.new_adopters for item in
                       RoundResultAIAdoption.objects.filter(
                           game=game, round_number=expected_round,
                           segment=rec.segment, market=rec.market)
                       .order_by('ai_competitor__name')), 0)
        rows.append({{
            'round': expected_round,
            'market': rec.market.code,
            'segment': rec.segment.name,
            'population': str(effective_population[rec.segment_id]),
            'adoption_pool': str(rec.adoption_pool),
            'human_adopters': str(rec.human_adopters),
            'ai_adopters': str(ai_take),
            'unserved_adopters': str(rec.unserved_adopters),
        }})
    for team in teams:
        financials = RoundResultFinancials.objects.get(
            game=game, round_number=expected_round, team=team)
        performance = RoundResultPerformanceIndex.objects.get(
            game=game, round_number=expected_round, team=team)
        leaderboard = LeaderboardEntry.objects.get(
            game=game, round_number=expected_round, team=team)
        product_rows = RoundResultProductMarket.objects.filter(
            game=game, round_number=expected_round, team=team).select_related(
                'team_product', 'market').order_by('team_product_id', 'market_id', 'id')
        for product_row in product_rows:
            product_rounds.append({{
                'round': expected_round,
                'team': team.name,
                'starter_profile': team.firm_starter_profile.profile_name,
                'product_id': product_row.team_product_id,
                'product_name': product_row.team_product.name,
                'market': product_row.market.code,
                'units_produced': str(product_row.units_produced),
                'units_sold': str(product_row.units_sold),
                'units_unsold': str(product_row.units_unsold),
            }})
        demand_rows = RoundResultProductDemand.objects.filter(
            game=game, round_number=expected_round, team=team).select_related(
                'team_product', 'segment', 'market').order_by(
                    'team_product_id', 'segment_id', 'market_id', 'id')
        for demand_row in demand_rows:
            product_demand_rounds.append({{
                'round': expected_round,
                'team': team.name,
                'starter_profile': team.firm_starter_profile.profile_name,
                'product_id': demand_row.team_product_id,
                'product_name': demand_row.team_product.name,
                'segment': demand_row.segment.name,
                'market': demand_row.market.code,
                'fit_score': str(demand_row.fit_score),
                'adjusted_fit_score': str(demand_row.adjusted_fit_score),
                'market_readiness_pct': str(demand_row.market_readiness_pct),
                'attractiveness': str(demand_row.attractiveness),
                'share_pct': str(demand_row.share_pct),
                'unconstrained_demand': str(demand_row.unconstrained_demand),
                'available_production': str(demand_row.available_production),
                'units_sold': str(demand_row.units_sold),
                'lost_demand': str(demand_row.lost_demand),
            }})
        team_rounds.append({{
            'round': expected_round,
            'team': team.name,
            'starter_profile': team.firm_starter_profile.profile_name,
            'total_revenue': str(financials.total_revenue),
            'gross_revenue': str(financials.gross_revenue),
            'net_income': str(financials.net_income),
            'cash_closing': str(financials.cash_closing),
            'total_debt': str(financials.total_debt),
            'total_equity': str(financials.total_equity),
            'debt_to_equity': str(financials.debt_to_equity),
            'financing_cash_flow': str(financials.financing_cash_flow),
            'strategy_expense': str(financials.strategy_expense),
            'share_price': str(financials.share_price),
            'performance_index': str(performance.index_value),
            'satisfaction_score': str(performance.satisfaction_score),
            'rank': leaderboard.rank,
            'units_produced': str(sum((row.units_produced for row in product_rows), 0)),
            'units_sold': str(sum((row.units_sold for row in product_rows), 0)),
            'units_unsold': str(sum((row.units_unsold for row in product_rows), 0)),
        }})
    advance_to_next_round(game.id)
    game.refresh_from_db()

print({marker!r})
print(json.dumps({{
    'scenario': scenario.name,
    'home_markets': {home_markets!r},
    'teams_requested': {teams},
    'policy': {policy!r},
    'policy_spec': policy_spec,
    'adaptive_policy': adaptive_policy,
    'subject_team_index': {subject_team_index},
    'adaptive_production': {adaptive_production!r},
    'teams': [{{'name': team.name, 'starter_profile': team.firm_starter_profile.profile_name}}
              for team in teams],
    'rows': rows,
    'team_rounds': team_rounds,
    'product_rounds': product_rounds,
    'product_demand_rounds': product_demand_rounds,
    'decision_rounds': decision_rounds,
    'adaptive_policy_trace': adaptive_policy_trace,
}}, default=str, sort_keys=True))
'''


def command_env(database):
    required = ('DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_PORT')
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit('Missing database environment: ' + ', '.join(missing))
    return {**os.environ, 'DB_NAME': database, 'PYTHONPATH': str(BACKEND)}


def run(database, *args, timeout=3600):
    return subprocess.run([sys.executable, 'manage.py', *args], cwd=BACKEND,
                          env=command_env(database), text=True,
                          capture_output=True, timeout=timeout)


def psql(database, sql):
    env = {**os.environ, 'PGPASSWORD': os.environ['DB_PASSWORD']}
    return subprocess.run([
        'psql', '-h', os.environ['DB_HOST'], '-p', os.environ['DB_PORT'],
        '-U', os.environ['DB_USER'], '-d', database, '-v', 'ON_ERROR_STOP=1',
        '-c', sql,
    ], env=env, text=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=pathlib.Path,
                        default=HERE / 'stage1_runtime_replay.json')
    parser.add_argument('--scenario', choices=tuple(SCENARIOS),
                        default='consumer_electronics_2026',
                        help='shipped scenario slug to resolve')
    parser.add_argument('--rounds', type=int, default=10,
                        help='number of sequential rounds to resolve (1-10)')
    parser.add_argument('--home-markets', default='',
                        help='optional comma-separated home-market assignment')
    parser.add_argument('--teams', type=int, default=4,
                        help='number of teams in the replay (minimum 1)')
    parser.add_argument('--policy', default='baseline', choices=(
        'baseline', 'price_plus_10', 'promotion_plus_50',
        'production_plus_25', 'sales_team_plus_50'),
                        help='apply one measurement-only change to team 0')
    parser.add_argument('--policy-spec-json', default='',
                        help='generic measurement-only policy JSON; mutually '
                             'exclusive with a non-baseline legacy --policy')
    parser.add_argument('--adaptive-policy-json', default='',
                        help='scenario-agnostic feedback-policy JSON applied '
                             'only to the subject team')
    parser.add_argument('--subject-team-index', type=int, default=0,
                        help='zero-based team index for a policy variation')
    parser.add_argument('--adaptive-production', action='store_true',
                        help='use a uniform 10%% buffer over prior sales after round 1')
    parser.add_argument('--name-seed', type=int, default=None,
                        help='pin the shuffled company names so a run is '
                             'reproducible; names affect no outcome, because '
                             'starter profiles are assigned by team creation '
                             'index, but pinning lets two runs be compared row '
                             'for row')
    options = parser.parse_args()
    if not 1 <= options.rounds <= 10:
        raise SystemExit('--rounds must be between 1 and 10')
    if options.teams < 1:
        raise SystemExit('--teams must be at least 1')
    if not 0 <= options.subject_team_index < options.teams:
        raise SystemExit('--subject-team-index must identify a requested team')
    if options.policy_spec_json and options.policy != 'baseline':
        raise SystemExit('--policy-spec-json cannot be combined with a non-baseline --policy')
    if options.adaptive_policy_json and (options.policy_spec_json
                                         or options.policy != 'baseline'):
        raise SystemExit('--adaptive-policy-json cannot be combined with a fixed policy')
    try:
        policy_spec = (parse_policy_spec(options.policy_spec_json)
                       if options.policy_spec_json
                       else LEGACY_POLICY_SPECS[options.policy])
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    try:
        adaptive_policy = (normalize_policy(json.loads(options.adaptive_policy_json))
                           if options.adaptive_policy_json else {})
    except (ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')
    database = f'gsp_crv211_stage1_{stamp}_{os.getpid()}'
    if psql('postgres', f'CREATE DATABASE {database}').returncode:
        raise SystemExit(f'could not create {database}')
    try:
        for args in (('migrate', '--noinput'), ('shell', '-c', LEGACY_TABLES)):
            result = run(database, *args)
            if result.returncode:
                raise RuntimeError(result.stderr[-3000:])
        result = run(database, 'shell', '-c', BODY.format(
            harness=str(HARNESS), calibration=str(HERE), marker=MARKER,
            rounds=options.rounds,
            scenario_name=SCENARIOS[options.scenario],
            home_markets=options.home_markets,
            adaptive_production=options.adaptive_production, teams=options.teams,
            policy=options.policy, name_seed=options.name_seed,
            policy_spec_json=json.dumps(policy_spec, sort_keys=True),
            adaptive_policy_json=json.dumps(adaptive_policy, sort_keys=True),
            subject_team_index=options.subject_team_index), timeout=3600)
        if result.returncode or MARKER not in result.stdout:
            raise RuntimeError(result.stderr[-5000:] + result.stdout[-5000:])
        payload = json.loads(result.stdout.split(MARKER, 1)[1].strip())
        payload['database'] = database
        payload['generated_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        payload['code_revision'] = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True,
            capture_output=True, check=True).stdout.strip()
        options.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
        print(f'wrote {options.output}')
    finally:
        dropped = psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        if dropped.returncode:
            print(dropped.stderr, file=sys.stderr)


if __name__ == '__main__':
    main()
