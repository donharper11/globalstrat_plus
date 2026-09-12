#!/usr/bin/env python3
"""R11 probe: fixed-policy replay that exports every per-round output.

Development-grade measurement (not release evidence).  The replay loop is
`stage1_runtime_replay.py`'s — same scenario, same
`initialize_game ... home_markets=NA`, same adversarial-balance
`baseline.build` competent policy, same 10% adaptive production — plus the D6
probe's two additions: it snapshots the real competitive output manifest for
round 0 and after every resolved round, and dumps every row of every per-round
result table, round 0 included, with human-readable natural keys.

One deliberate difference from the D6 copy: that probe *asserted* the presence
of the retired `new_adopters = bass_p * pop * avg_share * 10` line, which R11
deletes.  Here the round-zero rule is **recorded** rather than asserted, so one
script drives both arms of a before/after comparison and each run carries
proof of which engine it exercised.

Usage (needs the DB_* environment of a disposable local PostgreSQL, which
`backend/scripts/run-calibration-postgres` or an equivalent wrapper supplies):

    r11_round_zero_replay.py --label baseline_pre_r11 --teams 8 --rounds 10
    r11_round_zero_replay.py --label variant_r11      --teams 8 --rounds 10
    r11_round_zero_compare.py baseline_pre_r11 variant_r11 <runs-root>

Pass --name-seed to pin the random company names when a byte-exact manifest
hash comparison is wanted; without it, team names differ between runs and only
the name-normalised row comparison is meaningful.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
BACKEND = REPO / 'backend'
HARNESS = REPO / 'handoff_readiness_v2' / 'evidence' / 'adversarial-balance' / 'harness'

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
import inspect
import json
import math
import os
import pathlib
import sys
import time
from decimal import Decimal

P = json.loads(os.environ['R11_PARAMS'])
out = pathlib.Path(P['out_dir'])
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, P['harness'])
import baseline as BASE

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.db import models as djm
from django.utils import timezone

if not DjangoUser.objects.filter(is_superuser=True).exists():
    DjangoUser.objects.create_superuser('r11-owner', 'r11@example.com', 'x')
call_command('load_all_scenarios', verbosity=0)

from core.models import (Game, Round, Team, LeaderboardEntry, DecisionSubmission,
                         RoundResultAdoption, RoundResultAIAdoption,
                         RoundResultDemandReconciliation, RoundResultFinancials,
                         RoundResultPerformanceIndex, RoundResultProductDemand,
                         RoundResultProductMarket)
from core.models.results_financials import RoundResultMarketRevenue, RoundResultCoherence
from core.models.decisions import DecisionMarketing
from core.models.scenario import Scenario
from core.engine.advance_round import _run_phase_1, advance_to_next_round
from core.services.resolution_manifest import build_output_manifest
from core.services.canonical_json import canonical_sha256
import core.engine.bootstrap as BOOT

# Record, never assert: the retired rule is one line, R11's is a block.
source = inspect.getsource(BOOT.bootstrap_round_zero)
retired = [line.strip() for line in source.splitlines()
           if 'bass_p * pop * avg_share' in line]
derived = [line.strip() for line in source.splitlines()
           if '_apportion_starter_units(' in line]
rule_line = retired[0] if retired else (derived[0] if derived else 'UNKNOWN')
print('RUNTIME ROUND-ZERO RULE:', rule_line, flush=True)

scenario = Scenario.objects.get(name='Consumer Electronics 2026')
if P.get('name_seed') is not None:
    import random
    random.seed(P['name_seed'])
call_command('initialize_game', scenario=scenario.id, teams=P['teams'],
             name='R11 round-zero probe', home_markets='NA')
game = Game.objects.order_by('-id').first()
teams = list(Team.objects.filter(game=game).order_by('id'))

REL = (('team', 'team__name'), ('segment', 'segment__name'), ('market', 'market__code'),
       ('team_product', 'team_product__name'), ('best_product', 'best_product__name'),
       ('ai_competitor', 'ai_competitor__name'))


def dump(model):
    names = {f.name for f in model._meta.concrete_fields}
    fields = [f.attname for f in model._meta.concrete_fields
              if f.attname != 'id' and not isinstance(f, (djm.DateTimeField, djm.DateField))]
    extra = [path for rel, path in REL if rel in names]
    qs = model.objects.filter(game=game).order_by('round_number', 'pk').values(*fields, *extra)
    return [{k: (str(v) if isinstance(v, Decimal) else v) for k, v in row.items()} for row in qs]


manifests = []


def snapshot(round_number):
    rnd = Round.objects.get(game=game, round_number=round_number)
    started = time.time()
    try:
        body, narrative = build_output_manifest(rnd)
    except Exception as exc:  # recorded, never hidden
        rec = {'round': round_number, 'error': repr(exc)}
        manifests.append(rec)
        print('MANIFEST ERROR', rec, flush=True)
        return
    rec = {'round': round_number, 'output_sha256': canonical_sha256(body),
           'narrative_sha256': canonical_sha256(narrative),
           'section_digests': body['section_digests'],
           'seconds': round(time.time() - started, 2)}
    manifests.append(rec)
    (out / f'manifest_r{round_number:02d}.json').write_text(
        json.dumps(body, default=str, sort_keys=True))
    print(f'manifest r{round_number}: {rec["output_sha256"]} ({rec["seconds"]}s)', flush=True)


snapshot(0)
round_seconds = {}
for expected_round in range(1, P['rounds'] + 1):
    started = time.time()
    assert game.current_round == expected_round, (game.current_round, expected_round)
    rnd = Round.objects.get(game=game, round_number=expected_round)
    for team in teams:
        sub, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=rnd, defaults={'status': 'draft'})
        BASE.build(sub, team)
        if expected_round > 1:  # --adaptive-production, as in the CRV2-11 runs
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
    _run_phase_1(game.id)
    snapshot(expected_round)
    advance_to_next_round(game.id)
    game.refresh_from_db()
    round_seconds[expected_round] = round(time.time() - started, 1)
    print(f'round {expected_round} done in {round_seconds[expected_round]}s', flush=True)

tables = {
    'adoption': dump(RoundResultAdoption),
    'product_demand': dump(RoundResultProductDemand),
    'ai_adoption': dump(RoundResultAIAdoption),
    'reconciliation': dump(RoundResultDemandReconciliation),
    'financials': dump(RoundResultFinancials),
    'performance_index': dump(RoundResultPerformanceIndex),
    'leaderboard': dump(LeaderboardEntry),
    'product_market': dump(RoundResultProductMarket),
    'market_revenue': dump(RoundResultMarketRevenue),
    'coherence': dump(RoundResultCoherence),
}
(out / 'results.json').write_text(json.dumps({
    'factor_line': rule_line,
    'teams': [{'name': t.name, 'starter_profile': t.firm_starter_profile.profile_name}
              for t in teams],
    'round_seconds': round_seconds,
    'manifests': manifests,
    'tables': tables,
}, default=str, sort_keys=True, indent=1))
print('R11-DONE', flush=True)
'''


def command_env(database, params):
    for name in ('DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_PORT'):
        if not os.environ.get(name):
            raise SystemExit('Missing database environment: ' + name)
    if os.environ['DB_HOST'] != '127.0.0.1':
        raise SystemExit('refusing: DB_HOST must be the disposable local container')
    return {**os.environ, 'DB_NAME': database, 'PYTHONPATH': str(BACKEND),
            'R11_PARAMS': json.dumps(params)}


def psql(database, sql):
    env = {**os.environ, 'PGPASSWORD': os.environ['DB_PASSWORD']}
    return subprocess.run(['psql', '-h', os.environ['DB_HOST'], '-p', os.environ['DB_PORT'],
                           '-U', os.environ['DB_USER'], '-d', database,
                           '-v', 'ON_ERROR_STOP=1', '-c', sql],
                          env=env, text=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--rounds', type=int, default=10)
    parser.add_argument('--teams', type=int, default=8)
    parser.add_argument('--name-seed', type=int, default=None)
    parser.add_argument('--out-root', type=pathlib.Path,
                        default=pathlib.Path.cwd() / 'r11_runs')
    options = parser.parse_args()
    out_dir = options.out_root / options.label
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')
    database = f'gsp_r11_{options.label}_{stamp}'.replace('-', '_')
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True,
                              capture_output=True, check=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--short'], cwd=REPO, text=True,
                           capture_output=True, check=True).stdout
    print(f'PHASE0 database={database} pid={os.getpid()} revision={revision} '
          f'dirty={dirty.strip()!r}', flush=True)
    params = {'out_dir': str(out_dir), 'harness': str(HARNESS),
              'rounds': options.rounds, 'teams': options.teams,
              'name_seed': options.name_seed}
    if psql('postgres', f'CREATE DATABASE {database}').returncode:
        raise SystemExit(f'could not create {database}')
    started = time.time()
    try:
        for args in (('migrate', '--noinput'), ('shell', '-c', LEGACY_TABLES)):
            result = subprocess.run([sys.executable, 'manage.py', *args], cwd=BACKEND,
                                    env=command_env(database, params), text=True,
                                    capture_output=True, timeout=3600)
            if result.returncode:
                raise RuntimeError(result.stderr[-3000:])
        print(f'migrated in {time.time() - started:.1f}s', flush=True)
        log = out_dir / 'engine.log'
        with log.open('w') as handle:
            result = subprocess.run([sys.executable, 'manage.py', 'shell', '-c', BODY],
                                    cwd=BACKEND, env=command_env(database, params),
                                    text=True, stdout=handle, stderr=subprocess.STDOUT,
                                    timeout=7200)
        if result.returncode or 'R11-DONE' not in log.read_text():
            raise RuntimeError(log.read_text()[-5000:])
    finally:
        dropped = psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
        if dropped.returncode:
            print(dropped.stderr, file=sys.stderr)
    meta = {'label': options.label, 'database': database, 'revision': revision,
            'worktree_dirty': dirty, 'rounds': options.rounds, 'teams': options.teams,
            'wall_seconds': round(time.time() - started, 1)}
    (out_dir / 'run_meta.json').write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta), flush=True)


if __name__ == '__main__':
    main()
