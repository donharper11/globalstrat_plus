#!/usr/bin/env python3
"""GSP-CRV2-04 rework evidence — the TRUNCATE authorization bypass, closed.

Narrow by design. The full harness (`audit_integrity_evidence.py`) still holds
for everything else in this handoff; this run exists to answer one question
against a real migrated database:

    SET globalstrat.allow_truncate = 'on';
    TRUNCATE competition_decision_audit_event;

The application connects as the tables' owner, so it holds TRUNCATE privilege,
and PostgreSQL lets any ordinary session set a custom setting. For as long as
the guard consulted only that setting, this pair emptied the audit log without
dropping a single trigger.

The database here is created for the run and dropped afterwards, and it is
deliberately *not* named the way Django names a test database — that is the
whole point of the check being exercised.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
BACKEND = REPO / 'backend'
EVIDENCE = ROOT / 'evidence' / 'audit-integrity-rework'

DB_HOST = os.environ.get('DB_HOST', '192.168.50.38')
DB_USER = os.environ.get('DB_USER', 'donwh')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED-CREDENTIAL-V2-048***')
DB_PORT = os.environ.get('DB_PORT', '5432')

BYPASS_SQL = ("SET globalstrat.allow_truncate = 'on'; "
              'TRUNCATE competition_decision_audit_event CASCADE')


def psql(database, sql, tuples_only=False):
    env = {**os.environ, 'PGPASSWORD': DB_PASSWORD}
    flags = ['-tA'] if tuples_only else []
    return subprocess.run(
        ['psql', '-h', DB_HOST, '-p', DB_PORT, '-U', DB_USER, '-d', database,
         '-v', 'ON_ERROR_STOP=0', *flags, '-c', sql],
        capture_output=True, text=True, env=env)


def manage(database, *args):
    env = {**os.environ, 'DB_NAME': database, 'DB_HOST': DB_HOST,
           'DB_USER': DB_USER, 'DB_PASSWORD': DB_PASSWORD, 'DB_PORT': DB_PORT}
    return subprocess.run([sys.executable, 'manage.py', *args],
                          cwd=BACKEND, capture_output=True, text=True, env=env)


def write(name, text):
    path = EVIDENCE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def count_rows(database, table):
    result = psql(database, f'SELECT count(*) FROM {table}')
    for line in result.stdout.splitlines():
        if line.strip().isdigit():
            return int(line.strip())
    raise SystemExit(f'could not read a row count:\n{result.stdout}{result.stderr}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--keep', action='store_true')
    options = parser.parse_args()

    stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    # Not `test_...`: a database that the guard would legitimately let reset
    # itself could not demonstrate the guard.
    database = f'gsp_truncate_rework_{stamp}'

    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain',
                            '--untracked-files=no'], cwd=REPO,
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit('Refusing to certify from a dirty tree:\n  '
                         + '\n  '.join(dirty.splitlines()))
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
    import django
    django.setup()
    from core.services.build_identity import build_identity
    from core.services import audit_guards

    record = {
        'generated_at': datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        'code_revision': revision,
        'source_tree_sha256': build_identity()['source_tree_sha256'],
        'working_tree_clean': True,
        'evidence_database': database,
        'database_is_named_like_a_test_database': database.startswith(
            audit_guards.TEST_DATABASE_PREFIX),
        'connecting_role': DB_USER,
    }
    transcript = []

    def step(title, ok, detail=''):
        transcript.append({'step': title, 'as_expected': ok, 'detail': detail})
        print(f"  {'ok ' if ok else 'BAD'} {title}")
        return ok

    created = psql('postgres', f'CREATE DATABASE {database}')
    if created.returncode != 0:
        raise SystemExit(created.stderr)
    print(f'Created disposable database {database}')

    try:
        migrated = manage(database, 'migrate', '--noinput')
        step('migrate (0072 included)', migrated.returncode == 0)
        write('migrate.txt', migrated.stdout + migrated.stderr)

        sqlmigrate = manage(database, 'sqlmigrate', 'core',
                            '0072_truncate_guard_authorization')
        write('migration-0072-sql.txt', sqlmigrate.stdout + sqlmigrate.stderr)

        installed = psql(database, """
            SELECT p.proname, pg_get_functiondef(p.oid)
            FROM pg_proc p
            WHERE p.proname IN ('competition_truncate_is_allowed',
                                'competition_audit_reject_truncate')
            ORDER BY p.proname""")
        write('installed-functions.txt', installed.stdout + installed.stderr)
        step('the corrected function body reached the database',
             'db_name LIKE' in installed.stdout)

        seeded = manage(database, 'shell', '-c', SEED_SCRIPT)
        step('seed one audit row through the ORM', seeded.returncode == 0)
        write('seed.txt', seeded.stdout + seeded.stderr)

        table = 'competition_decision_audit_event'
        before = count_rows(database, table)

        # The audited bypass, run verbatim as the application's own role.
        bypass = psql(database, BYPASS_SQL)
        refused = 'ERROR:' in (bypass.stdout + bypass.stderr)
        after = count_rows(database, table)
        step('the audited bypass is refused', refused)
        step('the rows survive it', before == after and before > 0,
             f'{before} rows before, {after} after')

        plain = psql(database, f'TRUNCATE {table} CASCADE')
        plain_refused = 'ERROR:' in (plain.stdout + plain.stderr)
        step('plain TRUNCATE is refused', plain_refused)

        # Asked with the setting deliberately on, which is the state the
        # audited version treated as sufficient authorization.
        candidates = {
            'globalstrat_plus': False,       # the competition database
            database: False,                 # this evidence database
            'testing_db': False,             # `_` is a LIKE wildcard
            'test_globalstrat_plus': True,   # Django's isolated test database
        }
        query = f"SET {audit_guards.TRUNCATE_SETTING} = 'on'; " + ' UNION ALL '.join(
            f"SELECT '{name}', {audit_guards.POLICY_FUNCTION}('{name}')"
            for name in candidates)
        policy = psql(database, query, tuples_only=True)
        decided = dict(
            (line.split('|')[0], line.split('|')[1] == 't')
            for line in policy.stdout.strip().splitlines() if '|' in line)
        step('only an isolated test database is allowed to reset itself',
             decided == candidates, f'{decided}')
        write('policy-decisions.txt',
              f"With {audit_guards.TRUNCATE_SETTING} deliberately set to 'on' —\n"
              'the state the audited version treated as sufficient — which\n'
              'database names the policy would let reset themselves:\n'
              '===========================================================\n\n'
              + '\n'.join(f'  {name:<28} {"ALLOWED" if allowed else "refused"}'
                          for name, allowed in decided.items())
              + f'\n\nexpected: {candidates}\n'
              + f'observed: {decided}\n'
              + policy.stderr)

        write('bypass-transcript.txt',
              'The exact statement pair from the audit, run as the application\n'
              'role against a migrated database that is not named like a test\n'
              'database.\n'
              '==========================================================\n\n'
              f'rows in {table} before: {before}\n\n'
              f'$ psql -c "{BYPASS_SQL}"\n'
              + bypass.stdout + bypass.stderr
              + f'--> {"REFUSED" if refused else "!!! PERMITTED !!!"}\n\n'
              f'$ psql -c "TRUNCATE {table} CASCADE"\n'
              + plain.stdout + plain.stderr
              + f'--> {"REFUSED" if plain_refused else "!!! PERMITTED !!!"}\n\n'
              f'rows in {table} after: {after}\n')

        record['steps'] = transcript
        record['all_steps_as_expected'] = all(s['as_expected'] for s in transcript)
        record['rows_before'] = before
        record['rows_after'] = after
        write('provenance.json', json.dumps(record, indent=2, sort_keys=True))

        lines = []
        for path in sorted(EVIDENCE.rglob('*')):
            if path.is_file() and path.name != 'SHA256SUMS':
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                lines.append(f'{digest}  {path.relative_to(EVIDENCE)}')
        write('SHA256SUMS', '\n'.join(lines) + '\n')
        print(f'\nEvidence written to {EVIDENCE} ({len(lines)} files)')
        print('all steps as expected:', record['all_steps_as_expected'])
        return 0 if record['all_steps_as_expected'] else 1
    finally:
        if not options.keep:
            psql('postgres', f'DROP DATABASE IF EXISTS {database} WITH (FORCE)')
            print(f'Dropped {database}')


SEED_SCRIPT = r'''
from django.contrib.auth.models import User as DjangoUser
from django.utils import timezone
from core.models import (DecisionAuditEvent, Game, Round, Scenario, Team, User)
from core.models.scenario import FirmStarterProfile, MarketDefinition

owner = DjangoUser.objects.create(username='rework-owner')
user = User.objects.create(username='rework-user', role='instructor',
                           password_hash='x')
scenario = Scenario.objects.create(name='Rework', industry_label='T',
                                   description='d', starting_cash=1000,
                                   num_rounds=2)
market = MarketDefinition.objects.create(
    scenario=scenario, name='Home', code='HM', description='d',
    currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
    entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
    infrastructure_quality=1)
profile = FirmStarterProfile.objects.create(
    scenario=scenario, profile_name='S', description='d', home_market=market,
    starting_cash=1000, starting_debt=0)
game = Game.objects.create(scenario=scenario, name='Rework game',
                           current_round=1, status='active', created_by=owner)
rnd = Round.objects.create(game=game, round_number=1, status='open',
                           opened_at=timezone.now())
team = Team.objects.create(game=game, name='T1', firm_starter_profile=profile,
                           performance_index=100, cash_on_hand=1000,
                           total_equity=1000)
for i in range(3):
    DecisionAuditEvent.objects.create(
        game=game, team=team, round=rnd, user=user, action='save',
        endpoint='/api/rework/', payload={'budget': 1000 + i})
print('decision audit rows:', DecisionAuditEvent.objects.count())
'''


if __name__ == '__main__':
    raise SystemExit(main())
