"""GSP-CRV2-04 — audit records that resist the code that writes them, and
evidence of who read a team's decisions.

The model layer already refused to re-save an audit row. That guard held for
every write that went through the model layer, which is not the same set as
every write. These tests take the position that a defence nobody has attacked
is a claim, so each one performs the bypass — queryset update, queryset delete,
raw SQL, and a privileged change made with the guards deliberately removed —
and asserts on what the database did about it.

Two things are proven separately and must not be conflated:

* the triggers **reject** a change made by the application, at any layer;
* the chain and its external anchor **detect** a change made by someone who
  could drop the triggers first. Nothing can reject that one, and a report
  claiming otherwise would be describing a different database.
"""
import hashlib
import json
import pathlib
import tempfile

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.db import connection, transaction
from django.db.utils import InternalError, ProgrammingError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import (
    AuditChainEntry, DecisionAuditEvent, Game, OperatorAuditEvent,
    ResolutionManifest, Round, Scenario, SensitiveReadEvent, Team, User,
)
from core.models.scenario import FirmStarterProfile, MarketDefinition
from core.services import audit_anchor, audit_chain, audit_guards

# psycopg raises one of these for a trigger `RAISE EXCEPTION`; which one
# depends on the error class the trigger chose.
REFUSED = (InternalError, ProgrammingError)


class AuditIntegrityBase(TestCase):
    def setUp(self):
        owner = DjangoUser.objects.create(username=f'owner-{id(self)}')
        self.student = User.objects.create(
            username=f'student-{id(self)}', role='student', password_hash='x')
        scenario = Scenario.objects.create(
            name=f'Integrity {id(self)}', industry_label='Test',
            description='d', starting_cash=1000, num_rounds=2)
        market = MarketDefinition.objects.create(
            scenario=scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=scenario, profile_name='Starter', description='d',
            home_market=market, starting_cash=1000, starting_debt=0)
        self.game = Game.objects.create(
            scenario=scenario, name='Integrity game', current_round=1,
            status='active', created_by=owner)
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        self.team = Team.objects.create(
            game=self.game, name='T', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000)

    def make_decision_event(self, action='save', payload=None):
        return DecisionAuditEvent.objects.create(
            game=self.game, team=self.team, round=self.round, user=self.student,
            action=action, endpoint='/api/test/',
            payload=payload if payload is not None else {'budget': 1000})

    def make_operator_event(self, action='close_round'):
        return OperatorAuditEvent.objects.create(
            game=self.game, round=self.round, user=self.student, action=action,
            outcome='committed', reason='test', before={}, after={'status': 'closed'})

    def make_manifest(self, completed=True):
        manifest = ResolutionManifest.objects.create(
            game=self.game, round=self.round, schema_version=2, seed='s',
            input_manifest={'a': 1}, input_sha256='a' * 64,
            decision_event_count=0)
        if completed:
            ResolutionManifest.objects.filter(pk=manifest.pk).update(
                output_sha256='b' * 64, completed_at=timezone.now())
            manifest.refresh_from_db()
        return manifest

    def raw(self, sql, params=None):
        with connection.cursor() as cursor:
            cursor.execute(sql, params or [])


# ---------------------------------------------------------------------------
# The guards themselves
# ---------------------------------------------------------------------------

class AuditGuardInstallationTests(AuditIntegrityBase):

    def test_every_audit_table_carries_an_enabled_guard(self):
        self.assertEqual(audit_guards.missing_guards(connection), [])
        tables = {row['table'] for row in audit_guards.installed_triggers(connection)}
        expected = set(audit_guards.PROTECTED_TABLES) | {audit_guards.MANIFEST_TABLE}
        self.assertEqual(expected - tables, set())

    def test_the_check_command_fails_when_a_guard_is_dropped(self):
        table = 'competition_decision_audit_event'
        self.raw(f'DROP TRIGGER {table}_append_only ON {table}')
        try:
            missing = audit_guards.missing_guards(connection)
            self.assertEqual([row['table'] for row in missing], [table])
            with self.assertRaises(SystemExit):
                call_command('install_audit_guards', '--check')
        finally:
            audit_guards.install(connection)
        self.assertEqual(audit_guards.missing_guards(connection), [])

    def test_truncate_is_refused(self):
        """The bypass the row-level guards did not cover.

        `TRUNCATE` fires no row trigger, so until a statement-level guard was
        added one statement emptied the audit log while every `BEFORE DELETE`
        trigger stayed silent. The test database announces itself so Django can
        still reset between tests, so proving the guard means withdrawing that
        announcement for one transaction.
        """
        # Deliberately not preceded by an insert in this transaction:
        # PostgreSQL refuses TRUNCATE outright while foreign-key trigger events
        # are pending, and an assertion satisfied by that refusal would pass
        # with no guard installed at all.
        with self.assertRaises(REFUSED) as caught:
            with transaction.atomic():
                self.raw(f"SET LOCAL {audit_guards.TRUNCATE_SETTING} = 'off'")
                self.raw('TRUNCATE competition_decision_audit_event CASCADE')
        self.assertIn('TRUNCATE is not permitted', str(caught.exception))

        # And the reset path the test runner depends on still works.
        self.raw('TRUNCATE competition_decision_audit_event CASCADE')

    def test_every_audit_table_refuses_truncate(self):
        for table in audit_guards.ALL_TABLES:
            with self.subTest(table=table):
                with self.assertRaises(REFUSED) as caught:
                    with transaction.atomic():
                        self.raw(
                            f"SET LOCAL {audit_guards.TRUNCATE_SETTING} = 'off'")
                        self.raw(f'TRUNCATE {table} CASCADE')
                self.assertIn('TRUNCATE is not permitted',
                              str(caught.exception))

    def test_the_provisioned_role_is_denied_update_and_delete(self):
        statements = audit_guards.provision_app_role_sql('globalstrat_app')
        joined = '\n'.join(statements)
        for table in audit_guards.PROTECTED_TABLES + (audit_guards.MANIFEST_TABLE,):
            self.assertIn(f'REVOKE UPDATE, DELETE, TRUNCATE ON {table}', joined)
        self.assertIn('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES', joined)


class AuditRejectionTests(AuditIntegrityBase):
    """Each bypass the model layer does not see, attempted for real."""

    def test_the_model_layer_still_refuses_a_re_save(self):
        event = self.make_decision_event()
        event.action = 'tampered'
        with self.assertRaises(ValueError):
            event.save()

    def test_a_queryset_update_is_refused_by_the_database(self):
        event = self.make_decision_event()
        with self.assertRaises(REFUSED):
            with transaction.atomic():
                DecisionAuditEvent.objects.filter(pk=event.pk).update(
                    action='tampered')
        event.refresh_from_db()
        self.assertEqual(event.action, 'save')

    def test_a_queryset_delete_is_refused_by_the_database(self):
        event = self.make_decision_event()
        with self.assertRaises(REFUSED):
            with transaction.atomic():
                DecisionAuditEvent.objects.filter(pk=event.pk).delete()
        self.assertTrue(DecisionAuditEvent.objects.filter(pk=event.pk).exists())

    def test_raw_sql_as_the_application_role_is_refused(self):
        event = self.make_decision_event()
        for statement in (
                'UPDATE competition_decision_audit_event SET action = %s WHERE id = %s',
                'DELETE FROM competition_decision_audit_event WHERE id = %s'):
            params = (['tampered', event.pk] if 'UPDATE' in statement
                      else [event.pk])
            with self.assertRaises(REFUSED):
                with transaction.atomic():
                    self.raw(statement, params)
        event.refresh_from_db()
        self.assertEqual(event.payload, {'budget': 1000})

    def test_operator_audit_rows_are_equally_protected(self):
        event = self.make_operator_event()
        with self.assertRaises(REFUSED):
            with transaction.atomic():
                OperatorAuditEvent.objects.filter(pk=event.pk).update(
                    outcome='rejected')
        with self.assertRaises(REFUSED):
            with transaction.atomic():
                self.raw('DELETE FROM competition_operator_audit_event WHERE id = %s',
                         [event.pk])

    def test_read_evidence_rows_are_equally_protected(self):
        row = SensitiveReadEvent.objects.create(
            actor_user_id=self.student.user_id, username='s',
            game_id_read=self.game.id, team_id_read=self.team.id,
            round_number_read=1, category='decisions', route='r',
            endpoint='/api/x/', method='GET', status_code=200,
            outcome='allowed', request_id='req-1')
        with self.assertRaises(REFUSED):
            with transaction.atomic():
                SensitiveReadEvent.objects.filter(pk=row.pk).update(
                    outcome='denied')
        with self.assertRaises(REFUSED):
            with transaction.atomic():
                SensitiveReadEvent.objects.filter(pk=row.pk).delete()

    def test_the_chain_table_cannot_be_rewritten_either(self):
        self.make_decision_event()
        audit_chain.seal_pending()
        entry = AuditChainEntry.objects.first()
        self.assertIsNotNone(entry)
        with self.assertRaises(REFUSED):
            with transaction.atomic():
                AuditChainEntry.objects.filter(pk=entry.pk).update(
                    entry_sha256='0' * 64)

    def test_an_incomplete_manifest_may_still_be_rewritten(self):
        """The manifest is written twice by design; the guard has to know that."""
        manifest = self.make_manifest(completed=False)
        ResolutionManifest.objects.filter(pk=manifest.pk).update(seed='second')
        manifest.refresh_from_db()
        self.assertEqual(manifest.seed, 'second')

    def test_a_completed_manifest_is_frozen(self):
        manifest = self.make_manifest(completed=True)
        with self.assertRaises(REFUSED):
            with transaction.atomic():
                ResolutionManifest.objects.filter(pk=manifest.pk).update(
                    output_sha256='c' * 64)
        manifest.refresh_from_db()
        self.assertEqual(manifest.output_sha256, 'b' * 64)

    def test_a_manifest_can_never_be_deleted(self):
        manifest = self.make_manifest(completed=False)
        with self.assertRaises(REFUSED):
            with transaction.atomic():
                ResolutionManifest.objects.filter(pk=manifest.pk).delete()


# ---------------------------------------------------------------------------
# Detection, for the change that cannot be rejected
# ---------------------------------------------------------------------------

class AuditChainTests(AuditIntegrityBase):

    def test_the_unchained_columns_are_the_declared_ones(self):
        """Every audit column is either chained or excluded with a reason.

        A column added later joins neither list on its own, so this fails and
        someone decides — which is the point. "The chain covers this table" is
        worth what the list of exclusions is worth.
        """
        for table, (model, fields) in audit_chain.PROJECTIONS.items():
            with self.subTest(table=table):
                actual = {f.attname for f in model._meta.fields}
                self.assertEqual(set(fields) - actual, set(),
                                 'projection names a column that does not exist')
                excluded = actual - set(fields)
                declared = set(audit_chain.UNCHAINED_FIELDS.get(table, {}))
                self.assertEqual(
                    excluded, declared,
                    f'{table}: undeclared exclusions {sorted(excluded - declared)}, '
                    f'stale declarations {sorted(declared - excluded)}')

    def test_an_audit_write_is_chained_when_its_transaction_commits(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.make_decision_event()
        entry = AuditChainEntry.objects.get(
            source_table='competition_decision_audit_event')
        self.assertEqual(entry.seq, 1)
        self.assertEqual(entry.prev_sha256, '0' * 64)
        self.assertTrue(audit_chain.verify_chain()['ok'])

    def test_sealing_is_idempotent(self):
        self.make_decision_event()
        self.make_operator_event()
        first = audit_chain.seal_pending()
        second = audit_chain.seal_pending()
        self.assertEqual(first, 2)
        self.assertEqual(second, 0)
        self.assertEqual(AuditChainEntry.objects.count(), 2)

    def test_the_chain_links_every_entry_to_the_one_before_it(self):
        for index in range(4):
            self.make_decision_event(action=f'save-{index}')
        audit_chain.seal_pending()
        entries = list(AuditChainEntry.objects.order_by('seq'))
        self.assertEqual(len(entries), 4)
        previous = '0' * 64
        for entry in entries:
            self.assertEqual(entry.prev_sha256, previous)
            previous = entry.entry_sha256
        self.assertTrue(audit_chain.verify_chain()['ok'])

    def test_a_privileged_edit_made_with_the_guards_removed_is_detected(self):
        """The change the triggers cannot stop, and the reason the chain exists.

        The trigger is dropped exactly as a database owner would drop it, the
        row is rewritten, and the trigger is put back — so the tables afterwards
        look untouched. Verification is the only thing that disagrees.
        """
        event = self.make_decision_event(payload={'budget': 1000})
        audit_chain.seal_pending()
        self.assertTrue(audit_chain.verify_chain()['ok'])

        table = 'competition_decision_audit_event'
        self.raw(f'DROP TRIGGER {table}_append_only ON {table}')
        try:
            self.raw(f'UPDATE {table} SET payload = %s WHERE id = %s',
                     [json.dumps({'budget': 999999}), event.pk])
        finally:
            audit_guards.install(connection)

        event.refresh_from_db()
        self.assertEqual(event.payload, {'budget': 999999})

        report = audit_chain.verify_chain()
        self.assertFalse(report['ok'])
        self.assertEqual([p['kind'] for p in report['problems']],
                         ['row_modified'])

    def test_deleting_a_sealed_row_is_detected(self):
        event = self.make_decision_event()
        audit_chain.seal_pending()
        table = 'competition_decision_audit_event'
        self.raw(f'DROP TRIGGER {table}_append_only ON {table}')
        try:
            self.raw(f'DELETE FROM {table} WHERE id = %s', [event.pk])
        finally:
            audit_guards.install(connection)
        report = audit_chain.verify_chain()
        self.assertFalse(report['ok'])
        self.assertIn('row_deleted', [p['kind'] for p in report['problems']])

    def test_a_forged_chain_entry_does_not_recompute(self):
        self.make_decision_event()
        audit_chain.seal_pending()
        entry = AuditChainEntry.objects.get(seq=1)
        self.raw('DROP TRIGGER competition_audit_chain_append_only '
                 'ON competition_audit_chain')
        try:
            self.raw('UPDATE competition_audit_chain SET row_sha256 = %s '
                     'WHERE id = %s', ['f' * 64, entry.pk])
        finally:
            audit_guards.install(connection)
        report = audit_chain.verify_chain()
        self.assertFalse(report['ok'])
        kinds = {p['kind'] for p in report['problems']}
        self.assertTrue({'row_modified', 'entry_forged'} & kinds)

    def test_verification_reports_rows_that_are_not_sealed_yet(self):
        self.make_decision_event()
        report = audit_chain.verify_chain()
        self.assertTrue(report['ok'])
        self.assertEqual(report['unsealed_total'], 1)
        audit_chain.seal_pending()
        self.assertEqual(audit_chain.verify_chain()['unsealed_total'], 0)

    def test_a_completed_manifest_is_chained_and_an_incomplete_one_is_not(self):
        self.make_manifest(completed=False)
        audit_chain.seal_pending()
        self.assertFalse(AuditChainEntry.objects.filter(
            source_table='competition_resolution_manifest').exists())
        ResolutionManifest.objects.filter(round=self.round).update(
            completed_at=timezone.now())
        audit_chain.seal_pending()
        self.assertTrue(AuditChainEntry.objects.filter(
            source_table='competition_resolution_manifest').exists())
        self.assertTrue(audit_chain.verify_chain()['ok'])


class RecoveryAuditChainTests(AuditIntegrityBase):
    """The recovery audit lives in a file, and the chain has to cover it too."""

    def test_the_recovery_audit_file_is_chained_and_its_edits_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(COMPETITION_BACKUP_DIR=directory):
                path = pathlib.Path(directory) / 'recovery-audit.jsonl'
                path.write_text('{"action": "restore"}\n', encoding='utf-8')
                audit_chain.seal_pending()
                entry = AuditChainEntry.objects.get(
                    source_table=audit_chain.RECOVERY_AUDIT_TABLE)
                self.assertEqual(
                    entry.row_sha256,
                    hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertTrue(audit_chain.verify_chain()['ok'])

                # An append is legitimate history and produces a new entry.
                with path.open('a', encoding='utf-8') as stream:
                    stream.write('{"action": "prune"}\n')
                self.assertEqual(audit_chain.seal_pending(), 1)

                # Rewriting what was already chained does not.
                path.write_text('{"action": "nothing happened"}\n',
                                encoding='utf-8')
                self.assertEqual(audit_chain.seal_pending(), 1)
                sealed = list(AuditChainEntry.objects.filter(
                    source_table=audit_chain.RECOVERY_AUDIT_TABLE))
                self.assertEqual(len(sealed), 3)


class AuditAnchorTests(AuditIntegrityBase):

    def test_an_exported_anchor_verifies_against_the_live_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(COMPETITION_BACKUP_DIR=directory):
                self.make_decision_event()
                audit_chain.seal_pending()
                record = audit_anchor.export_anchor()
                self.assertTrue(pathlib.Path(record['path']).is_file())
                report = audit_anchor.verify_against_anchor()
                self.assertTrue(report['ok'], report)
                self.assertEqual(report['recomputed_head_sha256'],
                                 record['head_entry_sha256'])

    def test_a_privileged_edit_breaks_the_external_check(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(COMPETITION_BACKUP_DIR=directory):
                event = self.make_decision_event()
                audit_chain.seal_pending()
                audit_anchor.export_anchor()

                table = 'competition_decision_audit_event'
                self.raw(f'DROP TRIGGER {table}_append_only ON {table}')
                try:
                    self.raw(f'UPDATE {table} SET action = %s WHERE id = %s',
                             ['tampered', event.pk])
                finally:
                    audit_guards.install(connection)

                report = audit_anchor.verify_against_anchor()
                self.assertFalse(report['ok'])
                self.assertNotEqual(report['recomputed_head_sha256'],
                                    report['anchored_head_sha256'])

    def test_an_edited_anchor_file_is_rejected_by_its_own_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(COMPETITION_BACKUP_DIR=directory):
                self.make_decision_event()
                audit_chain.seal_pending()
                audit_anchor.export_anchor()
                latest = audit_anchor.anchor_root() / 'latest.json'
                body = json.loads(latest.read_text(encoding='utf-8'))
                body['head_entry_sha256'] = 'e' * 64
                latest.write_text(json.dumps(body, indent=2, sort_keys=True) + '\n',
                                  encoding='utf-8')
                with self.assertRaises(ValueError):
                    audit_anchor.load_anchor()

    def test_the_verify_command_exits_non_zero_when_history_is_broken(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(COMPETITION_BACKUP_DIR=directory):
                event = self.make_decision_event()
                audit_chain.seal_pending()
                audit_anchor.export_anchor()
                call_command('verify_audit_chain')

                table = 'competition_decision_audit_event'
                self.raw(f'DROP TRIGGER {table}_append_only ON {table}')
                try:
                    self.raw(f'UPDATE {table} SET action = %s WHERE id = %s',
                             ['tampered', event.pk])
                finally:
                    audit_guards.install(connection)
                with self.assertRaises(SystemExit):
                    call_command('verify_audit_chain')


# ---------------------------------------------------------------------------
# Read evidence
# ---------------------------------------------------------------------------

class SensitiveReadInventoryTests(TestCase):
    """The inventory is the coverage claim; these tests are what make it one."""

    def test_the_checked_in_inventory_matches_the_live_url_conf(self):
        call_command('dump_read_inventory', '--check')

    def test_every_exemption_names_a_registered_view_and_gives_a_reason(self):
        from core.services import read_inventory
        live = {row['view'] for row in read_inventory.sensitive_routes()}
        for view, reason in read_inventory.EXEMPTIONS.items():
            self.assertIn(view, live,
                          f'{view} is exempted but is no longer registered')
            self.assertGreater(len(reason), 40,
                               f'{view} needs a reason someone can review')

    def test_the_middleware_reads_the_generated_file_rather_than_rebuilding(self):
        """Rebuilding the inventory parses the source of every view, which
        measured 6.3 seconds. Doing that lazily would have charged it to the
        first student to open a decision page in each worker process.

        Asserted against the middleware's own lookup, not against the helper it
        is supposed to call: the first version of this fix made
        `logged_routes()` fast and left the middleware calling the slow scan,
        and a test written against the helper passed anyway.
        """
        from unittest.mock import patch
        from core.middleware import SensitiveReadLogMiddleware
        from core.services import read_inventory

        middleware = SensitiveReadLogMiddleware(lambda request: None)
        with patch.object(read_inventory, 'sensitive_routes',
                          side_effect=AssertionError('rebuilt the inventory')):
            category = middleware._sensitive(
                'api/games/<int:game_id>/teams/<int:team_id>'
                '/decisions/round/<int:round_number>/')
        self.assertEqual(category, 'decisions')
        self.assertEqual(len(middleware._routes), 30)

    def test_a_stale_inventory_falls_back_to_the_live_scan(self):
        """A generated file that no longer describes the URL conf must not be
        believed: under-logging would be silent, and silence is what this
        table exists to remove."""
        from unittest.mock import patch
        from core.services import read_inventory
        stale = dict(read_inventory.load_inventory())
        stale['url_conf_route_count'] = 1
        with patch.object(read_inventory, 'load_inventory', return_value=stale):
            with self.assertLogs('core.services.read_inventory', 'WARNING') as logs:
                routes = read_inventory.logged_route_categories()
        self.assertIn('stale', logs.output[0])
        self.assertEqual(routes, {row['route']: row['category']
                                  for row in read_inventory.sensitive_routes()
                                  if row['logged']})

    def test_the_inventory_route_format_is_what_a_request_resolves_to(self):
        """A pattern the middleware can never match protects nothing.

        The inventory is built by walking the URL conf and the middleware
        matches on `resolver_match.route`. If those two spellings ever diverge,
        every route silently stops being logged and every test that asserts on
        the *inventory* still passes.
        """
        from django.urls import resolve
        from core.services import read_inventory
        logged = read_inventory.logged_routes()
        match = resolve('/api/games/1/teams/2/decisions/round/3/')
        self.assertIn(match.route, logged)
        self.assertEqual(match.kwargs.get('team_id'), 2)
        self.assertEqual(match.kwargs.get('round_number'), 3)


class SensitiveReadLogTests(AuditIntegrityBase):
    """Who read a team's decisions, answered without a web-server log."""

    def setUp(self):
        super().setUp()
        from core.models.course import Course, Section
        self.course = Course.objects.create(
            course_code=f'C{id(self) % 100000}', course_name='Audit course',
            instructor_id=None, is_active=True)
        self.section = Section.objects.create(
            course_id=self.course.course_id, section_code='S1',
            section_name='Section 1', max_teams=4, team_size_min=1,
            team_size_max=4, is_active=True)
        Game.objects.filter(pk=self.game.pk).update(
            section_id=self.section.section_id)
        self.instructor = User.objects.create(
            username=f'inst-{id(self)}', role='instructor', password_hash='x')
        Course.objects.filter(course_id=self.course.course_id).update(
            instructor_id=self.instructor.user_id)
        self.other_team = Team.objects.create(
            game=self.game, name='Rival',
            firm_starter_profile=self.team.firm_starter_profile,
            performance_index=100, cash_on_hand=1000, total_equity=1000)

    def client_for(self, user):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    def test_an_instructor_reading_a_team_leaves_an_attributable_record(self):
        url = (f'/api/games/{self.game.id}/instructor/teams/'
               f'{self.team.id}/decisions/?round=1')
        response = self.client_for(self.instructor).get(url)
        self.assertIn(response.status_code, (200, 404))

        event = SensitiveReadEvent.objects.latest('id')
        self.assertEqual(event.actor_user_id, self.instructor.user_id)
        self.assertEqual(event.username, self.instructor.username)
        self.assertEqual(event.game_id_read, self.game.id)
        self.assertEqual(event.team_id_read, self.team.id)
        self.assertEqual(event.round_number_read, 1)
        self.assertEqual(event.category, 'audit')
        self.assertEqual(event.outcome, 'allowed')
        self.assertEqual(event.method, 'GET')
        self.assertTrue(event.request_id)
        self.assertIsNotNone(event.created_at)

    def test_a_refused_cross_team_read_is_recorded_as_refused(self):
        """The row a disclosure dispute actually needs: the attempt, and that
        it failed. An access log that only records successes cannot tell a
        team that nobody got in — only that nobody is recorded as having."""
        url = (f'/api/games/{self.game.id}/teams/{self.other_team.id}'
               f'/decisions/round/1/')
        response = self.client_for(self.student).get(url)
        self.assertEqual(response.status_code, 403)

        event = SensitiveReadEvent.objects.latest('id')
        self.assertEqual(event.outcome, 'denied')
        self.assertEqual(event.status_code, 403)
        self.assertEqual(event.actor_user_id, self.student.user_id)
        self.assertEqual(event.team_id_read, self.other_team.id)
        self.assertEqual(event.round_number_read, 1)

    def test_the_record_does_not_copy_the_decisions_it_is_protecting(self):
        from core.models import DecisionBudgetAllocation, DecisionSubmission
        submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='submitted')
        DecisionBudgetAllocation.objects.create(
            submission=submission, rd_budget=0, marketing_budget=777777,
            strategy_budget=0, research_budget=0)
        url = (f'/api/games/{self.game.id}/instructor/teams/'
               f'{self.team.id}/decisions/?round=1')
        self.client_for(self.instructor).get(url)

        event = SensitiveReadEvent.objects.latest('id')
        rendered = json.dumps({
            field.name: str(getattr(event, field.name))
            for field in event._meta.fields})
        self.assertNotIn('777777', rendered)
        self.assertNotIn('budget_allocation', rendered)
        self.assertNotIn('Bearer', rendered)
        self.assertNotIn(create_access_token(self.instructor)[:20], rendered)

    def test_an_unauthenticated_read_is_still_recorded(self):
        url = (f'/api/games/{self.game.id}/teams/{self.team.id}'
               f'/decisions/round/1/')
        APIClient().get(url)
        event = SensitiveReadEvent.objects.latest('id')
        self.assertIsNone(event.actor_user_id)
        self.assertEqual(event.username, '')
        self.assertEqual(event.outcome, 'denied')

    def test_a_write_is_not_recorded_as_a_read(self):
        before = SensitiveReadEvent.objects.count()
        url = (f'/api/games/{self.game.id}/teams/{self.team.id}'
               f'/decisions/round/1/')
        self.client_for(self.student).post(url, {}, format='json')
        self.assertEqual(SensitiveReadEvent.objects.count(), before)

    def test_who_accessed_answers_the_question_from_this_table_alone(self):
        instructor_client = self.client_for(self.instructor)
        instructor_client.get(f'/api/games/{self.game.id}/instructor/teams/'
                              f'{self.team.id}/decisions/?round=1')
        self.client_for(self.student).get(
            f'/api/games/{self.game.id}/teams/{self.other_team.id}'
            f'/decisions/round/1/')

        from io import StringIO
        out = StringIO()
        call_command('who_accessed', '--game', str(self.game.id),
                     '--team', str(self.team.id), '--round', '1',
                     '--json', stdout=out)
        report = json.loads(out.getvalue())
        self.assertEqual(report['total'], 1)
        entry = report['reads'][0]
        self.assertEqual(entry['username'], self.instructor.username)
        self.assertEqual(entry['outcome'], 'allowed')
        self.assertEqual(entry['team'], self.team.id)
        self.assertTrue(entry['request_id'])

        out = StringIO()
        call_command('who_accessed', '--game', str(self.game.id),
                     '--team', str(self.other_team.id), '--outcome', 'denied',
                     '--json', stdout=out)
        denied = json.loads(out.getvalue())
        self.assertEqual(denied['total'], 1)
        self.assertEqual(denied['reads'][0]['actor_user_id'],
                         self.student.user_id)

    def test_read_evidence_reaches_the_tamper_evidence_chain(self):
        self.client_for(self.instructor).get(
            f'/api/games/{self.game.id}/instructor/teams/'
            f'{self.team.id}/decisions/?round=1')
        self.assertEqual(SensitiveReadEvent.objects.count(), 1)
        audit_chain.seal_pending()
        self.assertTrue(AuditChainEntry.objects.filter(
            source_table='competition_sensitive_read_event').exists())
        self.assertTrue(audit_chain.verify_chain()['ok'])


class SealSchedulingTests(AuditIntegrityBase):
    """Sealing must not scale with the number of audit rows in a transaction."""

    def test_one_transaction_schedules_one_seal(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            with transaction.atomic():
                for index in range(5):
                    self.make_decision_event(action=f'save-{index}')
                    self.make_operator_event(action=f'act-{index}')
        self.assertEqual(len(callbacks), 1)

    def test_the_single_seal_covers_every_row_written(self):
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                for index in range(5):
                    self.make_decision_event(action=f'save-{index}')
        self.assertEqual(AuditChainEntry.objects.count(), 5)
        self.assertTrue(audit_chain.verify_chain()['ok'])

    def test_a_failed_seal_never_breaks_the_write_it_followed(self):
        """Losing the tamper evidence for a row is recoverable; losing the row
        is not. The next pass picks up whatever the failure left behind."""
        from unittest.mock import patch
        with patch('core.services.audit_chain.seal_pending',
                   side_effect=RuntimeError('database is on fire')):
            with self.captureOnCommitCallbacks(execute=True):
                event = self.make_decision_event()
        self.assertTrue(DecisionAuditEvent.objects.filter(pk=event.pk).exists())
        self.assertEqual(AuditChainEntry.objects.count(), 0)
        audit_chain.seal_pending()
        self.assertEqual(AuditChainEntry.objects.count(), 1)
        self.assertTrue(audit_chain.verify_chain()['ok'])


# ---------------------------------------------------------------------------
# The two remaining surfaces: the admin UI and the registered API
# ---------------------------------------------------------------------------

class AdminTamperingTests(AuditIntegrityBase):
    """`/admin/` is enabled and serves 72 models; the audit tables are 5 of them."""

    def setUp(self):
        super().setUp()
        self.superuser = DjangoUser.objects.create_superuser(
            username=f'root-{id(self)}', email='r@example.com', password='pw')
        self.client.force_login(self.superuser)

    def test_a_superuser_can_read_the_audit_log_in_the_browser(self):
        event = self.make_decision_event()
        response = self.client.get(
            '/admin/core/decisionauditevent/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, event.payload_sha256[:12])

    def test_the_admin_refuses_to_change_an_audit_row(self):
        event = self.make_decision_event()
        response = self.client.post(
            f'/admin/core/decisionauditevent/{event.pk}/change/',
            {'action': 'tampered'})
        self.assertIn(response.status_code, (302, 403))
        event.refresh_from_db()
        self.assertEqual(event.action, 'save')

    def test_the_admin_refuses_to_delete_an_audit_row(self):
        event = self.make_decision_event()
        response = self.client.post(
            f'/admin/core/decisionauditevent/{event.pk}/delete/',
            {'post': 'yes'})
        self.assertIn(response.status_code, (302, 403))
        self.assertTrue(DecisionAuditEvent.objects.filter(pk=event.pk).exists())

    def test_the_admin_offers_no_way_in_for_any_audit_record(self):
        from django.contrib import admin as django_admin
        for model in (DecisionAuditEvent, OperatorAuditEvent,
                      ResolutionManifest, AuditChainEntry, SensitiveReadEvent):
            options = django_admin.site._registry[model]
            self.assertFalse(options.has_add_permission(None), model.__name__)
            self.assertFalse(options.has_change_permission(None), model.__name__)
            self.assertFalse(options.has_delete_permission(None), model.__name__)


class ApiTamperingTests(TestCase):
    """No registered API route writes an audit record, and that is checked.

    Scope, stated because the number is easy to over-read: this walks routes
    whose callback exposes a view class, which is every DRF and class-based
    route and none of Django admin's function-based add/change/delete views.
    The admin is covered by `AdminTamperingTests` instead, and the gap that
    the *lifecycle* route inventory has for the same reason is logged as V2-017.
    """

    def test_no_mutating_route_writes_to_an_audit_table(self):
        import re
        from django.urls import get_resolver
        from core.services.route_inventory import (
            MUTATING_METHODS, _view_source, _walk,
        )
        audit_models = ('DecisionAuditEvent', 'OperatorAuditEvent',
                        'ResolutionManifest', 'AuditChainEntry',
                        'SensitiveReadEvent')
        # A write is `.objects.<writer>(` or an assignment/save on one of them.
        writer = re.compile(
            r'\b(%s)\.objects\.(create|update_or_create|get_or_create|'
            r'bulk_create|bulk_update)\b|'
            r'\b(%s)\.objects[^\n]*?\.(update|delete)\('
            % ('|'.join(audit_models), '|'.join(audit_models)))

        offenders = []
        for route, entry in _walk(get_resolver()):
            callback = entry.callback
            view_class = (getattr(callback, 'cls', None)
                          or getattr(callback, 'view_class', None))
            if view_class is None:
                continue
            actions = getattr(callback, 'actions', None)
            methods = (tuple(actions) if actions
                       else tuple(m for m in MUTATING_METHODS
                                  if callable(getattr(view_class, m, None))))
            if not any(m in MUTATING_METHODS for m in methods):
                continue
            for match in writer.finditer(_view_source(view_class)):
                # Appending a decision or operator audit row is the whole point
                # of those two tables; rewriting one is not, and the pattern
                # above only matches writers.
                if match.group(0).endswith(('.update(', '.delete(')):
                    offenders.append((route, match.group(0)))
        self.assertEqual(offenders, [])

    def test_no_route_serves_the_read_evidence_table(self):
        """Who read what must not itself become something to read."""
        from django.urls import get_resolver
        from core.services.route_inventory import _view_source, _walk
        offenders = []
        for route, entry in _walk(get_resolver()):
            callback = entry.callback
            view_class = (getattr(callback, 'cls', None)
                          or getattr(callback, 'view_class', None))
            if view_class is None:
                continue
            if 'SensitiveReadEvent' in _view_source(view_class):
                offenders.append(route)
        self.assertEqual(offenders, [])
