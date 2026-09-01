"""A platform is never ready in the round it is created.

V2-040 measured what the code did instead: `_process_platform_development`
created the platform and then, in the same call for the same round, ran the
loop that decrements in-development platforms. A generation authored
`development_rounds: 0` went to -1 and became active immediately; one authored
2 was ready after a single round, so the scenario's numbers meant one less than
they said.

These tests pin the authored figure as the number of rounds actually waited,
the minimum that a zero-round generation still observes, and the scenario
maximum that bounds the other end.
"""
from decimal import Decimal as D

from django.test import TestCase

from core.engine.rd_processing import MIN_DEVELOPMENT_ROUNDS
from core.models import DecisionSubmission, Round
from core.models.decisions import DecisionPlatformDevelopment
from core.models.scenario import PlatformGenerationDefinition, ScenarioConfig
from core.models.team_state import TeamPlatform
from core.tests.test_operator_concurrency import build_minimal_game


class PlatformTimingTests(TestCase):

    def setUp(self):
        self.game, self.teams = build_minimal_game(f'timing-{id(self)}')
        self.team = self.teams[0]
        self.scenario = self.game.scenario

    def generation(self, order, rounds):
        return PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name=f'Gen {order}', description='d',
            generation_order=order, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=rounds)

    def submit_and_process(self, generation, round_number):
        """Submit a development in `round_number` and process that round."""
        rnd, _ = Round.objects.get_or_create(
            game=self.game, round_number=round_number,
            defaults={'status': 'open'})
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=self.team, round=rnd, defaults={'status': 'locked'})
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=generation,
            method='in_house',
            committed_cost=generation.development_cost,
            platform_name=f'P{generation.generation_order}',
            feature_levels={})
        self.process(round_number)
        return submission

    def process(self, round_number):
        """Run the R&D lifecycle for one round, as the engine does."""
        from core.engine.rd_processing import _process_platform_development
        rnd, _ = Round.objects.get_or_create(
            game=self.game, round_number=round_number,
            defaults={'status': 'open'})
        submission = DecisionSubmission.objects.filter(
            team=self.team, round=rnd).first()
        if submission is None:
            submission, _ = DecisionSubmission.objects.get_or_create(
                team=self.team, round=rnd, defaults={'status': 'locked'})
        _process_platform_development(self.team, submission, round_number)

    def platform(self, generation):
        return TeamPlatform.objects.filter(
            team=self.team, platform_generation=generation).first()

    # -- the authored figure is the number of rounds waited -----------------

    def test_a_two_round_platform_waits_two_rounds(self):
        gen = self.generation(2, rounds=2)
        self.submit_and_process(gen, 1)
        self.assertEqual(self.platform(gen).status, 'in_development',
                         'ready in its own creation round')

        self.process(2)
        self.assertEqual(self.platform(gen).status, 'in_development',
                         'ready after one round when two were authored')

        self.process(3)
        self.assertEqual(self.platform(gen).status, 'active')
        self.assertEqual(self.platform(gen).activated_round, 3)

    def test_a_zero_round_generation_still_waits_the_minimum(self):
        gen = self.generation(3, rounds=0)
        self.submit_and_process(gen, 1)
        self.assertEqual(self.platform(gen).status, 'in_development',
                         'a zero-round generation was ready immediately')

        self.process(2)
        self.assertEqual(self.platform(gen).status, 'active')
        self.assertEqual(self.platform(gen).activated_round, 2)

    def test_the_minimum_is_one_round(self):
        self.assertEqual(MIN_DEVELOPMENT_ROUNDS, 1)

    def test_the_scenario_bounds_the_maximum(self):
        ScenarioConfig.objects.create(
            scenario=self.scenario, config_key='max_platform_development_rounds',
            config_value='2', description='CRV2-10 Stage 3')
        gen = self.generation(4, rounds=9)      # authored beyond the maximum
        self.submit_and_process(gen, 1)
        self.process(2)
        self.assertEqual(self.platform(gen).status, 'in_development')
        self.process(3)
        self.assertEqual(self.platform(gen).status, 'active',
                         'a generation authored at 9 was not bounded to 2')

    def test_development_rounds_remaining_never_goes_negative(self):
        gen = self.generation(5, rounds=0)
        self.submit_and_process(gen, 1)
        self.process(2)
        platform = self.platform(gen)
        self.assertEqual(platform.status, 'active')
        self.assertGreaterEqual(platform.development_rounds_remaining, 0,
                                'the decrement ran against its own creation')


class UnlockGateTests(TestCase):
    """A generation cannot be developed before the round it unlocks.

    V2-039: the check lived only in the lock validator. A Gen 3 platform
    unlocking at round 5 was submitted in round 3; the team never locked, close
    defaulted the submission, and the engine built it anyway. A gate that binds
    only the teams who lock does not bind anyone.
    """

    def setUp(self):
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        self.game, self.teams = build_minimal_game(f'unlock-{id(self)}')
        self.team = self.teams[0]
        self.round = Round.objects.create(
            game=self.game, round_number=2, status='open')
        self.locked = PlatformGenerationDefinition.objects.create(
            scenario=self.game.scenario, name='Gen 3 locked', description='d',
            generation_order=3, unlock_round=5,
            development_cost=D('25000000'), license_cost=D('55000000'),
            development_rounds=2)
        self.student = User.objects.create(
            username=f'student-{id(self)}', role='student', password_hash='x')
        course = Course.objects.create(
            course_code=f'UL{id(self) % 100000}', course_name='Unlock',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=self.student.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True)

    def client_as_student(self):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.student)}')
        return client

    def payload(self):
        return [{'platform_generation': self.locked.id, 'method': 'in_house',
                 'committed_cost': str(self.locked.development_cost),
                 'platform_name': 'Too early', 'feature_levels': {}}]

    def test_the_per_type_surface_refuses_a_locked_generation(self):
        response = self.client_as_student().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/2/platforms/', self.payload(), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('unlocks in round 5', str(response.data))
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 0)

    def test_the_whole_submission_surface_refuses_it_too(self):
        response = self.client_as_student().post(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/round/2/',
            {'platform_developments': self.payload()}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('unlocks in round 5', str(response.data))
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 0)

    def test_a_row_written_behind_the_api_refuses_the_round(self):
        from core.services import rd_costs
        submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='locked')
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=self.locked,
            method='in_house', committed_cost=self.locked.development_cost,
            platform_name='Smuggled', feature_levels={})
        violations = rd_costs.persisted_unlock_violations(self.game, self.round)
        self.assertEqual(len(violations), 1)
        self.assertIn('unlocks in round 5', violations[0]['detail'])
        self.assertIn('DecisionPlatformDevelopment',
                      rd_costs.describe_unlock_violations(violations))

    def test_an_unlocked_generation_is_accepted(self):
        available = PlatformGenerationDefinition.objects.create(
            scenario=self.game.scenario, name='Gen 2 open', description='d',
            generation_order=2, unlock_round=1,
            development_cost=D('15000000'), license_cost=D('35000000'),
            development_rounds=2)
        response = self.client_as_student().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/2/platforms/',
            [{'platform_generation': available.id, 'method': 'in_house',
              'platform_name': 'In time', 'feature_levels': {}}],
            format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(DecisionPlatformDevelopment.objects.get().committed_cost,
                         D('15000000'))
