"""Operator events must be readable by the instructor who owns the game.

CRV2-08 found the runbook instructing an operator to "review operator events in
timestamp order" to answer a dispute, while no product API or UI returned any.
The rows had always been written -- every lifecycle action and every refusal --
and nothing read them, so the only way to see one was the Django admin: a
separate maintenance login competition instructors do not have.

These tests cover what the dispute needs (actor, timestamp, action, before and
after, reason, request id, and refusals) and the isolation that keeps one
instructor out of another cohort's operator trail.
"""
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import OperatorAuditEvent, Round, User
from core.models.course import Course, Section
from core.tests.test_operator_concurrency import build_minimal_game


class OperatorEventsViewTests(TestCase):

    def setUp(self):
        self.game, self.teams = build_minimal_game(f'opevents-{id(self)}')
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='processed')
        self.owner = User.objects.create(
            username=f'owner-{id(self)}', role='instructor', password_hash='x')
        self.stranger = User.objects.create(
            username=f'stranger-{id(self)}', role='instructor', password_hash='x')
        self.student = User.objects.create(
            username=f'student-{id(self)}', role='student', password_hash='x')

        self.committed = OperatorAuditEvent.objects.create(
            game=self.game, round=self.round, user=self.owner,
            action='close_round', outcome='committed',
            reason='Closing at the published deadline',
            before={'status': 'open'}, after={'status': 'closed'},
            request_id='srv-committed-1')
        self.refused = OperatorAuditEvent.objects.create(
            game=self.game, round=self.round, user=self.stranger,
            action='close_round', outcome='rejected',
            reason='Second operator, same round',
            before={'status': 'closed'}, after={},
            conflict={'code': 'round_already_closed'},
            request_id='srv-rejected-1')

    def _client(self, user):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    def _url(self, game=None, query=''):
        return (f'/api/games/{(game or self.game).id}/instructor/'
                f'operator-events/{query}')

    # -- what the dispute needs -------------------------------------------

    def test_returns_every_field_the_dispute_procedure_names(self):
        response = self._client(self.owner).get(self._url())
        self.assertEqual(response.status_code, 200)
        events = {e['request_id']: e for e in response.data['events']}
        committed = events['srv-committed-1']
        for field in ('server_timestamp', 'actor', 'action', 'outcome',
                      'before', 'after', 'reason', 'request_id'):
            self.assertIn(field, committed)
        self.assertEqual(committed['actor'], self.owner.username)
        self.assertEqual(committed['action'], 'close_round')
        self.assertEqual(committed['before'], {'status': 'open'})
        self.assertEqual(committed['after'], {'status': 'closed'})
        self.assertEqual(committed['reason'], 'Closing at the published deadline')

    def test_a_refusal_is_returned_with_its_conflict(self):
        # A race shows as one committed row and one rejected row carrying an
        # empty `after`. An endpoint that returned only successes would hide
        # exactly the half an operator is asked to look for.
        response = self._client(self.owner).get(self._url())
        refused = next(e for e in response.data['events']
                       if e['request_id'] == 'srv-rejected-1')
        self.assertEqual(refused['outcome'], 'rejected')
        self.assertEqual(refused['after'], {})
        self.assertEqual(refused['conflict'], {'code': 'round_already_closed'})

    def test_events_are_ordered_newest_first(self):
        response = self._client(self.owner).get(self._url())
        stamps = [e['server_timestamp'] for e in response.data['events']]
        self.assertEqual(stamps, sorted(stamps, reverse=True))

    def test_filters_by_round_action_and_outcome(self):
        client = self._client(self.owner)
        self.assertEqual(
            len(client.get(self._url(query='?outcome=rejected')).data['events']), 1)
        self.assertEqual(
            len(client.get(self._url(query='?action=close_round')).data['events']), 2)
        self.assertEqual(
            len(client.get(self._url(query='?round=1')).data['events']), 2)
        self.assertEqual(
            len(client.get(self._url(query='?round=99')).data['events']), 0)

    # -- isolation ---------------------------------------------------------

    def test_an_instructor_from_another_course_is_refused(self):
        course = Course.objects.create(
            course_code=f'OTHER{id(self) % 10000}', course_name='Other',
            instructor_id=self.stranger.user_id, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S1', section_name='S1',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        mine = Course.objects.create(
            course_code=f'MINE{id(self) % 10000}', course_name='Mine',
            instructor_id=self.owner.user_id, is_active=True)
        my_section = Section.objects.create(
            course_id=mine.course_id, section_code='S2', section_name='S2',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        self.game.section_id = my_section.section_id
        self.game.save(update_fields=['section_id'])

        response = self._client(self.stranger).get(self._url())
        self.assertEqual(response.status_code, 403)
        # The refusal now comes from GameScopeGuardMiddleware, before the view
        # runs, so it is a plain JsonResponse with no DRF `.data`. What matters
        # is unchanged: no event body is disclosed.
        body = response.content.decode()
        self.assertNotIn('"events"', body)
        self.assertNotIn('srv-committed-1', body)
        self.assertTrue(section.section_id)

    def test_a_student_is_refused(self):
        response = self._client(self.student).get(self._url())
        self.assertIn(response.status_code, (401, 403))
        self.assertNotIn('srv-committed-1', response.content.decode())

    def test_the_view_is_read_only(self):
        client = self._client(self.owner)
        for method in (client.post, client.put, client.patch, client.delete):
            self.assertEqual(method(self._url()).status_code, 405)
        self.assertEqual(OperatorAuditEvent.objects.count(), 2)
