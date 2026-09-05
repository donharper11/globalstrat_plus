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


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
BACKEND = REPO / 'backend'
HARNESS = REPO / 'handoff_readiness_v2' / 'evidence' / 'adversarial-balance' / 'harness'
MARKER = '---STAGE1-RUNTIME-JSON---'

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
from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command

sys.path.insert(0, {harness!r})
import baseline as BASE

if not DjangoUser.objects.filter(is_superuser=True).exists():
    DjangoUser.objects.create_superuser('stage1-owner', 'stage1@example.com', 'x')
call_command('load_all_scenarios', verbosity=0)

from core.models import (Game, Round, Team, LeaderboardEntry,
                         RoundResultAIAdoption, RoundResultDemandReconciliation,
                         RoundResultFinancials, RoundResultPerformanceIndex,
                         RoundResultProductMarket)
from core.models.scenario import Scenario
from core.engine.advance_round import _run_phase_1, advance_to_next_round
from django.utils import timezone

scenario = Scenario.objects.get(name='Consumer Electronics 2026')
if {home_markets!r}:
    call_command('initialize_game', scenario=scenario.id, teams=4,
                 name='CRV2-11 parity replay', home_markets={home_markets!r})
else:
    call_command('setup_test_game', scenario=scenario.id, verbosity=0)
game = Game.objects.order_by('-id').first()
teams = list(Team.objects.filter(game=game).order_by('id'))
rows = []
team_rounds = []
product_rounds = []

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
        sub.status = 'locked'
        sub.locked_at = timezone.now()
        sub.save(update_fields=['status', 'locked_at'])

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
        team_rounds.append({{
            'round': expected_round,
            'team': team.name,
            'starter_profile': team.firm_starter_profile.profile_name,
            'total_revenue': str(financials.total_revenue),
            'net_income': str(financials.net_income),
            'cash_closing': str(financials.cash_closing),
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
    'adaptive_production': {adaptive_production!r},
    'teams': [{{'name': team.name, 'starter_profile': team.firm_starter_profile.profile_name}}
              for team in teams],
    'rows': rows,
    'team_rounds': team_rounds,
    'product_rounds': product_rounds,
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
    parser.add_argument('--rounds', type=int, default=10,
                        help='number of sequential rounds to resolve (1-10)')
    parser.add_argument('--home-markets', default='',
                        help='optional comma-separated home-market assignment')
    parser.add_argument('--adaptive-production', action='store_true',
                        help='use a uniform 10%% buffer over prior sales after round 1')
    options = parser.parse_args()
    if not 1 <= options.rounds <= 10:
        raise SystemExit('--rounds must be between 1 and 10')
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')
    database = f'gsp_crv211_stage1_{stamp}'
    if psql('postgres', f'CREATE DATABASE {database}').returncode:
        raise SystemExit(f'could not create {database}')
    try:
        for args in (('migrate', '--noinput'), ('shell', '-c', LEGACY_TABLES)):
            result = run(database, *args)
            if result.returncode:
                raise RuntimeError(result.stderr[-3000:])
        result = run(database, 'shell', '-c', BODY.format(
            harness=str(HARNESS), marker=MARKER, rounds=options.rounds,
            home_markets=options.home_markets,
            adaptive_production=options.adaptive_production), timeout=3600)
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
