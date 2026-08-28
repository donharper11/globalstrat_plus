#!/usr/bin/env python3
"""GSP-CRV2-04 evidence harness.

Runs against a **disposable database created for this run**, never the
competition stack, and never the test runner's database. The distinction
matters: the test runner builds its schema from the models with migrations
disabled, so a guard proven only there is a guard proven in the one environment
that does not use the migration. This harness applies migration 0070 and then
attacks what the migration installed.

Everything destructive — dropping a trigger, rewriting a sealed audit row,
deleting one — happens inside that database and only there. It is dropped when
the run finishes.
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
EVIDENCE = ROOT / 'evidence' / 'audit-integrity'

DB_HOST = os.environ.get('DB_HOST', '192.168.50.38')
DB_USER = os.environ.get('DB_USER', 'donwh')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED-CREDENTIAL-V2-048***')
DB_PORT = os.environ.get('DB_PORT', '5432')


def psql(database, sql, capture=True):
    env = {**os.environ, 'PGPASSWORD': DB_PASSWORD}
    result = subprocess.run(
        ['psql', '-h', DB_HOST, '-p', DB_PORT, '-U', DB_USER, '-d', database,
         '-v', 'ON_ERROR_STOP=0', '-c', sql],
        capture_output=capture, text=True, env=env)
    return result


def manage(database, *args, env_extra=None):
    env = {**os.environ, 'DB_NAME': database, 'DB_HOST': DB_HOST,
           'DB_USER': DB_USER, 'DB_PASSWORD': DB_PASSWORD, 'DB_PORT': DB_PORT}
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, 'manage.py', *args],
        cwd=BACKEND, capture_output=True, text=True, env=env)


def write(name, text):
    path = EVIDENCE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def provenance():
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                              capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain',
                            '--untracked-files=no'], cwd=REPO,
                           capture_output=True, text=True).stdout.strip()
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
    import django
    django.setup()
    from core.services.build_identity import build_identity
    identity = build_identity()
    return {
        'generated_at': datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        'code_revision': revision,
        'source_tree_sha256': identity['source_tree_sha256'],
        'working_tree_clean': dirty == '',
        'uncommitted': dirty.splitlines(),
        'database_host': DB_HOST,
        'connecting_role': DB_USER,
        'python': sys.version.split()[0],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', default=None)
    parser.add_argument('--keep', action='store_true',
                        help='Do not drop the disposable database.')
    options = parser.parse_args()

    stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    database = options.database or f'gsp_audit_evidence_{stamp}'

    record = provenance()
    if not record['working_tree_clean']:
        raise SystemExit(
            'Refusing to certify from a dirty tree:\n  '
            + '\n  '.join(record['uncommitted']))
    record['evidence_database'] = database
    transcript = []

    def step(title, result, expect_failure=False):
        ok = (result.returncode != 0) if expect_failure else (
            result.returncode == 0)
        transcript.append({
            'step': title,
            'returncode': result.returncode,
            'as_expected': ok,
            'stdout': result.stdout,
            'stderr': result.stderr,
        })
        print(f"  {'ok ' if ok else 'BAD'} {title}")
        return ok

    print(f'Creating disposable database {database}')
    created = psql('postgres', f'CREATE DATABASE {database}')
    if created.returncode != 0:
        raise SystemExit(created.stderr)

    try:
        print('Applying migrations (this is the path production uses)')
        step('migrate', manage(database, 'migrate', '--noinput'))

        # 1. The migration SQL itself.
        sql = []
        for name in ('0069_audit_integrity', '0070_audit_guards'):
            result = manage(database, 'sqlmigrate', 'core', name)
            sql.append(f'-- ===== core.{name} =====\n{result.stdout}')
        write('migration-sql.txt', '\n'.join(sql))

        # 2. What the migration actually installed.
        step('guards installed by migration',
             manage(database, 'install_audit_guards', '--check'))
        triggers = psql(database, """
            SELECT c.relname AS table, t.tgname AS trigger,
                   p.proname AS function,
                   CASE t.tgtype & 32 WHEN 32 THEN 'TRUNCATE'
                        ELSE 'UPDATE/DELETE' END AS fires_on,
                   t.tgenabled AS enabled
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_proc p ON p.oid = t.tgfoid
            WHERE NOT t.tgisinternal
              AND (t.tgname LIKE '%_append_only'
                   OR t.tgname LIKE '%_no_truncate')
            ORDER BY c.relname, t.tgname""")
        write('triggers.txt', triggers.stdout + triggers.stderr)

        # 3. Privileges and ownership, as they really are.
        privileges = psql(database, """
            SELECT tablename, tableowner,
                   has_table_privilege(tableowner, tablename, 'UPDATE') AS owner_update,
                   has_table_privilege(tableowner, tablename, 'DELETE') AS owner_delete
            FROM pg_tables
            WHERE tablename IN ('competition_decision_audit_event',
                                'competition_operator_audit_event',
                                'competition_resolution_manifest',
                                'competition_sensitive_read_event',
                                'competition_audit_chain')
            ORDER BY tablename""")
        role_sql = manage(database, 'install_audit_guards',
                          '--role-sql', 'globalstrat_app')
        write('privileges.txt',
              'Ownership and owner privileges on the audit tables\n'
              '=================================================\n'
              + privileges.stdout + privileges.stderr
              + '\nThe connecting role owns these tables, so the reject layer '
                'is the triggers,\nnot the grants. SQL that provisions a '
                'non-owner application role:\n\n'
              + role_sql.stdout)

        # 4. The legacy tables migrations do not create.
        #    Ten models are managed=False: `users`, `enrollment`, `course`,
        #    `section` and the grading tables are raw-SQL tables that no
        #    migration builds, so a freshly migrated database has the audit
        #    tables and the triggers but cannot serve a request. The test
        #    runner solves this by flipping the flag; the same is done here so
        #    the walkthrough can exercise real HTTP against the migrated
        #    schema.
        legacy = manage(database, 'shell', '-c', LEGACY_TABLES_SCRIPT)
        step('create managed=False legacy tables', legacy)
        write('legacy-tables.txt', legacy.stdout + legacy.stderr)

        # 5. Seed a round's worth of audit rows through the application.
        seeded = manage(database, 'shell', '-c', SEED_SCRIPT)
        if not step('seed audit rows through the ORM', seeded):
            print(seeded.stdout, seeded.stderr)
            raise SystemExit('seeding failed')
        write('seed.txt', seeded.stdout + seeded.stderr)

        # 6. Chain and anchor, verified.
        backup_dir = str(EVIDENCE / 'anchor-store')
        env_extra = {'COMPETITION_BACKUP_DIR': backup_dir}
        step('seal', manage(database, 'seal_audit_chain', '--json',
                            env_extra=env_extra))
        anchor = manage(database, 'export_audit_anchor', '--json',
                        env_extra=env_extra)
        step('export anchor', anchor)
        write('anchor-export.json', anchor.stdout)
        verified = manage(database, 'verify_audit_chain', '--json',
                          env_extra=env_extra)
        step('verify (clean)', verified)
        write('chain-verification-clean.json', verified.stdout)

        # 7. Negative transcripts: every bypass, attempted for real.
        negatives = []
        for title, statement in NEGATIVE_STATEMENTS:
            result = psql(database, statement)
            refused = 'ERROR:' in (result.stdout + result.stderr)
            negatives.append(
                f'$ psql -c "{statement.strip()}"\n'
                f'{result.stdout}{result.stderr}'
                f'--> {"REFUSED" if refused else "!!! PERMITTED !!!"}\n')
            print(f"  {'ok ' if refused else 'BAD'} refused: {title}")
        orm = manage(database, 'shell', '-c', ORM_BYPASS_SCRIPT)
        step('ORM bypasses refused', orm)
        write('negative-transcripts.txt',
              'Every write path that skips Model.save(), attempted against a\n'
              'real database with the migration applied.\n'
              '============================================================\n\n'
              + '\n'.join(negatives)
              + '\nSame attempts through the ORM and the admin:\n\n'
              + orm.stdout + orm.stderr)

        # 8. The privileged change, and proof the external check catches it.
        tamper = []
        table = 'competition_decision_audit_event'
        tamper.append(psql(database,
                           f'DROP TRIGGER {table}_append_only ON {table}'))
        tamper.append(psql(
            database,
            f"UPDATE {table} SET payload = '{{\"budget\": 999999}}'::jsonb "
            f"WHERE id = (SELECT MIN(id) FROM {table})"))
        reinstall = manage(database, 'install_audit_guards')
        broken = manage(database, 'verify_audit_chain', '--json',
                        env_extra=env_extra)
        step('verify FAILS after a privileged edit', broken, expect_failure=True)
        write('chain-verification-tampered.json', broken.stdout)
        write('tamper-transcript.txt',
              'A change no trigger can stop, because the trigger is dropped\n'
              'first and reinstalled after. The tables look untouched.\n'
              '===========================================================\n\n'
              + ''.join(r.stdout + r.stderr for r in tamper)
              + reinstall.stdout + reinstall.stderr
              + '\n$ manage.py verify_audit_chain\n'
              + broken.stdout + broken.stderr
              + f'\n--> exit {broken.returncode} '
                f'({"detected" if broken.returncode else "MISSED"})\n')

        # 9. Read evidence walkthrough, end to end over HTTP.
        walk = manage(database, 'shell', '-c', WALKTHROUGH_SCRIPT)
        step('read-evidence walkthrough', walk)
        write('read-evidence-walkthrough.txt', walk.stdout + walk.stderr)

        record['steps'] = transcript
        record['all_steps_as_expected'] = all(s['as_expected'] for s in transcript)
        write('provenance.json', json.dumps(record, indent=2, sort_keys=True))

        # 10. Checksums last.
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


LEGACY_TABLES_SCRIPT = r'''
from django.apps import apps
from django.db import connection

existing = set(connection.introspection.table_names())
unmanaged = [m for m in apps.get_models() if not m._meta.managed]
created = []
for model in unmanaged:
    model._meta.managed = True
with connection.schema_editor() as editor:
    for model in unmanaged:
        if model._meta.db_table in existing:
            continue
        editor.create_model(model)
        created.append(model._meta.db_table)
for model in unmanaged:
    model._meta.managed = False
print(f'{len(unmanaged)} managed=False models; created {len(created)} tables')
for name in sorted(created):
    print('  ', name)
'''

SEED_SCRIPT = r'''
from django.contrib.auth.models import User as DjangoUser
from django.utils import timezone
from core.models import (DecisionAuditEvent, OperatorAuditEvent,
                         ResolutionManifest, Game, Round, Scenario, Team, User)
from core.models.scenario import FirmStarterProfile, MarketDefinition

owner = DjangoUser.objects.create(username='evidence-owner')
user = User.objects.create(username='evidence-instructor', role='instructor',
                           password_hash='x')
scenario = Scenario.objects.create(name='Evidence', industry_label='T',
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
game = Game.objects.create(scenario=scenario, name='Evidence game',
                           current_round=1, status='active', created_by=owner)
rnd = Round.objects.create(game=game, round_number=1, status='open',
                           opened_at=timezone.now())
team = Team.objects.create(game=game, name='T1', firm_starter_profile=profile,
                           performance_index=100, cash_on_hand=1000,
                           total_equity=1000)
for i in range(3):
    DecisionAuditEvent.objects.create(
        game=game, team=team, round=rnd, user=user, action='save',
        endpoint='/api/evidence/', payload={'budget': 1000 + i})
OperatorAuditEvent.objects.create(
    game=game, round=rnd, user=user, action='close_round', outcome='committed',
    reason='evidence', before={'status': 'open'}, after={'status': 'closed'})
OperatorAuditEvent.objects.create(
    game=game, round=rnd, user=user, action='close_round', outcome='rejected',
    reason='lost the race', conflict={'expected': 'open'}, before={}, after={})
manifest = ResolutionManifest.objects.create(
    game=game, round=rnd, schema_version=2, seed='evidence',
    input_manifest={'seed': 'evidence'}, input_sha256='a' * 64,
    decision_event_count=3)
ResolutionManifest.objects.filter(pk=manifest.pk).update(
    output_sha256='b' * 64, completed_at=timezone.now())
print('seeded game', game.id, 'team', team.id, 'round', rnd.id)
print('decision audit rows :', DecisionAuditEvent.objects.count())
print('operator audit rows :', OperatorAuditEvent.objects.count())
print('manifests           :', ResolutionManifest.objects.count())
'''

NEGATIVE_STATEMENTS = [
    ('raw UPDATE on decision audit',
     "UPDATE competition_decision_audit_event SET action = 'tampered' "
     "WHERE id = (SELECT MIN(id) FROM competition_decision_audit_event)"),
    ('raw DELETE on decision audit',
     "DELETE FROM competition_decision_audit_event "
     "WHERE id = (SELECT MIN(id) FROM competition_decision_audit_event)"),
    ('raw UPDATE on operator audit',
     "UPDATE competition_operator_audit_event SET outcome = 'committed' "
     "WHERE outcome = 'rejected'"),
    ('raw DELETE on operator audit',
     "DELETE FROM competition_operator_audit_event WHERE outcome = 'rejected'"),
    ('raw UPDATE on a completed manifest',
     "UPDATE competition_resolution_manifest SET output_sha256 = repeat('c', 64) "
     "WHERE completed_at IS NOT NULL"),
    ('raw DELETE on a manifest',
     'DELETE FROM competition_resolution_manifest'),
    ('raw UPDATE on the chain itself',
     "UPDATE competition_audit_chain SET entry_sha256 = repeat('0', 64)"),
    ('TRUNCATE the decision audit',
     'TRUNCATE competition_decision_audit_event CASCADE'),
]

ORM_BYPASS_SCRIPT = r'''
from django.db import transaction
from django.contrib import admin as django_admin
from core.models import (AuditChainEntry, DecisionAuditEvent,
                         OperatorAuditEvent, ResolutionManifest,
                         SensitiveReadEvent)

def attempt(label, action):
    try:
        with transaction.atomic():
            action()
    except Exception as error:
        first = str(error).strip().splitlines()[0]
        print(f'REFUSED  {label}\n         {first}')
        return
    print(f'!!! PERMITTED !!!  {label}')

event = DecisionAuditEvent.objects.first()

def resave():
    event.action = 'tampered'
    event.save()

attempt('Model.save() on an existing audit row', resave)
attempt('queryset .update()',
        lambda: DecisionAuditEvent.objects.filter(pk=event.pk).update(action='x'))
attempt('queryset .delete()',
        lambda: DecisionAuditEvent.objects.filter(pk=event.pk).delete())
attempt('operator audit .update()',
        lambda: OperatorAuditEvent.objects.all().update(outcome='committed'))
attempt('completed manifest .update()',
        lambda: ResolutionManifest.objects.filter(
            completed_at__isnull=False).update(output_sha256='d' * 64))
attempt('manifest .delete()',
        lambda: ResolutionManifest.objects.all().delete())

print()
print('Django admin permissions on each audit record:')
for model in (DecisionAuditEvent, OperatorAuditEvent, ResolutionManifest,
              AuditChainEntry, SensitiveReadEvent):
    options = django_admin.site._registry[model]
    print(f'  {model.__name__:<22} add={options.has_add_permission(None)} '
          f'change={options.has_change_permission(None)} '
          f'delete={options.has_delete_permission(None)}')
'''

WALKTHROUGH_SCRIPT = r'''
from io import StringIO
from django.core.management import call_command
from django.test import Client
from django.conf import settings
from core.authentication import create_access_token
from core.models import Game, SensitiveReadEvent, Team, User

# No Course/Section is created: `course` is one of the ten managed=False
# legacy tables that migrations never create, so a migrated database does not
# have it. Cohort ownership is GSP-CRV2-03's boundary and is
# tested there; what this walkthrough has to show is the read record.
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

game = Game.objects.first()
team = Team.objects.first()
instructor = User.objects.get(username='evidence-instructor')
student = User.objects.create(username='evidence-student', role='student',
                              password_hash='x')

def get(user, url):
    client = Client()
    if user is not None:
        client.defaults['HTTP_AUTHORIZATION'] = (
            f'Bearer {create_access_token(user)}')
    response = client.get(url)
    print(f'  {response.status_code}  {"anonymous" if user is None else user.username:<22} {url}')
    return response

print('Reads performed:')
get(instructor, f'/api/games/{game.id}/instructor/teams/{team.id}/decisions/?round=1')
get(student, f'/api/games/{game.id}/teams/{team.id}/decisions/round/1/')
get(None, f'/api/games/{game.id}/teams/{team.id}/decisions/round/1/')

print()
print('What competition_sensitive_read_event recorded:')
for row in SensitiveReadEvent.objects.order_by('id'):
    print(f'  #{row.id} {row.created_at.isoformat()} {row.outcome:<8} '
          f'actor={row.username or "anonymous"!r} game={row.game_id_read} '
          f'team={row.team_id_read} round={row.round_number_read} '
          f'category={row.category} status={row.status_code} '
          f'req={row.request_id}')

print()
print('$ manage.py who_accessed --game %d --team %d --round 1' % (game.id, team.id))
out = StringIO()
call_command('who_accessed', '--game', str(game.id), '--team', str(team.id),
             '--round', '1', stdout=out)
print(out.getvalue())

print('$ manage.py who_accessed --outcome denied')
out = StringIO()
call_command('who_accessed', '--outcome', 'denied', stdout=out)
print(out.getvalue())

print('No response body, header or token is stored. Fields held per row:')
print(' ', ', '.join(f.name for f in SensitiveReadEvent._meta.fields))
'''


if __name__ == '__main__':
    raise SystemExit(main())
