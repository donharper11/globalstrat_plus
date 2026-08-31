"""The refusal ledger has a supported reader.

V2-034 made cross-cohort mutation attempts captured, sealed and unreadable:
nothing in the product returned one, so investigating "did another instructor
try to act on our competition?" needed a database client. V2-030 already
settled that an audit row the operator cannot retrieve through supported
tooling does not answer the incident it exists for.

These tests prove the command finds a known refusal by the identifiers an
operator actually holds — the game and the request id from a 403 — that
unrelated refusals are excluded, and that nothing sensitive is printed.
"""
import json
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from core.models import AuthorizationRefusalEvent
from core.models.audit_integrity import AuditChainEntry


class WhoAttemptedTests(TestCase):

    def setUp(self):
        self.target = AuthorizationRefusalEvent.objects.create(
            actor_user_id=41, username='outsider', game_id_attempted=7,
            method='POST', route='api/games/<int:game_id>/round-control/close/',
            endpoint='/api/games/7/round-control/close/', outcome='rejected',
            reason='Game belongs to another instructor',
            request_id='srv-target-0001')
        self.unrelated = AuthorizationRefusalEvent.objects.create(
            actor_user_id=99, username='someone-else', game_id_attempted=8,
            method='PATCH', route='api/games/<int:game_id>/instructor/team-config/',
            endpoint='/api/games/8/instructor/team-config/', outcome='rejected',
            reason='Game belongs to another instructor',
            request_id='srv-unrelated-9999')

    def run_command(self, **options):
        out = StringIO()
        call_command('who_attempted', stdout=out, **options)
        return out.getvalue()

    def json_command(self, **options):
        return json.loads(self.run_command(json=True, **options))

    # -- finding the row an operator is holding a 403 for ------------------

    def test_a_refusal_is_found_by_game(self):
        output = self.run_command(game=7)
        self.assertIn('srv-target-0001', output)
        self.assertNotIn('srv-unrelated-9999', output)

    def test_a_refusal_is_found_by_request_id(self):
        payload = self.json_command(request_id='srv-target-0001')
        self.assertEqual(payload['shown'], 1)
        self.assertEqual(payload['refusals'][0]['request_id'], 'srv-target-0001')

    def test_every_field_the_incident_needs_is_present(self):
        row = self.json_command(request_id='srv-target-0001')['refusals'][0]
        self.assertEqual(row['username'], 'outsider')
        self.assertEqual(row['actor_user_id'], 41)
        self.assertEqual(row['game'], 7)
        self.assertEqual(row['method'], 'POST')
        self.assertIn('round-control/close', row['endpoint'])
        self.assertTrue(row['route'])
        self.assertEqual(row['outcome'], 'rejected')
        self.assertIn('another instructor', row['reason'])
        self.assertTrue(row['at'])

    def test_text_and_json_describe_the_same_row(self):
        text = self.run_command(request_id='srv-target-0001')
        row = self.json_command(request_id='srv-target-0001')['refusals'][0]
        for value in (row['request_id'], row['username'], row['method'],
                      row['endpoint'], row['reason'], str(row['game'])):
            self.assertIn(str(value), text)

    # -- the filters exclude what they should ------------------------------

    def test_a_nonmatching_game_excludes_the_row(self):
        self.assertEqual(self.json_command(game=1234)['shown'], 0)
        self.assertIn('No refused attempts',
                      self.run_command(game=1234))

    def test_nonmatching_actor_request_id_method_and_route_exclude_the_row(self):
        self.assertEqual(self.json_command(user=12345)['shown'], 0)
        self.assertEqual(self.json_command(username='nobody')['shown'], 0)
        self.assertEqual(self.json_command(request_id='srv-nothing')['shown'], 0)
        self.assertEqual(self.json_command(game=7, method='DELETE')['shown'], 0)
        self.assertEqual(
            self.json_command(game=7, route_contains='team-config')['shown'], 0)

    def test_a_time_range_excludes_the_row(self):
        later = (timezone.now() + timezone.timedelta(days=1)).isoformat()
        earlier = (timezone.now() - timezone.timedelta(days=1)).isoformat()
        self.assertEqual(self.json_command(since=later)['shown'], 0)
        self.assertEqual(self.json_command(until=earlier)['shown'], 0)
        self.assertEqual(self.json_command(since=earlier, until=later)['shown'], 2)

    def test_an_unparseable_timestamp_is_refused_clearly(self):
        with self.assertRaises(CommandError) as caught:
            self.run_command(since='last tuesday')
        self.assertIn('ISO 8601', str(caught.exception))

    # -- what it must never print ------------------------------------------

    def test_no_payload_token_or_credential_appears(self):
        text = self.run_command(game=7)
        payload = self.run_command(game=7, json=True)
        for forbidden in ('password', 'token', 'Bearer', 'authorization',
                          'payload', 'secret'):
            self.assertNotIn(forbidden.lower(), text.lower())
            self.assertNotIn(forbidden.lower(), payload.lower())

    # -- read-only ---------------------------------------------------------

    def test_the_command_changes_nothing(self):
        before = {
            'rows': list(AuthorizationRefusalEvent.objects.values_list(
                'id', 'reason', 'request_id').order_by('id')),
            'chain': AuditChainEntry.objects.count(),
        }
        self.run_command(game=7)
        self.run_command(json=True)
        after = {
            'rows': list(AuthorizationRefusalEvent.objects.values_list(
                'id', 'reason', 'request_id').order_by('id')),
            'chain': AuditChainEntry.objects.count(),
        }
        self.assertEqual(before, after)
