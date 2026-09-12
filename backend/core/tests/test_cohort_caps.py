"""The authored cohort caps are enforced, and competition games need an owner.

GSP-CRV2-10 Stage 6. Two findings are pinned here:

* **V2-042** — `Section.max_teams`, `team_size_min` and `team_size_max` were
  authored but read by nothing except a serializer field list. The finding
  enrolled eight students through the roster surface and put all eight on one
  team whose maximum is five, and neither surface refused. Game creation
  carried a separate, unrelated `num_teams must be between 2 and 16`.

* **V2-033** — `instructor_can_access_game` treats a course with no
  `instructor_id` as a shared pilot cohort visible to any instructor. That is
  the adopted rule and the live pilot depends on it, so it is preserved; what
  is refused is its reach into a *competition*, where several institutions
  share one deployment.

Every test here fails without the Stage 6 change.
"""
from decimal import Decimal as D

from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import Round, User
from core.models.core import Game, Team
from core.models.course import (
    Course, Enrollment, Section, SimulationInstance,
)
from core.models.scenario import Scenario
from core.services.cohort_caps import (
    game_team_count_error, is_competition_game, team_member_count,
)
from core.tests.test_operator_concurrency import build_minimal_game


class CohortCapTestBase(TestCase):

    def _make_section(self, *, max_teams=8, team_size_min=3, team_size_max=5,
                      instructor_id=None, tag='A'):
        course = Course.objects.create(
            course_code=f'{tag}{id(self) % 100000}', course_name=f'Course {tag}',
            instructor_id=instructor_id, is_active=True)
        return Course.objects.get(pk=course.course_id), Section.objects.create(
            course_id=course.course_id, section_code=f'S-{tag}',
            section_name=f'Section {tag}', max_teams=max_teams,
            team_size_min=team_size_min, team_size_max=team_size_max,
            is_active=True)

    def _instructor(self, name):
        return User.objects.create(
            username=f'{name}-{id(self)}', role='instructor', password_hash='x')

    def _client(self, user, language=None):
        client = APIClient()
        credentials = {
            'HTTP_AUTHORIZATION': f'Bearer {create_access_token(user)}'}
        if language:
            credentials['HTTP_ACCEPT_LANGUAGE'] = language
        client.credentials(**credentials)
        return client


class EnrolmentCapTests(CohortCapTestBase):
    """The section seats max_teams x team_size_max students, and no more."""

    def setUp(self):
        self.instructor = self._instructor('roster-instructor')
        # Capacity of exactly two, so the third enrolment is the refusal.
        self.course, self.section = self._make_section(
            max_teams=1, team_size_min=1, team_size_max=2,
            instructor_id=self.instructor.user_id, tag='CAP')
        self.client_ = self._client(self.instructor)

    def _add(self, student_id, client=None):
        return (client or self.client_).post('/api/roster/', {
            'action': 'add', 'section_id': self.section.section_id,
            'student_id': student_id, 'display_name': student_id,
            'email': f'{student_id}@example.edu',
        }, format='json')

    def test_enrolments_up_to_capacity_are_accepted(self):
        self.assertEqual(self._add('s1').status_code, 201)
        self.assertEqual(self._add('s2').status_code, 201)
        self.assertEqual(Enrollment.objects.filter(
            section_id=self.section.section_id).count(), 2)

    def test_an_enrolment_over_capacity_is_refused(self):
        self._add('s1')
        self._add('s2')
        response = self._add('s3')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('code'), 'section_full')
        # Proves the refusal changed nothing: the third student is not seated.
        self.assertEqual(Enrollment.objects.filter(
            section_id=self.section.section_id).count(), 2)

    def test_the_refusal_names_the_cap_in_business_language(self):
        self._add('s1')
        self._add('s2')
        detail = self._add('s3').data['error']

        self.assertIn('2', detail)                  # the capacity
        # Names the rule and what to do next, and no storage name leaks.
        self.assertIn('Remove a student', detail)
        for storage_name in ('max_teams', 'team_size_max', 'Enrollment',
                             'section_id'):
            self.assertNotIn(storage_name, detail)

    def test_the_refusal_is_localised_for_a_zh_instructor(self):
        self._add('s1')
        self._add('s2')
        zh_client = self._client(self.instructor, language='zh-CN')
        detail = self._add('s3', client=zh_client).data['error']

        self.assertIn('名额已满', detail)
        self.assertNotIn('This section is full', detail)

    def test_re_uploading_an_existing_roster_is_not_refused(self):
        """A capacity check that breaks idempotency would be its own defect."""
        self._add('s1')
        self._add('s2')
        again = self._add('s1')
        self.assertEqual(again.status_code, 200)


class TeamAssignmentCapTests(CohortCapTestBase):
    """team_size_max binds where the assignment is written."""

    def setUp(self):
        self.instructor = self._instructor('team-instructor')
        self.course, self.section = self._make_section(
            max_teams=4, team_size_min=3, team_size_max=5,
            instructor_id=self.instructor.user_id, tag='TEAM')
        self.game, self.teams = build_minimal_game(f'caps-{id(self)}')
        Game.objects.filter(pk=self.game.pk).update(
            section_id=self.section.section_id)
        self.game.refresh_from_db()
        self.team = self.teams[0]
        self.client_ = self._client(self.instructor)

    def _enrol(self, student_id, team_id=None):
        user = User.objects.create(
            username=f'{student_id}-{id(self)}', role='Student',
            password_hash='x', student_id=student_id)
        Enrollment.objects.create(
            user_id=user.user_id, section_id=self.section.section_id,
            team_id=team_id, is_active=True)
        return user

    def _assign(self, user, team_id):
        return self.client_.put('/api/team-management/', {
            'action': 'assign',
            'assignments': [{'user_id': user.user_id, 'team_id': team_id}],
        }, format='json')

    def test_a_team_fills_to_its_maximum(self):
        for index in range(5):
            user = self._enrol(f'full{index}')
            response = self._assign(user, self.team.id)
            self.assertEqual(response.data['errors'], [], f'member {index + 1}')
        self.assertEqual(team_member_count(self.team.id), 5)

    def test_a_sixth_member_is_refused(self):
        for index in range(5):
            self._enrol(f'seated{index}', team_id=self.team.id)
        sixth = self._enrol('sixth')

        response = self._assign(sixth, self.team.id)

        self.assertEqual(response.data['updated'], 0)
        self.assertEqual(len(response.data['errors']), 1)
        self.assertIn('5', response.data['errors'][0]['error'])
        # Proves nothing was written: the sixth student is still unassigned.
        self.assertIsNone(Enrollment.objects.get(
            user_id=sixth.user_id).team_id)
        self.assertEqual(team_member_count(self.team.id), 5)

    def test_reasserting_an_existing_assignment_is_not_refused(self):
        members = [self._enrol(f'member{index}', team_id=self.team.id)
                   for index in range(5)]
        response = self._assign(members[0], self.team.id)
        self.assertEqual(response.data['errors'], [])

    def test_a_team_below_minimum_is_reported_not_refused(self):
        """team_size_min is advice while a team is being filled, not a refusal."""
        user = self._enrol('only-one')
        response = self._assign(user, self.team.id)

        self.assertEqual(response.data['updated'], 1)
        self.assertEqual(response.data['errors'], [])
        reported = [row for row in response.data['under_minimum']
                    if row['team_id'] == self.team.id]
        self.assertEqual(len(reported), 1)
        self.assertEqual(reported[0]['minimum'], 3)
        self.assertIn('at least 3', reported[0]['detail'])

    def test_the_user_route_respects_the_same_cap(self):
        """User.team_id is a second membership record; one uncapped route is
        enough to make the cap meaningless (see cohort_caps)."""
        for index in range(5):
            self._enrol(f'seated{index}', team_id=self.team.id)
        sixth = self._enrol('sixth-by-user-route')

        response = self.client_.post(
            f'/api/users/{sixth.user_id}/assign-team/',
            {'team_id': self.team.id}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('code'), 'team_full')
        sixth.refresh_from_db()
        self.assertIsNone(sixth.team_id)

    def test_occupancy_counts_both_membership_records_once(self):
        user = self._enrol('counted-once', team_id=self.team.id)
        User.objects.filter(pk=user.user_id).update(team_id=self.team.id)
        self.assertEqual(team_member_count(self.team.id), 1)


class GameCreationCapTests(CohortCapTestBase):
    """The two disagreeing caps become one: the section's max_teams."""

    def setUp(self):
        self.instructor = self._instructor('creator')
        self.course, self.section = self._make_section(
            max_teams=8, instructor_id=self.instructor.user_id, tag='GAME')
        self.scenario = Scenario.objects.create(
            name=f'Cap scenario {id(self)}', industry_label='Test',
            description='d', starting_cash=1000000, num_rounds=5,
            performance_index_base=100)
        self.client_ = self._client(self.instructor)

    def _create(self, num_teams):
        return self.client_.post('/api/games/create/', {
            'scenario_id': self.scenario.pk, 'num_teams': num_teams,
            'section_id': self.section.section_id,
        }, format='json')

    def test_a_game_above_the_section_cap_is_refused(self):
        response = self._create(9)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('code'), 'team_count_refused')
        self.assertEqual(Game.objects.filter(
            section_id=self.section.section_id).count(), 0)

    def test_the_old_upper_bound_of_sixteen_no_longer_applies(self):
        """The previous cap accepted 16 teams in an 8-team section."""
        response = self._create(16)
        self.assertEqual(response.status_code, 400)
        self.assertIn('8', response.data['error'])

    def test_the_two_caps_now_agree(self):
        """The section cap is the only bound, at the section's own value."""
        for allowed in (2, 8):
            self.assertIsNone(
                game_team_count_error(self.section, allowed),
                f'{allowed} teams is within max_teams=8')
        for refused in (1, 9, 16):
            self.assertIsNotNone(
                game_team_count_error(self.section, refused),
                f'{refused} teams is outside max_teams=8')

    def test_a_narrower_section_cap_binds_immediately(self):
        """CRV2-11 may narrow the field; whichever number is authored binds."""
        Section.objects.filter(pk=self.section.section_id).update(max_teams=6)
        self.section.refresh_from_db()
        self.assertIsNotNone(game_team_count_error(self.section, 7))
        self.assertIsNone(game_team_count_error(self.section, 6))


class CompetitionOwnershipTests(CohortCapTestBase):
    """A competition game needs an instructor of record; a pilot game does not."""

    def setUp(self):
        self.judge = self._instructor('judge')
        self.game, self.teams = build_minimal_game(f'comp-{id(self)}')
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open')
        Game.objects.filter(pk=self.game.pk).update(current_round=1)
        self.game.refresh_from_db()

    def _attach(self, *, instructor_id, competition, tag):
        """Put the game on a cohort, optionally marked as a competition heat."""
        _course, section = self._make_section(
            instructor_id=instructor_id, tag=tag)
        Game.objects.filter(pk=self.game.pk).update(
            section_id=section.section_id)
        self.game.refresh_from_db()
        SimulationInstance.objects.create(
            section_id=section.section_id, game_id=self.game.pk,
            current_round=1, total_rounds=5, status='active',
            settings={'is_competition': True} if competition else {})
        return section

    def _close(self):
        return self._client(self.judge).post(
            f'/api/games/{self.game.pk}/round-control/close/',
            {'reason': 'closing this heat'}, format='json')

    def test_a_competition_game_on_an_unowned_course_is_refused(self):
        self._attach(instructor_id=None, competition=True, tag='COMP')

        response = self._close()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('code'),
                         'competition_course_unowned')
        # Proves the lifecycle action did not run: the round is still open.
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'open')

    def test_the_refusal_says_what_to_do_next(self):
        self._attach(instructor_id=None, competition=True, tag='COMP2')
        payload = self._close().data
        self.assertIn('Assign an instructor', payload['guidance'])
        self.assertIn(self.game.name, payload['error'])

    def test_a_pilot_game_on_an_unowned_course_still_works(self):
        """The unowned-pilot rule is preserved exactly for non-competition games."""
        self._attach(instructor_id=None, competition=False, tag='PILOT')

        response = self._close()

        self.assertNotEqual(response.data.get('code'),
                            'competition_course_unowned')
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'closed')

    def test_a_competition_game_on_an_owned_course_is_allowed(self):
        self._attach(instructor_id=self.judge.user_id, competition=True,
                     tag='OWNED')

        response = self._close()

        self.assertNotEqual(response.data.get('code'),
                            'competition_course_unowned')
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'closed')

    def test_competition_mode_defaults_to_off(self):
        """Nothing becomes a competition game by accident."""
        self._attach(instructor_id=None, competition=False, tag='DEFAULT')
        self.assertFalse(is_competition_game(self.game))

    def test_competition_mode_is_read_from_the_heat(self):
        self._attach(instructor_id=None, competition=True, tag='FLAG')
        self.assertTrue(is_competition_game(self.game))


class LifecycleNamesTheGameTests(CohortCapTestBase):
    """Every lifecycle confirmation names its game (concurrent heats)."""

    def setUp(self):
        self.instructor = self._instructor('namer')
        self.game, self.teams = build_minimal_game(f'named-{id(self)}')
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open')
        Game.objects.filter(pk=self.game.pk).update(current_round=1)
        self.game.refresh_from_db()
        _course, section = self._make_section(
            instructor_id=self.instructor.user_id, tag='NAME')
        Game.objects.filter(pk=self.game.pk).update(
            section_id=section.section_id)
        self.game.refresh_from_db()
        self.client_ = self._client(self.instructor)

    def test_the_close_confirmation_names_the_game(self):
        response = self.client_.post(
            f'/api/games/{self.game.pk}/round-control/close/',
            {'reason': 'closing'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.game.name, response.data['message'])
        self.assertEqual(response.data['game_name'], self.game.name)

    def test_the_deadline_confirmation_names_the_game(self):
        response = self.client_.post(
            f'/api/games/{self.game.pk}/round-control/deadline/',
            {'minutes_from_now': 90}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.game.name, response.data['message'])

    def test_the_round_control_payload_carries_the_game_name(self):
        response = self.client_.get(
            f'/api/games/{self.game.pk}/round-control/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['game_name'], self.game.name)
