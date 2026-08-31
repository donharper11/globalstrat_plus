"""The refusal table is protected and chained, not merely listed as such.

The V2-034 repair claimed the refusal rows were trigger-protected and
tamper-evident. Neither was true on a deployed upgrade. Adding the table to
`audit_guards.PROTECTED_TABLES` changes what `install_audit_guards` and the
test runner install; it does nothing to a competition database that has already
been migrated. And listing the table in `audit_chain.SEAL_ORDER` only makes its
rows *eligible* for a pass something else triggers, so a final refusal could sit
unsealed indefinitely.

The focused audit tests could not have caught either: the custom test runner
installs the current guard list after building its database, which is exactly
the masking that let the claim stand.
"""
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase

from core.models import AuthorizationRefusalEvent
from core.models.audit_integrity import AuditChainEntry
from core.services import audit_chain, audit_guards


class RefusalTableGuardTests(TestCase):

    def setUp(self):
        self.row = AuthorizationRefusalEvent.objects.create(
            actor_user_id=1, username='outsider', game_id_attempted=7,
            method='POST', route='api/games/<int:game_id>/round-control/close/',
            endpoint='/api/games/7/round-control/close/', outcome='rejected',
            reason='Game belongs to another instructor', request_id='srv-guard-1')

    def test_the_table_is_registered_for_protection(self):
        self.assertIn('competition_authorization_refusal_event',
                      audit_guards.PROTECTED_TABLES)

    def test_the_migration_installs_this_table_s_guards(self):
        # The statements the migration runs, rather than the list it reads.
        statements = ' '.join(audit_guards.install_table_sql(
            'competition_authorization_refusal_event'))
        self.assertIn('BEFORE UPDATE OR DELETE ON '
                      'competition_authorization_refusal_event', statements)
        self.assertIn('BEFORE TRUNCATE ON '
                      'competition_authorization_refusal_event', statements)

    def test_reversing_the_guard_migration_touches_only_this_table(self):
        statements = audit_guards.uninstall_table_sql(
            'competition_authorization_refusal_event')
        joined = ' '.join(statements)
        self.assertEqual(len(statements), 2)
        for other in ('competition_decision_audit_event',
                      'competition_operator_audit_event',
                      'competition_sensitive_read_event',
                      'competition_audit_chain',
                      'competition_resolution_manifest'):
            self.assertNotIn(other, joined)
        # And it must not drop the shared functions every other table uses.
        self.assertNotIn('DROP FUNCTION', joined)

    def test_a_direct_sql_update_is_refused(self):
        with self.assertRaises(Exception) as caught:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE competition_authorization_refusal_event '
                    'SET reason = %s WHERE id = %s', ['rewritten', self.row.id])
        self.assertIn('append-only', str(caught.exception).lower())

    def test_a_direct_sql_delete_is_refused(self):
        with self.assertRaises(Exception) as caught:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(
                    'DELETE FROM competition_authorization_refusal_event '
                    'WHERE id = %s', [self.row.id])
        self.assertIn('append-only', str(caught.exception).lower())

    def test_an_orm_queryset_update_is_refused(self):
        with self.assertRaises(Exception):
            with transaction.atomic():
                AuthorizationRefusalEvent.objects.filter(
                    pk=self.row.pk).update(reason='rewritten')
        self.row.refresh_from_db()
        self.assertEqual(self.row.reason,
                         'Game belongs to another instructor')

    def test_truncate_is_refused_under_the_non_test_policy(self):
        """The test database announces itself so Django can reset between
        tests, so proving the guard means withdrawing that announcement for one
        transaction -- the same way the established audit tests do it."""
        table = 'competition_authorization_refusal_event'
        with self.assertRaises(Exception) as caught:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(
                    f"SET LOCAL {audit_guards.TRUNCATE_SETTING} = 'off'")
                cursor.execute(f'TRUNCATE {table} CASCADE')
        self.assertIn('TRUNCATE is not permitted', str(caught.exception))

    def test_the_truncate_policy_refuses_a_production_database_name(self):
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT {audit_guards.POLICY_FUNCTION}(%s)',
                ['globalstrat_plus'])
            self.assertFalse(cursor.fetchone()[0])


class RefusalSealingTests(TransactionTestCase):
    """Sealing happens on commit, so these need real transactions."""

    reset_sequences = False

    def _make(self, request_id):
        return AuthorizationRefusalEvent.objects.create(
            actor_user_id=2, username='outsider', game_id_attempted=9,
            method='POST', route='api/games/<int:game_id>/round-control/close/',
            endpoint='/api/games/9/round-control/close/', outcome='rejected',
            reason='Game belongs to another instructor', request_id=request_id)

    def test_a_committed_refusal_is_chained(self):
        row = self._make('srv-seal-1')
        entries = AuditChainEntry.objects.filter(
            source_table='competition_authorization_refusal_event',
            source_id=row.id)
        self.assertEqual(entries.count(), 1)

    def test_creating_a_refusal_schedules_exactly_one_seal(self):
        connection_ = transaction.get_connection()
        with transaction.atomic():
            self._make('srv-seal-2')
            self._make('srv-seal-3')
            scheduled = [entry for entry in connection_.run_on_commit
                         if entry[1] is audit_chain._seal_after_commit]
            # One callback for the transaction, not one per row: the seal takes
            # a global advisory lock and a callback per row would take it twice
            # to seal what one pass covers.
            self.assertEqual(len(scheduled), 1)

    def test_the_chain_reports_no_unsealed_refusal(self):
        self._make('srv-seal-4')
        pending = audit_chain._pending(
            'competition_authorization_refusal_event')
        self.assertEqual(list(pending), [],
                         'a refusal was left unsealed after commit')
        self.assertFalse(audit_chain.verify_chain().get('problems'))

    def test_a_rolled_back_refusal_is_not_chained(self):
        before = AuditChainEntry.objects.filter(
            source_table='competition_authorization_refusal_event').count()
        try:
            with transaction.atomic():
                self._make('srv-rollback-1')
                raise IntegrityError('forced rollback')
        except IntegrityError:
            pass
        self.assertFalse(
            AuthorizationRefusalEvent.objects.filter(
                request_id='srv-rollback-1').exists())
        self.assertEqual(
            AuditChainEntry.objects.filter(
                source_table='competition_authorization_refusal_event').count(),
            before)
