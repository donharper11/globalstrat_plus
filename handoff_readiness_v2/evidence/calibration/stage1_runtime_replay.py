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
import sys
from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command

sys.path.insert(0, {harness!r})
import baseline as BASE

if not DjangoUser.objects.filter(is_superuser=True).exists():
    DjangoUser.objects.create_superuser('stage1-owner', 'stage1@example.com', 'x')
call_command('load_all_scenarios', verbosity=0)

from core.models import (Game, Round, Team, RoundResultAIAdoption,
                         RoundResultDemandReconciliation)
from core.models.scenario import Scenario
from core.engine.advance_round import _run_phase_1, advance_to_next_round
from django.utils import timezone

scenario = Scenario.objects.get(name='Consumer Electronics 2026')
call_command('setup_test_game', scenario=scenario.id, verbosity=0)
game = Game.objects.order_by('-id').first()
teams = list(Team.objects.filter(game=game).order_by('id'))
rows = []

for expected_round in range(1, scenario.num_rounds + 1):
    assert game.current_round == expected_round, (game.current_round, expected_round)
    rnd = Round.objects.get(game=game, round_number=expected_round)
    for team in teams:
        from core.models import DecisionSubmission
        sub, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=rnd, defaults={{'status': 'draft'}})
        BASE.build(sub, team)
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
    advance_to_next_round(game.id)
    game.refresh_from_db()

print({marker!r})
print(json.dumps({{
    'scenario': scenario.name,
    'teams': [{{'name': team.name, 'starter_profile': team.firm_starter_profile.profile_name}}
              for team in teams],
    'rows': rows,
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
    options = parser.parse_args()
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
            harness=str(HARNESS), marker=MARKER), timeout=3600)
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
