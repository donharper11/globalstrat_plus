"""W-CE-24's remainder: "Advance Round" still could not advance a round.

The Game Lifecycle card's Advance Round now asks for a written reason when
teams are pending -- that half was repaired on 2026-09-22 -- but with the
reason typed the route answered 400 `round_not_ready`:

    Team "Aurora Devices" has not locked decisions for round 3. Re-lock the
    team (or close the round) before processing.

while the modal above it promised the pending teams would be carried in. The
round had to be resolved from the Round Control card instead, so the one
control on the card that says "advance" could not advance a round with
pending teams at all.

`force` on this route only skipped the *view's* all-teams-locked
precondition; `_run_phase_1` checks the same thing again, for the reason its
comment gives -- the engine entry point must not silently create or lock
submissions. So the override reached the engine and the engine refused it.

The repair does the step the engine's own sentence names, and that the
operator expects from a one-step advance: with `force` and a reason on an
open round, `close_round` runs first. That is the deadline path -- it locks
each team's draft as it stands and records a `deadline_lock` audit event per
team -- and is exactly what `RoundProcessView` already does with `force`. No
guard is weakened: the engine's precondition is satisfied by closing the
round, not bypassed, and the override still costs a written reason on the
audit record.
"""
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.engine.utils import _config_cache
from core.models import (DecisionAuditEvent, DecisionSubmission,
                         OperatorAuditEvent, Round, User)
from core.models.course import Course, Section
from core.models.decisions import DecisionBudgetAllocation
from core.tests.test_operator_concurrency import build_minimal_game

REASON = 'Heat A is over time; resolving with what the teams have entered.'


class LegacyAdvanceWithPendingTeamsTests(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, self.teams = build_minimal_game(f'la-{id(self)}')
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        # One team locked, one still out: the walkthrough's state.
        self.locked_team, self.pending_team = self.teams
        for team, status in ((self.locked_team, 'locked'),
                             (self.pending_team, 'draft')):
            submission = DecisionSubmission.objects.create(
                team=team, round=self.round, status=status,
                locked_at=timezone.now() if status == 'locked' else None)
            DecisionBudgetAllocation.objects.create(
                submission=submission, rd_budget=D('0'),
                marketing_budget=D('0'), strategy_budget=D('0'),
                research_budget=D('0'))

        self.instructor = User.objects.create(
            username=f'la-{id(self)}', role='instructor', password_hash='x')
        course = Course.objects.create(
            course_code=f'LA{id(self) % 100000}', course_name='Legacy',
            instructor_id=self.instructor.user_id, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S1', section_name='S1',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        self.game.section_id = section.section_id
        self.game.save(update_fields=['section_id'])
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.instructor)}')

    def advance(self, **body):
        return self.client.post(
            f'/api/games/{self.game.id}/instructor/advance-round/',
            body, format='json')

    # -- the defect --------------------------------------------------------

    def test_with_a_reason_the_round_is_resolved_and_the_game_moves_on(self):
        response = self.advance(force=True, reason=REASON)

        self.assertEqual(response.status_code, 200, response.data)
        self.round.refresh_from_db()
        self.game.refresh_from_db()
        self.assertEqual(self.round.status, 'processed')
        self.assertEqual(self.game.current_round, 2)

    def test_the_pending_team_is_locked_with_what_it_had_and_it_is_recorded(self):
        self.advance(force=True, reason=REASON)

        submission = DecisionSubmission.objects.get(
            team=self.pending_team, round=self.round)
        self.assertEqual(submission.status, 'locked')
        self.assertTrue(DecisionAuditEvent.objects.filter(
            team=self.pending_team, round=self.round,
            action='deadline_lock').exists())

    def test_the_override_is_on_the_operator_audit_record_with_its_reason(self):
        self.advance(force=True, reason=REASON)

        event = OperatorAuditEvent.objects.filter(
            game=self.game, action='advance_round_legacy').order_by('id').last()
        self.assertIsNotNone(event)
        self.assertIn('over time', event.reason)

    # -- the guards that must not move -------------------------------------

    def test_without_a_reason_the_override_is_still_refused(self):
        response = self.advance(force=True)

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data.get('code'), 'reason_required')
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'open')

    def test_without_force_a_pending_team_still_stops_it(self):
        response = self.advance()

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data.get('code'), 'team_not_locked')
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'open')

    def test_an_already_processed_round_is_still_refused(self):
        Round.objects.filter(pk=self.round.pk).update(status='processed')

        response = self.advance(force=True, reason=REASON)

        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data.get('code'),
                         'round_already_processed')

    def test_with_every_team_locked_nothing_about_the_plain_path_changes(self):
        DecisionSubmission.objects.filter(round=self.round).update(
            status='locked', locked_at=timezone.now())

        response = self.advance()

        self.assertEqual(response.status_code, 200, response.data)
        self.game.refresh_from_db()
        self.assertEqual(self.game.current_round, 2)
