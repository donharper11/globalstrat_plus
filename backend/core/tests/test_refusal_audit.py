"""A refused cross-cohort attempt must leave a record.

CRV2-02 established that operator refusals are auditable: a race leaves one
committed row and one rejected row, and the rejected row is what shows the
attempt was made. V2-032 moved authorization to a middleware boundary that
refuses before the view runs — correct, and it meant thirty-seven refused
lifecycle attempts reached no auditing code at all (V2-034). An instructor
trying to act on another cohort's competition left nothing to investigate.

These tests pin what the record contains, what it must never contain, and that
nothing is written when nothing was refused.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import (AuthorizationRefusalEvent, OperatorAuditEvent, Round,
                         User)
from core.models.audit_integrity import SensitiveReadEvent
from core.models.course import Course, Section
from core.tests.test_operator_concurrency import build_minimal_game


class RefusalAuditTests(TestCase):

    def setUp(self):
        self.game, _ = build_minimal_game(f'refusal-{id(self)}')
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open')
        self.owner = User.objects.create(
            username=f'owner-{id(self)}', role='instructor', password_hash='x')
        self.outsider = User.objects.create(
            username=f'outsider-{id(self)}', role='instructor', password_hash='x')
        course = Course.objects.create(
            course_code=f'OWN{id(self) % 100000}', course_name='Owned',
            instructor_id=self.owner.user_id, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S1', section_name='S1',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        self.game.section_id = section.section_id
        self.game.save(update_fields=['section_id'])

    def _client(self, user):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    # -- the record ---------------------------------------------------------

    def test_a_refused_mutation_is_recorded_exactly_once(self):
        response = self._client(self.outsider).post(
            f'/api/games/{self.game.id}/round-control/close/',
            {'reason': 'not my cohort'}, format='json')
        self.assertEqual(response.status_code, 403)

        rows = list(AuthorizationRefusalEvent.objects.all())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.actor_user_id, self.outsider.user_id)
        self.assertEqual(row.username, self.outsider.username)
        self.assertEqual(row.game_id_attempted, self.game.id)
        self.assertEqual(row.method, 'POST')
        self.assertEqual(row.outcome, 'rejected')
        self.assertIn('another instructor', row.reason)
        self.assertIn('round-control/close', row.endpoint)
        self.assertTrue(row.route)
        self.assertIsNotNone(row.created_at)

    def test_the_response_and_the_record_share_one_request_id(self):
        response = self._client(self.outsider).post(
            f'/api/games/{self.game.id}/round-control/close/',
            {'reason': 'not my cohort'}, format='json')
        import json
        row = AuthorizationRefusalEvent.objects.get()
        self.assertTrue(row.request_id)
        # The boundary refuses before the view, so this is a plain
        # JsonResponse rather than a DRF response.
        body = json.loads(response.content.decode())
        self.assertEqual(body.get('request_id'), row.request_id)

    def test_the_refused_attempt_changes_no_state(self):
        self._client(self.outsider).post(
            f'/api/games/{self.game.id}/round-control/close/',
            {'reason': 'not my cohort'}, format='json')
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'open')
        self.assertEqual(OperatorAuditEvent.objects.count(), 0)

    def test_no_payload_or_credential_is_stored(self):
        secret = 'super-secret-reason-text'
        self._client(self.outsider).post(
            f'/api/games/{self.game.id}/round-control/deadline/',
            {'reason': secret, 'password': 'hunter2', 'minutes_from_now': 5},
            format='json')
        row = AuthorizationRefusalEvent.objects.get()
        stored = ' '.join(str(v) for v in row.__dict__.values())
        self.assertNotIn(secret, stored)
        self.assertNotIn('hunter2', stored)
        self.assertNotIn('Bearer', stored)
        # The row's own fields are the whole record; there is nowhere else a
        # body could hide.
        self.assertEqual(
            sorted(f.name for f in AuthorizationRefusalEvent._meta.fields),
            ['actor_user_id', 'created_at', 'endpoint', 'game_id_attempted',
             'id', 'method', 'outcome', 'reason', 'request_id', 'route',
             'username'])

    def test_a_patch_is_recorded_too(self):
        self._client(self.outsider).patch(
            f'/api/games/{self.game.id}/instructor/team-config/',
            {'name': 'x'}, format='json')
        self.assertEqual(
            AuthorizationRefusalEvent.objects.filter(
                method='PATCH').count(), 1)

    # -- reads follow the read policy, not this one ------------------------

    def test_a_refused_read_is_not_recorded_as_a_mutation_refusal(self):
        response = self._client(self.outsider).get(
            f'/api/games/{self.game.id}/instructor/teams/1/decisions/?round=1')
        self.assertEqual(response.status_code, 403)
        # The read ledger owns this event; a second row here would double-count
        # the same disclosure attempt.
        self.assertEqual(AuthorizationRefusalEvent.objects.count(), 0)
        self.assertTrue(
            SensitiveReadEvent.objects.filter(outcome='denied').exists())
        self.assertEqual(OperatorAuditEvent.objects.count(), 0)

    # -- nothing is written when nothing was refused -----------------------

    def test_the_owner_is_not_audited_by_the_boundary(self):
        response = self._client(self.owner).post(
            f'/api/games/{self.game.id}/round-control/close/',
            {'reason': 'closing my own round'}, format='json')
        self.assertNotEqual(response.status_code, 403)
        self.assertEqual(AuthorizationRefusalEvent.objects.count(), 0)

    def test_the_record_is_append_only(self):
        self._client(self.outsider).post(
            f'/api/games/{self.game.id}/round-control/close/',
            {'reason': 'not my cohort'}, format='json')
        row = AuthorizationRefusalEvent.objects.get()
        row.reason = 'rewritten'
        with self.assertRaises(ValueError):
            row.save()
