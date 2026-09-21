"""A committed game deletion leaves a durable audit record (R45, V2-134).

Before this work the only trace of a committed deletion was a `core.lifecycle`
log line: `OperatorAuditEvent` holds a PROTECTED key to the game, so a row
saying "this game was deleted" would have blocked the deletion it described.
`GameDeletionAuditEvent` carries the same facts as plain values and no key to
the game at all.

Three things are proven here, each against real PostgreSQL and each through
the registered route with a signed JWT where a route is involved:

* the record is written in the deletion's transaction -- never a deletion
  without its record, never a record without its deletion;
* the table is a first-class audit table: append-only and truncate triggers,
  hash chain, read-only admin, and an application role that holds INSERT and
  SELECT on it and nothing else;
* every list that names the audit tables names this one, including the shell
  script that cannot import the Python tuple.
"""
import importlib
import os
import pathlib
import re
from unittest import mock

from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import OperatorAuditEvent, Round, User
from core.models.audit_integrity import AuditChainEntry
from core.models.core import Game, Team
from core.models.course import Course, Section
from core.services import audit_chain, audit_guards
from core.tests.test_operator_concurrency import build_minimal_game

TABLE = 'competition_game_deletion_audit_event'
MIGRATION = 'core.migrations.0088_game_deletion_audit_event'
REASON = 'created by mistake during setup'
REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[3]


def deletion_model():
    """Imported late so the red run fails test by test, not at collection."""
    from core.models import GameDeletionAuditEvent
    return GameDeletionAuditEvent


def say(response):
    body = getattr(response, 'data', None)
    if body is None:
        body = response.content[:300]
    return f'{response.status_code} {body!r}'


class DeletableGameMixin:
    """An owned, never-operated game, and JWT clients to delete it with."""

    def make_world(self):
        tag = f'{id(self) % 100000}'
        self.owner = User.objects.create(
            username=f'owner-{tag}', role='instructor', password_hash='x')
        self.rival = User.objects.create(
            username=f'rival-{tag}', role='instructor', password_hash='x')
        self.course = Course.objects.create(
            course_code=f'DEL{tag}', course_name='Deletion course',
            instructor_id=self.owner.user_id, is_active=True)
        self.section = Section.objects.create(
            course_id=self.course.course_id, section_code='S-DEL',
            section_name='Deletion section', max_teams=8, team_size_min=1,
            team_size_max=5, is_active=True)
        self.game, self.teams = build_minimal_game(f'delaudit-{tag}')
        Game.objects.filter(pk=self.game.pk).update(
            section_id=self.section.section_id, status='setup', current_round=0)
        self.game.refresh_from_db()
        Round.objects.create(game=self.game, round_number=0, status='pending')

    def client_for(self, user, language=None):
        client = APIClient()
        credentials = {
            'HTTP_AUTHORIZATION': f'Bearer {create_access_token(user)}'}
        if language:
            credentials['HTTP_ACCEPT_LANGUAGE'] = language
        client.credentials(**credentials)
        # A 500 is an outcome under test here, not a test error.
        client.raise_request_exception = False
        return client

    def delete(self, user, body=None, request_id=None, language=None):
        extra = {'HTTP_X_REQUEST_ID': request_id} if request_id else {}
        return self.client_for(user, language).delete(
            f'/api/games/{self.game.pk}/delete/',
            body if body is not None else {'reason': REASON}, format='json',
            **extra)


# ---------------------------------------------------------------------------
# 1. The record, and its transaction
# ---------------------------------------------------------------------------

class DeletionRecordTests(DeletableGameMixin, TestCase):

    def setUp(self):
        self.make_world()

    def test_a_committed_deletion_leaves_one_durable_record(self):
        game_id, name = self.game.pk, self.game.name
        scenario = self.game.scenario

        response = self.delete(self.owner, request_id='req-delete-audit-1')

        self.assertEqual(response.status_code, 200, say(response))
        self.assertFalse(Game.objects.filter(pk=game_id).exists())
        row = deletion_model().objects.get()
        self.assertEqual(row.game_id_deleted, game_id)
        self.assertEqual(row.game_name, name)
        self.assertEqual(row.scenario_id_value, scenario.pk)
        self.assertEqual(row.scenario_name, scenario.name)
        self.assertEqual(row.actor_user_id, self.owner.user_id)
        self.assertEqual(row.username, self.owner.username)
        self.assertEqual(row.action, 'delete_game')
        self.assertEqual(row.reason, REASON)
        self.assertEqual(row.before, {
            'game_id': game_id, 'name': name, 'status': 'setup',
            'current_round': 0})
        self.assertEqual(row.request_id, 'req-delete-audit-1')
        self.assertEqual(response.data['request_id'], row.request_id)
        self.assertIsNotNone(row.created_at)

    def test_the_record_holds_no_key_to_anything(self):
        """A key to the game is what made this record impossible before."""
        relations = [field.name for field in deletion_model()._meta.get_fields()
                     if field.is_relation]
        self.assertEqual(relations, [])
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid "
                "WHERE t.relname = %s AND c.contype = 'f'", [TABLE])
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_the_log_line_is_kept(self):
        with self.assertLogs('core.lifecycle', 'WARNING') as logs:
            response = self.delete(self.owner)
        line = '\n'.join(logs.output)
        self.assertIn('delete_game committed', line)
        self.assertIn(REASON, line)
        self.assertIn(response.data['request_id'], line)
        self.assertEqual(deletion_model().objects.count(), 1)

    def test_the_record_is_english_whatever_the_operator_reads(self):
        """R44: one record, one language."""
        response = self.delete(self.owner, language='zh-CN')

        self.assertEqual(response.status_code, 200, say(response))
        row = deletion_model().objects.get()
        self.assertEqual(row.action, 'delete_game')
        self.assertEqual(row.reason, REASON)
        self.assertEqual(row.before['status'], 'setup')

    def test_no_deletion_without_its_record(self):
        """The record cannot be written, so the game must still be there."""
        with mock.patch(
                'core.services.competition_audit.record_game_deletion',
                side_effect=RuntimeError('audit table unavailable')):
            response = self.delete(self.owner)

        self.assertEqual(response.status_code, 500, say(response))
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())
        self.assertEqual(Team.objects.filter(game=self.game).count(), 2)
        self.assertEqual(Round.objects.filter(game=self.game).count(), 1)
        self.assertEqual(deletion_model().objects.count(), 0)

    def test_no_record_without_its_deletion(self):
        """A failure injected after the record is written undoes the record."""
        from core.services import competition_audit
        real = competition_audit.record_game_deletion
        written = []

        def write_then_fail(*args, **kwargs):
            written.append(real(*args, **kwargs))
            self.assertEqual(deletion_model().objects.count(), 1,
                             'the injection must come after the write')
            raise RuntimeError('failure after the record was written')

        with mock.patch(
                'core.services.competition_audit.record_game_deletion',
                side_effect=write_then_fail):
            response = self.delete(self.owner)

        self.assertEqual(response.status_code, 500, say(response))
        self.assertEqual(len(written), 1)
        self.assertEqual(deletion_model().objects.count(), 0)
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())
        self.assertEqual(Team.objects.filter(game=self.game).count(), 2)

    def test_a_refused_delete_writes_no_deletion_record(self):
        no_reason = self.delete(self.owner, body={})
        rival = self.delete(self.rival)
        self.client_for(self.owner).post(
            f'/api/games/{self.game.pk}/activate/', {}, format='json')
        has_record = self.delete(self.owner)

        self.assertEqual(no_reason.status_code, 400, say(no_reason))
        self.assertEqual(rival.status_code, 403, say(rival))
        self.assertEqual(has_record.status_code, 409, say(has_record))
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())
        self.assertEqual(deletion_model().objects.count(), 0)
        # The refusals are still ordinary rejected operator rows.
        self.assertTrue(OperatorAuditEvent.objects.filter(
            game=self.game, action='delete_game', outcome='rejected').exists())

    def test_a_cascade_stopped_by_a_protected_row_writes_no_record(self):
        self.client_for(self.owner).post(
            f'/api/games/{self.game.pk}/activate/', {}, format='json')
        with mock.patch('core.views.scenario_views._has_permanent_record',
                        return_value=False), \
                self.assertLogs('core.lifecycle', 'ERROR'):
            response = self.delete(self.owner)

        self.assertEqual(response.status_code, 409, say(response))
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())
        self.assertEqual(deletion_model().objects.count(), 0)


class DeletionCommitTests(DeletableGameMixin, TransactionTestCase):
    """Real commits and real rollbacks, so `on_commit` sealing actually runs."""

    reset_sequences = False

    def setUp(self):
        self.make_world()

    def test_a_committed_deletion_is_sealed_into_the_chain(self):
        response = self.delete(self.owner)

        self.assertEqual(response.status_code, 200, say(response))
        row = deletion_model().objects.get()
        self.assertEqual(AuditChainEntry.objects.filter(
            source_table=TABLE, source_id=row.pk).count(), 1)
        self.assertEqual(list(audit_chain._pending(TABLE)), [])
        report = audit_chain.verify_chain()
        self.assertTrue(report['ok'], report['problems'])
        self.assertEqual(report['unsealed'][TABLE], 0)

    def test_a_failure_after_the_record_leaves_neither_and_seals_nothing(self):
        from core.services import competition_audit
        real = competition_audit.record_game_deletion

        def write_then_fail(*args, **kwargs):
            real(*args, **kwargs)
            raise RuntimeError('failure after the record was written')

        with mock.patch(
                'core.services.competition_audit.record_game_deletion',
                side_effect=write_then_fail):
            response = self.delete(self.owner)

        self.assertEqual(response.status_code, 500, say(response))
        self.assertTrue(Game.objects.filter(pk=self.game.pk).exists())
        self.assertEqual(Team.objects.filter(game=self.game).count(), 2)
        self.assertEqual(deletion_model().objects.count(), 0)
        self.assertEqual(
            AuditChainEntry.objects.filter(source_table=TABLE).count(), 0)

    def test_an_edit_made_with_the_trigger_dropped_is_detected(self):
        self.delete(self.owner)
        row = deletion_model().objects.get()
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TRIGGER {TABLE}_append_only ON {TABLE}')
            try:
                cursor.execute(f'UPDATE {TABLE} SET reason = %s WHERE id = %s',
                               ['rewritten afterwards', row.pk])
            finally:
                audit_guards.install(connection)
        report = audit_chain.verify_chain()
        self.assertFalse(report['ok'])
        self.assertIn('row_modified',
                      {problem['kind'] for problem in report['problems']})


# ---------------------------------------------------------------------------
# 2. A first-class audit table
# ---------------------------------------------------------------------------

class DeletionTableGuardTests(TestCase):

    def setUp(self):
        self.row = deletion_model().objects.create(
            game_id_deleted=41, game_name='Mistaken game',
            scenario_id_value=3, scenario_name='Scenario',
            actor_user_id=7, username='operator', action='delete_game',
            reason=REASON, before={'game_id': 41, 'status': 'setup'},
            request_id='srv-guard-del-1')

    def test_the_table_is_registered_for_protection(self):
        self.assertIn(TABLE, audit_guards.PROTECTED_TABLES)
        self.assertEqual(audit_guards.missing_guards(connection), [])
        live = {(row['table'], row['trigger'])
                for row in audit_guards.installed_triggers(connection)}
        self.assertIn((TABLE, f'{TABLE}_append_only'), live)
        self.assertIn((TABLE, f'{TABLE}_no_truncate'), live)

    def test_the_model_refuses_a_re_save(self):
        self.row.reason = 'rewritten'
        with self.assertRaises(ValueError):
            self.row.save()

    def test_a_direct_sql_update_is_refused(self):
        with self.assertRaises(Exception) as caught:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(f'UPDATE {TABLE} SET reason = %s WHERE id = %s',
                               ['rewritten', self.row.id])
        self.assertIn('append-only', str(caught.exception).lower())

    def test_a_direct_sql_delete_is_refused(self):
        with self.assertRaises(Exception) as caught:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(f'DELETE FROM {TABLE} WHERE id = %s',
                               [self.row.id])
        self.assertIn('append-only', str(caught.exception).lower())

    def test_orm_update_and_delete_are_refused(self):
        model = deletion_model()
        with self.assertRaises(Exception) as updated:
            with transaction.atomic():
                model.objects.filter(pk=self.row.pk).update(reason='rewritten')
        with self.assertRaises(Exception) as deleted:
            with transaction.atomic():
                model.objects.filter(pk=self.row.pk).delete()
        self.assertIn('append-only', str(updated.exception).lower())
        self.assertIn('append-only', str(deleted.exception).lower())
        self.row.refresh_from_db()
        self.assertEqual(self.row.reason, REASON)

    def test_truncate_is_refused_under_the_non_test_policy(self):
        with self.assertRaises(Exception) as caught:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(
                    f"SET LOCAL {audit_guards.TRUNCATE_SETTING} = 'off'")
                cursor.execute(f'TRUNCATE {TABLE} CASCADE')
        self.assertIn('TRUNCATE is not permitted', str(caught.exception))

    def test_every_column_is_chained(self):
        self.assertIn(TABLE, audit_chain.PROJECTIONS)
        self.assertIn(TABLE, audit_chain.SEAL_ORDER)
        model, fields = audit_chain.PROJECTIONS[TABLE]
        self.assertIs(model, deletion_model())
        self.assertEqual(set(fields),
                         {field.attname for field in model._meta.fields})
        self.assertNotIn(TABLE, audit_chain.UNCHAINED_FIELDS)

    def test_the_admin_shows_it_and_offers_no_way_in(self):
        from django.contrib import admin as django_admin
        options = django_admin.site._registry[deletion_model()]
        self.assertFalse(options.has_add_permission(None))
        self.assertFalse(options.has_change_permission(None))
        self.assertFalse(options.has_delete_permission(None))
        self.assertEqual(
            set(options.get_readonly_fields(None)),
            {field.name for field in deletion_model()._meta.fields})


class DeletionMigrationTests(TestCase):

    def test_the_migration_itself_builds_a_guarded_table_and_reverses(self):
        """Migration 0088, applied and unapplied against real PostgreSQL.

        The test runner builds its database from the models and then installs
        today's guard list, so nothing else in this suite ever executes a
        migration -- and that is exactly the masking that let 0078 ship a table
        with no triggers. Here the table the runner built is dropped, and the
        migration's own operations create it, guard it and remove it again.
        """
        from django.db.migrations.loader import MigrationLoader
        from django.test import override_settings
        # The runner hides every migration module so the database is built
        # from the models; the loader needs them back, from disk only.
        with override_settings(MIGRATION_MODULES={}):
            loader = MigrationLoader(None)
        name = MIGRATION.rsplit('.', 1)[1]
        migration = loader.get_migration('core', name)
        (parent,) = [key for key in migration.dependencies if key[0] == 'core']
        before = loader.project_state(parent)

        def table_exists():
            with connection.cursor() as cursor:
                cursor.execute('SELECT to_regclass(%s)', [TABLE])
                return cursor.fetchone()[0] is not None

        def triggers():
            return {row['trigger']
                    for row in audit_guards.installed_triggers(connection)
                    if row['table'] == TABLE}

        with connection.cursor() as cursor:
            cursor.execute(f'DROP TABLE {TABLE}')
        self.assertFalse(table_exists())

        with connection.schema_editor(atomic=False) as editor:
            migration.apply(before.clone(), editor)
        self.assertTrue(table_exists())
        self.assertEqual(triggers(), {f'{TABLE}_append_only',
                                      f'{TABLE}_no_truncate'})
        self.assertEqual(audit_guards.missing_guards(connection), [])
        row = deletion_model().objects.create(
            game_id_deleted=42, game_name='Built by the migration',
            actor_user_id=7, username='operator', reason=REASON,
            before={}, request_id='srv-migration-1')
        with self.assertRaises(Exception) as caught:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(f'UPDATE {TABLE} SET reason = %s WHERE id = %s',
                               ['rewritten', row.pk])
        self.assertIn('append-only', str(caught.exception).lower())

        # A stored record blocks the reversal that would drop it: each row is
        # the only durable record that its game was deleted (R45).
        with self.assertRaises(Exception) as refused:
            with transaction.atomic(), \
                    connection.schema_editor(atomic=False) as editor:
                migration.unapply(before.clone(), editor)
        self.assertIn('cannot reverse core.0088', str(refused.exception))
        self.assertTrue(table_exists())
        self.assertEqual(deletion_model().objects.count(), 1)

        # The row cannot be removed (append-only), so rebuild the table empty
        # to exercise the reversal that IS allowed.
        with connection.cursor() as cursor:
            cursor.execute(f'DROP TABLE {TABLE}')
        with connection.schema_editor(atomic=False) as editor:
            migration.apply(before.clone(), editor)
        with connection.schema_editor(atomic=False) as editor:
            migration.unapply(before.clone(), editor)
        self.assertFalse(table_exists())
        # Reversing unprotected nothing else, and kept the shared functions.
        self.assertEqual(
            {entry['table']
             for entry in audit_guards.missing_guards(connection)}, {TABLE})
        with connection.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM pg_proc WHERE proname = %s',
                           [audit_guards.REJECT_FUNCTION])
            self.assertEqual(cursor.fetchone()[0], 1)

        # Put back what the rest of the suite expects (the test transaction is
        # rolled back anyway; this keeps the assertion below honest).
        with connection.schema_editor(atomic=False) as editor:
            migration.apply(before.clone(), editor)
        self.assertEqual(audit_guards.missing_guards(connection), [])

    def test_the_migration_creates_the_table_and_guards_it_in_one_file(self):
        migration = importlib.import_module(MIGRATION)
        operations = migration.Migration.operations
        kinds = [type(operation).__name__ for operation in operations]
        self.assertEqual(kinds, ['CreateModel', 'RunPython'])
        self.assertEqual(operations[0].options['db_table'], TABLE)
        self.assertEqual(migration.TABLE, TABLE)


class AuditTableListTests(TestCase):
    """The lists that cannot import one another still have to agree."""

    def test_the_provisioning_script_names_every_append_only_table(self):
        script = (REPOSITORY_ROOT / 'ops' / 'provision-app-role.sh').read_text(
            encoding='utf-8')
        block = re.search(r'APPEND_ONLY_TABLES=\((.*?)\)', script, re.S)
        self.assertIsNotNone(block)
        self.assertEqual(sorted(block.group(1).split()),
                         sorted(audit_guards.PROTECTED_TABLES))
        manifest = re.search(r'^MANIFEST_TABLE=(\S+)$', script, re.M)
        self.assertEqual(manifest.group(1), audit_guards.MANIFEST_TABLE)

    def test_the_seal_order_and_the_projections_name_the_same_tables(self):
        self.assertEqual(set(audit_chain.SEAL_ORDER),
                         set(audit_chain.PROJECTIONS))
        self.assertEqual(len(audit_chain.SEAL_ORDER),
                         len(set(audit_chain.SEAL_ORDER)))

    def test_every_guarded_table_is_chained_except_the_chain_itself(self):
        self.assertEqual(
            set(audit_guards.ALL_TABLES) - set(audit_chain.SEAL_ORDER),
            {'competition_audit_chain'})

    def test_every_audit_model_is_registered_read_only_in_the_admin(self):
        from django.apps import apps
        from django.contrib import admin as django_admin
        by_table = {model._meta.db_table: model for model in apps.get_models()}
        for table in audit_guards.ALL_TABLES:
            with self.subTest(table=table):
                self.assertIn(table, by_table)
                options = django_admin.site._registry.get(by_table[table])
                self.assertIsNotNone(options, f'{table} is not in the admin')
                self.assertFalse(options.has_add_permission(None))
                self.assertFalse(options.has_change_permission(None))
                self.assertFalse(options.has_delete_permission(None))


class ProvisionedRolePrivilegeTests(TestCase):
    """The SQL `install_audit_guards --role-sql` prints, run for real.

    Inside the test transaction, so the role and its grants are rolled back.
    The role name carries the process id because roles are cluster-wide and
    parallel test workers share one cluster.
    """

    def test_the_application_role_may_insert_and_select_and_nothing_else(self):
        role = f'gsp_app_probe_{os.getpid()}'
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_user')
            owner = cursor.fetchone()[0]
            for statement in audit_guards.provision_app_role_sql(role, owner):
                if statement.lstrip().startswith('--'):
                    continue
                cursor.execute(statement)

            def may(privilege, table=TABLE):
                cursor.execute('SELECT has_table_privilege(%s, %s, %s)',
                               [role, table, privilege])
                return cursor.fetchone()[0]

            self.assertTrue(may('INSERT'))
            self.assertTrue(may('SELECT'))
            for privilege in ('UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES',
                              'TRIGGER'):
                self.assertFalse(may(privilege), privilege)
            # The control: an ordinary table keeps its DML, so the denials
            # above are this table's revocation and not a role with nothing.
            self.assertTrue(may('DELETE', 'game'))
            # The sequence the INSERT needs.
            cursor.execute(
                "SELECT has_sequence_privilege(%s, "
                "pg_get_serial_sequence(%s, 'id'), 'USAGE')", [role, TABLE])
            self.assertTrue(cursor.fetchone()[0])
