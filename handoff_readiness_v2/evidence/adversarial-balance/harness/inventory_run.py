#!/usr/bin/env python3
"""Phase 1 — discover the legal decision space and test the two write paths
against each other.

Runs against a disposable database it creates and drops, seeded through the
project's own `setup_test_game`, so nothing here can touch a competition stack.

Two questions, both answered by probing rather than by reading:

1. For every field of every decision type a team can submit, which values does
   the serializer accept? Boundaries are established by offering values.
2. Does the per-type PATCH endpoint refuse exactly what the whole-submission
   PUT refuses? A rule enforced on one path and not the other is not a rule.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent
REPO = EVIDENCE.parents[2]
BACKEND = REPO / 'backend'

DB_HOST = os.environ.get('DB_HOST', '192.168.50.38')
DB_USER = os.environ.get('DB_USER', 'donwh')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED-CREDENTIAL-V2-048***')
DB_PORT = os.environ.get('DB_PORT', '5432')


def psql(database, sql):
    env = {**os.environ, 'PGPASSWORD': DB_PASSWORD}
    return subprocess.run(
        ['psql', '-h', DB_HOST, '-p', DB_PORT, '-U', DB_USER, '-d', database,
         '-v', 'ON_ERROR_STOP=0', '-c', sql],
        capture_output=True, text=True, env=env)


def manage(database, *args, timeout=900):
    env = {**os.environ, 'DB_NAME': database, 'DB_HOST': DB_HOST,
           'DB_USER': DB_USER, 'DB_PASSWORD': DB_PASSWORD, 'DB_PORT': DB_PORT,
           'PYTHONPATH': str(BACKEND)}
    return subprocess.run([sys.executable, 'manage.py', *args], cwd=BACKEND,
                          capture_output=True, text=True, env=env,
                          timeout=timeout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', default=None)
    parser.add_argument('--keep', action='store_true')
    options = parser.parse_args()

    stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    database = options.database or f'gsp_adversarial_{stamp}'

    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain',
                            '--untracked-files=no'], cwd=REPO,
                           capture_output=True, text=True).stdout.strip()

    steps = []

    def step(title, ok, detail=''):
        steps.append({'step': title, 'as_expected': bool(ok), 'detail': detail})
        print(f"  {'ok ' if ok else 'BAD'} {title}{(' — ' + detail) if detail else ''}")
        return ok

    print(f'Creating disposable database {database}')
    created = psql('postgres', f'CREATE DATABASE {database}')
    if created.returncode != 0:
        raise SystemExit(created.stderr)

    try:
        step('migrate', manage(database, 'migrate', '--noinput').returncode == 0)
        legacy = manage(database, 'shell', '-c', LEGACY_TABLES)
        step('create managed=False legacy tables', legacy.returncode == 0)

        seeded = manage(database, 'shell', '-c', SEED)
        if not step('seed a playable game', seeded.returncode == 0):
            print(seeded.stdout[-3000:], seeded.stderr[-3000:])
            raise SystemExit('seeding failed')
        (EVIDENCE / 'phase1-seed.txt').write_text(
            seeded.stdout + seeded.stderr, encoding='utf-8')

        probed = manage(database, 'shell', '-c', PROBE)
        if probed.returncode != 0:
            print(probed.stdout[-4000:], probed.stderr[-4000:])
            raise SystemExit('probe failed')
        (EVIDENCE / 'phase1-probe-log.txt').write_text(
            probed.stdout + probed.stderr, encoding='utf-8')
        marker = '---INVENTORY-JSON---'
        payload = probed.stdout.split(marker, 1)[1].strip()
        inventory = json.loads(payload)
        (EVIDENCE / 'dimension-inventory.json').write_text(
            json.dumps(inventory, indent=2, sort_keys=True), encoding='utf-8')

        step('dimensions discovered',
             inventory['totals']['dimensions'] > 0,
             f"{inventory['totals']['dimensions']} across "
             f"{inventory['totals']['decision_types']} decision types")
        step('every decision type reachable by PATCH was probed',
             inventory['totals']['unprobed_types'] == 0,
             f"{inventory['totals']['unprobed_types']} unprobed")

        divergences = inventory['path_uniformity']['divergences']
        step('full and partial APIs refuse the same payloads',
             len(divergences) == 0,
             f'{len(divergences)} divergence(s)')

        # Value-loop probe runs last: it resolves the round, which mutates the
        # game the inventory probe read from.
        loop = manage(database, 'shell', '-c', VALUE_LOOP, timeout=1800)
        (EVIDENCE / 'value-loop-log.txt').write_text(
            loop.stdout + loop.stderr, encoding='utf-8')
        if loop.returncode != 0:
            print(loop.stdout[-3000:], loop.stderr[-3000:])
            step('negative-investment value-loop probe ran', False)
        else:
            marker2 = '---VALUE-LOOP-JSON---'
            vl = json.loads(loop.stdout.split(marker2, 1)[1].strip())
            (EVIDENCE / 'value-loop.json').write_text(
                json.dumps(vl, indent=2, sort_keys=True), encoding='utf-8')
            step('negative-investment value-loop probe ran', True)
            # The interesting result is a failure: a negative investment that
            # pays the team is a risk-free value loop.
            step('a negative ESG investment does not pay the team',
                 not vl['value_loop_confirmed'],
                 f"cash advantage {vl['probe_advantage_cash']}")

        sweep = manage(database, 'shell', '-c', NEGATIVE_SWEEP, timeout=2400)
        (EVIDENCE / 'negative-sweep-log.txt').write_text(
            sweep.stdout + sweep.stderr, encoding='utf-8')
        if sweep.returncode != 0:
            print(sweep.stdout[-3000:], sweep.stderr[-3000:])
            step('negative-value sweep ran', False)
        else:
            marker3 = '---NEGATIVE-SWEEP-JSON---'
            sw = json.loads(sweep.stdout.split(marker3, 1)[1].strip())
            (EVIDENCE / 'negative-sweep.json').write_text(
                json.dumps(sw, indent=2, sort_keys=True), encoding='utf-8')
            step('negative-value sweep ran', True,
                 f"{len(sw['fields_measured'])} fields measured")
            step('no negative field pays the team',
                 not sw['fields_that_pay'],
                 f"pays: {', '.join(sw['fields_that_pay']) or 'none'}")

        record = {
            'generated_at': datetime.datetime.now(
                datetime.timezone.utc).isoformat(),
            'code_revision': revision,
            'working_tree_clean': dirty == '',
            'database': database,
            'steps': steps,
            'all_steps_as_expected': all(s['as_expected'] for s in steps),
        }
        (EVIDENCE / 'phase1-provenance.json').write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding='utf-8')
        print(f"\nall steps as expected: {record['all_steps_as_expected']}")
        return 0 if record['all_steps_as_expected'] else 1
    finally:
        if not options.keep:
            psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
            print(f'Dropped {database}')


LEGACY_TABLES = r'''
from django.apps import apps
from django.db import connection
existing = set(connection.introspection.table_names())
unmanaged = [m for m in apps.get_models() if not m._meta.managed]
for m in unmanaged:
    m._meta.managed = True
created = []
with connection.schema_editor() as editor:
    for m in unmanaged:
        if m._meta.db_table not in existing:
            editor.create_model(m); created.append(m._meta.db_table)
for m in unmanaged:
    m._meta.managed = False
print('created', len(created), 'legacy tables')
'''

SEED = r'''
from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
# `setup_test_game` requires a Django superuser to own the game it creates.
if not DjangoUser.objects.filter(is_superuser=True).exists():
    DjangoUser.objects.create_superuser('adversarial-owner', 'a@example.com', 'x')
call_command('load_all_scenarios', verbosity=0)
call_command('setup_test_game', verbosity=1)
from core.models import Game, Team, Round
game = Game.objects.order_by('-id').first()
print('game', game.id, game.name, 'round', game.current_round)
print('teams', list(Team.objects.filter(game=game).values_list('id', 'name')))
print('rounds', list(Round.objects.filter(game=game).values_list('round_number', 'status')))
'''

PROBE = (HERE / 'probe_body.py').read_text(encoding='utf-8')
VALUE_LOOP = (HERE / 'value_loop_body.py').read_text(encoding='utf-8')
NEGATIVE_SWEEP = (HERE / 'negative_sweep_body.py').read_text(encoding='utf-8')
SEED_PROBE = (HERE / 'seed_probe_body.py').read_text(encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
