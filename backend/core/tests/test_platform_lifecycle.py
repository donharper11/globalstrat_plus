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


class LifecycleFixture(TestCase):

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

    def run_cost_path(self, round_number, capitalize):
        """Run the real cost path for one round and report what it booked.

        Calls `calculate_operating_expenses`, so the expense and capitalisation
        branches are exercised as the engine runs them rather than re-derived
        here. An earlier version of this helper took a `capitalize` flag and
        ignored it, so the capitalisation test asserted nothing about
        capitalisation.
        """
        from core.engine.costs import calculate_operating_expenses
        from core.engine.utils import RoundContext
        from core.models import Round
        from core.models.scenario import ScenarioConfig
        from core.models.team_state import TeamPlatform

        ScenarioConfig.objects.update_or_create(
            scenario=self.scenario,
            config_key='capitalize_platform_development',
            defaults={'config_value': 'true' if capitalize else 'false',
                      'description': 'CRV2-10 Stage 3A accounting test'})
        # get_config memoises per scenario, so a value written after the first
        # read would otherwise be invisible and this test would silently
        # measure the default branch twice.
        from core.engine import utils as engine_utils
        engine_utils._config_cache.pop(self.scenario.id, None)
        rnd, _ = Round.objects.get_or_create(
            game=self.game, round_number=round_number,
            defaults={'status': 'open'})
        submission = DecisionSubmission.objects.filter(
            team=self.team, round=rnd).first()
        before = {
            p.id: (p.capitalized_cost or D('0'))
            for p in TeamPlatform.objects.filter(team=self.team)}
        # The engine's own context, not a stand-in. A hand-built namespace
        # missed `round_number` and the cost path raised before reaching the
        # branch under test -- which the assertion on `result` caught.
        context = RoundContext(self.game, round_number)
        # State the earlier pipeline stages would have populated. The platform
        # branch does not read any of it, but the function does, so it is
        # seeded empty rather than stubbed away -- the branch under test runs
        # inside the real function.
        for attribute in ('revenue', 'cogs', 'market_revenue', 'market_profit',
                          'inventory_costs', 'logistics', 'entry_mode_overhead',
                          'esg_savings', 'interest', 'opex',
                          'org_structure_costs', 'partnership_savings',
                          'repatriation_costs', 'retirement_costs',
                          'retirement_revenue', 'talent_savings', 'tax',
                          'tax_audit_penalties', 'tax_structure_maintenance',
                          'tax_structure_savings'):
            if not hasattr(context, attribute):
                setattr(context, attribute, {})
        # The function mutates the context and returns None, so success is
        # recorded explicitly rather than inferred from a return value.
        try:
            calculate_operating_expenses(context)
            result = {'ran': True}
        except Exception as error:      # noqa: BLE001 - reported, not hidden
            result = {'ran': False,
                      'error': f'{type(error).__name__}: {error}'}
        after = {
            p.id: (p.capitalized_cost or D('0'))
            for p in TeamPlatform.objects.filter(team=self.team)}
        capitalised = sum(
            (after[pid] - before.get(pid, D('0')) for pid in after), D('0'))
        # The figures the cost path itself produced for this team, not a
        # re-derivation. An earlier version of this test summed its own
        # selector, which proved that funded_round picks one round and nothing
        # about what the engine booked -- the very defect it was written for.
        booked = context.opex.get(self.team.id, {}) if isinstance(
            getattr(context, 'opex', None), dict) else {}
        return {
            'result': result,
            'rd_expense': D(str(booked.get('rd_expense', D('0')))),
            'platform_capex': D(str(booked.get('platform_capex', D('0')))),
            'capitalised_delta': capitalised,
        }

    def platform(self, generation):
        return TeamPlatform.objects.filter(
            team=self.team, platform_generation=generation).first()


class PlatformTimingTests(LifecycleFixture):
    """The authored figure is the number of rounds actually waited."""

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


class FundingLifecycleTests(LifecycleFixture):
    """A platform completes only if its cost was actually charged.

    Before this a team that could not pay still got the platform: the engine
    created it in development regardless, and Stage 2's charge path took the
    committed cost whether or not the cash existed. A team that overreaches now
    keeps an unfunded draft it may fund later, rather than a free platform.
    """

    def poor_team(self, cash):
        from core.models import Team
        Team.objects.filter(pk=self.team.pk).update(cash_on_hand=cash)
        self.team.refresh_from_db()

    def test_a_team_that_cannot_pay_keeps_an_unfunded_draft(self):
        gen = self.generation(2, rounds=2)
        self.poor_team(D('100'))
        self.submit_and_process(gen, 1)
        platform = self.platform(gen)
        self.assertEqual(platform.status, 'unfunded_draft')
        self.assertIsNone(platform.development_started_round,
                          'an unfunded draft started its clock')
        self.assertIsNone(platform.funded_round)

    def test_an_unfunded_draft_never_becomes_active_on_its_own(self):
        gen = self.generation(2, rounds=2)
        self.poor_team(D('100'))
        self.submit_and_process(gen, 1)
        for round_number in (2, 3, 4):
            self.process(round_number)
            self.assertEqual(self.platform(gen).status, 'unfunded_draft',
                             f'draft advanced in round {round_number}')

    def test_the_clock_starts_in_the_round_the_funding_lands(self):
        gen = self.generation(2, rounds=2)
        self.poor_team(D('100'))
        self.submit_and_process(gen, 1)
        self.assertEqual(self.platform(gen).status, 'unfunded_draft')

        # The money arrives; the draft starts building in that round.
        self.poor_team(D('50000000'))
        self.process(2)
        platform = self.platform(gen)
        self.assertEqual(platform.status, 'in_development')
        self.assertEqual(platform.development_started_round, 2)
        self.assertEqual(platform.funded_round, 2)

        # And it still waits the authored two rounds from there.
        self.process(3)
        self.assertEqual(self.platform(gen).status, 'in_development')
        self.process(4)
        self.assertEqual(self.platform(gen).status, 'active')
        self.assertEqual(self.platform(gen).activated_round, 4)

    def test_a_funded_platform_records_the_round_it_was_paid_for(self):
        gen = self.generation(2, rounds=2)
        self.submit_and_process(gen, 1)
        platform = self.platform(gen)
        self.assertEqual(platform.status, 'in_development')
        self.assertEqual(platform.funded_round, 1)


class FeatureCapTests(LifecycleFixture):
    """A platform carries at most `max_platform_features` features.

    Enforced on both write surfaces and refused at the engine boundary. It is
    deliberately NOT applied by truncating at activation: slicing an over-cap
    decision built a platform carrying an arbitrary subset while the stored row
    still named the full set, so the evidence and the platform disagreed
    silently — the same shape V2-037 taught this handoff to refuse.
    """

    def features(self, count):
        from core.models.scenario import FeatureDefinition
        return [FeatureDefinition.objects.create(
            scenario=self.scenario, code=f'F{index}', name=f'F{index}',
            description='d', layer='platform', category='core',
            cost_curve_type='linear', cost_base=D('1000'))
            for index in range(count)]

    def student_client(self):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        user = User.objects.create(
            username=f'cap-student-{id(self)}', role='student',
            password_hash='x')
        course = Course.objects.create(
            course_code=f'CAP{id(self) % 100000}', course_name='Cap',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=user.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    # -- both write surfaces ------------------------------------------------

    def test_the_per_type_surface_refuses_an_over_cap_platform(self):
        gen = self.generation(2, rounds=1)
        Round.objects.get_or_create(game=self.game, round_number=1,
                                    defaults={'status': 'open'})
        response = self.student_client().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/platforms/',
            [{'platform_generation': gen.id, 'method': 'in_house',
              'platform_name': 'Wide',
              'feature_levels': {str(f.id): 3 for f in self.features(9)}}],
            format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Maximum 5 features', str(response.data))
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 0,
                         'a refused over-cap payload persisted a row')

    def test_the_whole_submission_surface_refuses_it_too(self):
        gen = self.generation(2, rounds=1)
        Round.objects.get_or_create(game=self.game, round_number=1,
                                    defaults={'status': 'open'})
        response = self.student_client().post(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/round/1/',
            {'platform_developments': [
                {'platform_generation': gen.id, 'method': 'in_house',
                 'platform_name': 'Wide',
                 'feature_levels': {str(f.id): 3 for f in self.features(9)}}]},
            format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Maximum 5 features', str(response.data))
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 0)

    def test_a_within_cap_payload_is_accepted(self):
        gen = self.generation(2, rounds=1)
        Round.objects.get_or_create(game=self.game, round_number=1,
                                    defaults={'status': 'open'})
        response = self.student_client().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/platforms/',
            [{'platform_generation': gen.id, 'method': 'in_house',
              'platform_name': 'Narrow',
              'feature_levels': {str(f.id): 3 for f in self.features(4)}}],
            format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 1)

    # -- the engine boundary refuses rather than truncates -------------------

    def test_an_over_cap_persisted_row_refuses_phase_1(self):
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        from core.models.results_financials import RoundResultFinancials
        from core.models.team_state import TeamPlatform
        gen = self.generation(2, rounds=1)
        rnd, _ = Round.objects.get_or_create(
            game=self.game, round_number=1,
            defaults={'status': 'closed'})
        Round.objects.filter(pk=rnd.pk).update(status='closed')
        # Every team must be locked or process_round refuses for that reason
        # first, which would prove nothing about the cap.
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=rnd, defaults={'status': 'locked'})
        submission = DecisionSubmission.objects.get(team=self.team, round=rnd)
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=gen, method='in_house',
            committed_cost=gen.development_cost, platform_name='Smuggled',
            feature_levels={str(f.id): 3 for f in self.features(9)})

        with self.assertRaises(InvalidPersistedDecisionError) as caught:
            process_round(self.game.id)
        message = str(caught.exception)
        self.assertIn('more features than a platform may carry', message)
        self.assertIn('names 9 features', message)
        self.assertIn('at most 5', message)

        # And nothing competitive was written.
        self.assertEqual(
            RoundResultFinancials.objects.filter(game=self.game).count(), 0)
        self.assertEqual(
            TeamPlatform.objects.filter(name='Smuggled').count(), 0)

    def test_a_within_cap_row_still_activates_with_every_feature(self):
        from core.models.team_state import TeamPlatformFeatureLevel
        gen = self.generation(2, rounds=1)
        chosen = {str(f.id): 3 for f in self.features(4)}
        rnd, _ = Round.objects.get_or_create(
            game=self.game, round_number=1, defaults={'status': 'open'})
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=self.team, round=rnd, defaults={'status': 'locked'})
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=gen, method='in_house',
            committed_cost=gen.development_cost, platform_name='Narrow',
            feature_levels=chosen)
        self.process(1)
        self.process(2)
        platform = self.platform(gen)
        self.assertEqual(platform.status, 'active')
        self.assertEqual(
            TeamPlatformFeatureLevel.objects.filter(
                team_platform=platform).count(), 4,
            'a within-cap decision lost features at activation')

    def test_the_cap_is_stated_in_one_place(self):
        from core.services import rd_costs
        self.assertEqual(rd_costs.feature_cap(self.scenario), 5)
        self.assertIn('at most 5', rd_costs.feature_count_problem(
            {str(i): 3 for i in range(9)}, self.scenario))
        self.assertIsNone(rd_costs.feature_count_problem(
            {str(i): 3 for i in range(5)}, self.scenario))


class PlatformOwnershipTests(LifecycleFixture):
    """R&D may only be invested in a platform the submitting team owns.

    V2-044. The write surfaces accepted a foreign `team_platform` and only the
    lock refused it, so a team that never locked carried the row into the
    engine, where it wrote duplicate PendingFeatureGain rows against the
    victim's platform and left the round unprocessable.
    """

    def setUp(self):
        super().setUp()
        from core.models.scenario import (FeatureDefinition, FeatureLevelCost,
                                          PlatformFeatureCeiling)
        from core.models.team_state import TeamPlatform
        self.other_team = self.teams[1]
        self.gen = self.generation(2, rounds=1)
        self.mine = TeamPlatform.objects.create(
            team=self.team, platform_generation=self.gen, name='Mine',
            # Ruling 1 froze ready platforms. This suite is about
            # ownership, so both platforms stay in development --
            # otherwise the freeze refuses first and the ownership
            # message is never reached.
            status='in_development')
        self.theirs = TeamPlatform.objects.create(
            team=self.other_team, platform_generation=self.gen,
            name='Theirs', status='in_development')
        self.feature = FeatureDefinition.objects.create(
            scenario=self.scenario, code='OWN', name='Owned', description='d',
            layer='platform', category='core', cost_curve_type='linear',
            cost_base=D('1000'))
        PlatformFeatureCeiling.objects.create(
            platform_generation=self.gen, feature=self.feature,
            ceiling_value=D('5'), starting_value=D('0'))
        cumulative = D('0')
        for level in range(1, 6):
            cumulative += D('1000')
            FeatureLevelCost.objects.create(
                feature=self.feature, platform_generation=self.gen,
                level=level, incremental_cost=D('1000'),
                cumulative_cost=cumulative)

    def student_client(self):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        user = User.objects.create(
            username=f'own-student-{id(self)}', role='student',
            password_hash='x')
        course = Course.objects.create(
            course_code=f'OWN{id(self) % 100000}', course_name='Own',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=user.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    def foreign_row(self):
        return {'team_platform': self.theirs.id, 'feature': self.feature.id,
                'method': 'in_house', 'target_level': 3}

    def test_the_per_type_surface_refuses_a_foreign_platform(self):
        from core.models.decisions import DecisionRDInvestment
        Round.objects.get_or_create(game=self.game, round_number=1,
                                    defaults={'status': 'open'})
        response = self.student_client().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/rd/', [self.foreign_row()], format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('belongs to another team', str(response.data))
        self.assertEqual(DecisionRDInvestment.objects.count(), 0,
                         'a refused foreign-platform payload persisted a row')

    def test_the_whole_submission_surface_refuses_it_too(self):
        from core.models.decisions import DecisionRDInvestment
        Round.objects.get_or_create(game=self.game, round_number=1,
                                    defaults={'status': 'open'})
        response = self.student_client().post(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/round/1/',
            {'rd_investments': [self.foreign_row()]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('belongs to another team', str(response.data))
        self.assertEqual(DecisionRDInvestment.objects.count(), 0)

    def test_investing_in_your_own_platform_is_accepted(self):
        from core.models.decisions import DecisionRDInvestment
        Round.objects.get_or_create(game=self.game, round_number=1,
                                    defaults={'status': 'open'})
        response = self.student_client().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/rd/',
            [{'team_platform': self.mine.id, 'feature': self.feature.id,
              'method': 'in_house', 'target_level': 3}], format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(DecisionRDInvestment.objects.count(), 1)

    def test_a_stored_foreign_row_refuses_phase_1(self):
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        from core.models.decisions import DecisionRDInvestment
        from core.models.results_financials import RoundResultFinancials
        from core.models.team_state import TeamPlatformFeatureLevel
        rnd, _ = Round.objects.get_or_create(
            game=self.game, round_number=1, defaults={'status': 'closed'})
        Round.objects.filter(pk=rnd.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=rnd, defaults={'status': 'locked'})
        submission = DecisionSubmission.objects.get(team=self.team, round=rnd)
        DecisionRDInvestment.objects.create(
            submission=submission, team_platform=self.theirs,
            feature=self.feature, method='in_house', amount=D('3000'),
            target_level=3, calculated_cost=D('3000'))

        with self.assertRaises(InvalidPersistedDecisionError) as caught:
            process_round(self.game.id)
        message = str(caught.exception)
        self.assertIn('does not own', message)
        self.assertIn('DecisionRDInvestment', message)

        # Nothing competitive was written, and the victim's platform is intact.
        self.assertEqual(
            RoundResultFinancials.objects.filter(game=self.game).count(), 0)
        self.assertEqual(
            TeamPlatformFeatureLevel.objects.filter(
                team_platform=self.theirs).count(), 0)


class FundingAccountingTests(LifecycleFixture):
    """Payment, accounting and the clock are one exactly-once event.

    The first cut made `funded_round` a label rather than evidence. The charge
    still followed the submission row, so an `unfunded_draft` was billed in the
    round it was first asked for, and when the money later arrived the draft
    started building with nothing booked in that round — the decision belonged
    to an earlier submission. Payment and the clock were never the same event.

    The charge now follows `TeamPlatform.funded_round`. These tests walk the
    same platform across four rounds and read what
    `calculate_operating_expenses` actually booked -- `rd_expense` and
    `platform_capex` from `context.opex` -- alongside status, `funded_round`,
    the start round and the rounds remaining.

    No cash figure is observed here, and nothing below claims one.
    """



    def test_cost_is_booked_exactly_once_in_the_funding_round(self):
        """Observed through calculate_operating_expenses, not re-derived."""
        from core.models import Team
        from core.services.rd_costs import platform_development_cost
        gen = self.generation(2, rounds=2)
        authored = platform_development_cost(gen, 'in_house')
        booked = {}

        # Round 1: asked for, cannot pay. Nothing booked anywhere.
        Team.objects.filter(pk=self.team.pk).update(cash_on_hand=D('100'))
        self.team.refresh_from_db()
        self.submit_and_process(gen, 1)
        platform = self.platform(gen)
        self.assertEqual(platform.status, 'unfunded_draft')
        self.assertIsNone(platform.funded_round)
        self.assertIsNone(platform.development_started_round)
        self.assertIsNone(platform.development_rounds_remaining)
        booked[1] = self.run_cost_path(1, capitalize=False)
        self.assertTrue(booked[1]['result']['ran'], booked[1]['result'])
        self.assertEqual(booked[1]['rd_expense'], D('0'),
                         'an unfunded draft was expensed in its request round')
        self.assertEqual(booked[1]['platform_capex'], D('0'))

        # Round 2: the money lands. Expensed here, clock starts here.
        Team.objects.filter(pk=self.team.pk).update(cash_on_hand=D('50000000'))
        self.team.refresh_from_db()
        self.process(2)
        platform = self.platform(gen)
        self.assertEqual(platform.status, 'in_development')
        self.assertEqual(platform.funded_round, 2)
        self.assertEqual(platform.development_started_round, 2)
        self.assertEqual(platform.development_rounds_remaining, 2)
        booked[2] = self.run_cost_path(2, capitalize=False)
        self.assertTrue(booked[2]['result']['ran'], booked[2]['result'])
        self.assertEqual(booked[2]['rd_expense'], authored,
                         'the authored cost was not expensed in the funding round')
        self.assertEqual(booked[2]['platform_capex'], D('0'),
                         'expense mode moved cost onto the balance sheet')

        # Rounds 3 and 4: not booked again, clock not restarted.
        for round_number in (3, 4):
            self.process(round_number)
            booked[round_number] = self.run_cost_path(round_number,
                                                      capitalize=False)
            self.assertTrue(booked[round_number]['result']['ran'])
            self.assertEqual(booked[round_number]['rd_expense'], D('0'),
                             f'charged again in round {round_number}')
            self.assertEqual(booked[round_number]['platform_capex'], D('0'))
        platform = self.platform(gen)
        self.assertEqual(platform.status, 'active')
        self.assertEqual(platform.funded_round, 2, 'funding round moved')
        self.assertEqual(platform.development_started_round, 2,
                         'the clock restarted')

        # Exactly once, across the whole lifecycle, from what was booked.
        self.assertEqual(
            sum((booked[r]['rd_expense'] for r in (1, 2, 3, 4)), D('0')),
            authored,
            'the authored cost was not booked exactly once')
        self.assertEqual(
            sum((booked[r]['platform_capex'] for r in (1, 2, 3, 4)), D('0')),
            D('0'))

    def test_a_platform_funded_on_request_is_charged_in_that_round(self):
        from core.services.rd_costs import platform_development_cost
        gen = self.generation(3, rounds=1)
        authored = platform_development_cost(gen, 'in_house')
        self.submit_and_process(gen, 1)
        self.assertEqual(self.platform(gen).funded_round, 1)
        first = self.run_cost_path(1, capitalize=False)
        self.assertTrue(first['result']['ran'], first['result'])
        self.assertEqual(first['rd_expense'], authored)
        self.process(2)
        second = self.run_cost_path(2, capitalize=False)
        self.assertEqual(second['rd_expense'], D('0'))

    def test_the_capitalisation_mode_books_the_cost_as_an_asset(self):
        """The capitalised branch, exercised through the real cost path."""
        from core.models import Team
        from core.services.rd_costs import platform_development_cost
        gen = self.generation(4, rounds=1)
        authored = platform_development_cost(gen, 'in_house')

        Team.objects.filter(pk=self.team.pk).update(cash_on_hand=D('100'))
        self.team.refresh_from_db()
        self.submit_and_process(gen, 1)
        draft_round = self.run_cost_path(1, capitalize=True)
        self.assertTrue(draft_round['result']['ran'], draft_round['result'])
        self.assertEqual(draft_round['platform_capex'], D('0'),
                         'an unfunded draft reported capex')
        self.assertEqual(draft_round['rd_expense'], D('0'))
        self.assertEqual(draft_round['capitalised_delta'], D('0'),
                         'an unfunded draft was capitalised')

        Team.objects.filter(pk=self.team.pk).update(cash_on_hand=D('50000000'))
        self.team.refresh_from_db()
        self.process(2)
        funding_round = self.run_cost_path(2, capitalize=True)
        self.assertTrue(funding_round['result']['ran'], funding_round['result'])
        self.assertEqual(funding_round['platform_capex'], authored,
                         'the cost path did not report capex in the funding '
                         'round')
        self.assertEqual(funding_round['rd_expense'], D('0'),
                         'capitalisation mode also expensed the cost')
        # Second check, on the asset itself rather than the reported figure.
        self.assertEqual(funding_round['capitalised_delta'], authored,
                         'the authored cost was not capitalised in the '
                         'funding round')

        later = self.run_cost_path(3, capitalize=True)
        self.assertEqual(later['platform_capex'], D('0'),
                         'capex reported again after the funding round')
        self.assertEqual(later['rd_expense'], D('0'))
        self.assertEqual(later['capitalised_delta'], D('0'),
                         'the platform was capitalised a second time')

    def test_the_expense_mode_books_the_cost_as_expense(self):
        """Expense mode books the cost somewhere, not merely nowhere.

        Asserting only that nothing was capitalised would pass for a branch
        that booked nothing at all, which is the failure this stage began with.
        """
        from core.services.rd_costs import platform_development_cost
        gen = self.generation(5, rounds=1)
        authored = platform_development_cost(gen, 'in_house')
        self.submit_and_process(gen, 1)
        expensed = self.run_cost_path(1, capitalize=False)
        self.assertTrue(expensed['result']['ran'], expensed['result'])
        self.assertEqual(expensed['rd_expense'], authored,
                         'expense mode booked nothing')
        self.assertEqual(expensed['platform_capex'], D('0'))
        self.assertEqual(expensed['capitalised_delta'], D('0'),
                         'the expense mode moved cost onto the balance sheet')


class AggregateFundingTests(LifecycleFixture):
    """No set of platform transitions may book more than the funding available.

    V2-045. Affordability was a per-row boolean against `team.cash_on_hand`,
    asked independently by each lifecycle loop, so two $1,000,000 drafts against
    $1,500,000 both started and the accounting path booked $2,000,000. A
    per-item test that never reserves what it has already accepted does not
    compose.
    """

    def two_generations(self, price=D('1000000')):
        from core.models.scenario import PlatformGenerationDefinition
        made = []
        for order in (2, 3):
            made.append(PlatformGenerationDefinition.objects.create(
                scenario=self.scenario, name=f'Agg Gen {order}',
                description='d', generation_order=order, unlock_round=0,
                development_cost=price, license_cost=price * 2,
                development_rounds=1))
        return made

    def request(self, generations, round_number, via_orm=False):
        """Submit a development for each generation in one round."""
        rnd, _ = Round.objects.get_or_create(
            game=self.game, round_number=round_number,
            defaults={'status': 'open'})
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=self.team, round=rnd, defaults={'status': 'locked'})
        for gen in generations:
            DecisionPlatformDevelopment.objects.create(
                submission=submission, platform_generation=gen,
                method='in_house', committed_cost=gen.development_cost,
                platform_name=f'Agg {gen.generation_order}',
                feature_levels={})
        return submission

    def states(self):
        from core.models.team_state import TeamPlatform
        return sorted(
            (p.name, p.status, p.funded_round, p.development_started_round)
            for p in TeamPlatform.objects.filter(team=self.team)
            if p.name.startswith('Agg'))

    def set_cash(self, amount):
        from core.models import Team
        Team.objects.filter(pk=self.team.pk).update(cash_on_hand=amount)
        self.team.refresh_from_db()

    # -- the reported reproduction ----------------------------------------

    def test_two_drafts_cannot_both_spend_the_same_cash(self):
        first, second = self.two_generations()
        price = first.development_cost

        # Round 1: both requested, neither affordable, both drafts.
        self.set_cash(D('100'))
        self.request([first, second], 1)
        self.process(1)
        self.assertEqual(
            [(name, status) for name, status, _, _ in self.states()],
            [('Agg 2', 'unfunded_draft'), ('Agg 3', 'unfunded_draft')])

        # Round 2: 1.5x one platform's price. Exactly one may start.
        self.set_cash(price + price / 2)
        self.process(2)
        started = [row for row in self.states() if row[1] == 'in_development']
        drafts = [row for row in self.states() if row[1] == 'unfunded_draft']
        self.assertEqual(len(started), 1,
                         f'{len(started)} platforms started on 1.5x one price')
        self.assertEqual(len(drafts), 1)
        self.assertIsNone(drafts[0][2], 'an unfunded draft kept a funded_round')
        self.assertIsNone(drafts[0][3], 'an unfunded draft kept a start round')

        # And the accounting path books one price, not two.
        booked = self.run_cost_path(2, capitalize=False)
        self.assertTrue(booked['result']['ran'], booked['result'])
        self.assertEqual(booked['rd_expense'], price,
                         'the accounting path booked more than one platform')

        # Round 3: more money arrives; the remaining draft starts and is
        # booked once, in the round its own clock starts.
        self.set_cash(price * 2)
        self.process(3)
        # The first platform was funded in round 2 with a one-round build, so
        # by now it is active; what matters is that neither is still an
        # unfunded draft.
        self.assertEqual(
            [status for _, status, _, _ in self.states()],
            ['active', 'in_development'])
        self.assertNotIn('unfunded_draft',
                         [status for _, status, _, _ in self.states()])
        later = self.run_cost_path(3, capitalize=False)
        self.assertEqual(later['rd_expense'], price,
                         'the later-funded draft was not booked exactly once')

    def test_two_requests_in_one_round_cannot_both_spend_the_same_cash(self):
        """The same-round control: aggregate safety without a carried draft."""
        first, second = self.two_generations()
        price = first.development_cost
        self.set_cash(price + price / 2)
        self.request([first, second], 1)
        self.process(1)
        started = [row for row in self.states() if row[1] == 'in_development']
        self.assertEqual(len(started), 1,
                         f'{len(started)} platforms started on 1.5x one price')
        booked = self.run_cost_path(1, capitalize=False)
        self.assertEqual(booked['rd_expense'], price)

    def test_a_row_inserted_outside_the_api_is_still_bounded(self):
        """Aggregate safety must not depend on the serializer having run."""
        first, second = self.two_generations()
        price = first.development_cost
        self.set_cash(price + price / 2)
        # Written straight to the table, as an admin edit or restore would.
        self.request([first, second], 1)
        self.process(1)
        booked = self.run_cost_path(1, capitalize=False)
        self.assertEqual(booked['rd_expense'], price,
                         'a directly inserted pair spent the same cash twice')

    def test_the_capitalisation_mode_observes_the_same_selection(self):
        first, second = self.two_generations()
        price = first.development_cost
        self.set_cash(price + price / 2)
        self.request([first, second], 1)
        self.process(1)
        booked = self.run_cost_path(1, capitalize=True)
        self.assertTrue(booked['result']['ran'], booked['result'])
        self.assertEqual(booked['platform_capex'], price,
                         'capitalisation mode funded a different set')
        self.assertEqual(booked['rd_expense'], D('0'))


class GenerationRequestMixin:
    """Fixture and helpers for the generation-conflict classes.

    Deliberately holds no `test_*` methods. `HeldGenerationTests`
    subclassed `DuplicateGenerationTests` and re-ran seven of its cases,
    inflating 48 distinct tests to 55 executions and contradicting the
    checkpoint's own claim that no class inherits another's tests.
    """

    def setUp(self):
        super().setUp()
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        self.gen = self.generation(2, rounds=1)
        self.student = User.objects.create(
            username=f'dup-student-{id(self)}', role='student',
            password_hash='x')
        course = Course.objects.create(
            course_code=f'DUP{id(self) % 100000}', course_name='Dup',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=self.student.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True)
        Round.objects.get_or_create(game=self.game, round_number=1,
                                    defaults={'status': 'open'})

    def client_as_student(self):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.student)}')
        return client

    def pair(self):
        return [{'platform_generation': self.gen.id, 'method': 'in_house',
                 'platform_name': 'Duplicate A', 'feature_levels': {}},
                {'platform_generation': self.gen.id, 'method': 'in_house',
                 'platform_name': 'Duplicate B', 'feature_levels': {}}]

    # -- both supported write surfaces --------------------------------------


class DuplicateGenerationTests(GenerationRequestMixin, LifecycleFixture):
    """A team develops one platform per generation.

    V2-046, a regression introduced by the V2-045 refactor. The engine used to
    get this for free: it created each platform inside the decision loop, so
    the next row's existing-platform query saw the one just created and
    skipped. Collecting candidates before creating any -- which the aggregate
    allocation needs -- made every row see the same pre-loop state, so two rows
    naming one generation were both funded, both created and both charged.
    """

    def test_the_per_type_surface_refuses_a_duplicate_generation(self):
        response = self.client_as_student().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/platforms/', self.pair(), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('one platform per generation', str(response.data))
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 0,
                         'a refused duplicate pair persisted rows')

    def test_the_whole_submission_surface_refuses_it_too(self):
        response = self.client_as_student().post(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/round/1/',
            {'platform_developments': self.pair()}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('one platform per generation', str(response.data))
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 0)

    def test_a_refused_pair_replaces_nothing_already_stored(self):
        """A refusal writes none of the replacement payload."""
        other = self.generation(3, rounds=1)
        client = self.client_as_student()
        accepted = client.patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/platforms/',
            [{'platform_generation': other.id, 'method': 'in_house',
              'platform_name': 'Keeper', 'feature_levels': {}}], format='json')
        self.assertEqual(accepted.status_code, 200, accepted.data)
        refused = client.patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/platforms/', self.pair(), format='json')
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(
            list(DecisionPlatformDevelopment.objects.values_list(
                'platform_name', flat=True)), ['Keeper'])

    # -- the Phase-1 boundary, for rows that bypassed the API ---------------

    def test_a_stored_duplicate_pair_refuses_phase_1(self):
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        from core.models.results_financials import RoundResultFinancials
        from core.models.team_state import TeamPlatform
        rnd = Round.objects.get(game=self.game, round_number=1)
        Round.objects.filter(pk=rnd.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=rnd, defaults={'status': 'locked'})
        submission = DecisionSubmission.objects.get(team=self.team, round=rnd)
        for name in ('Duplicate A', 'Duplicate B'):
            DecisionPlatformDevelopment.objects.create(
                submission=submission, platform_generation=self.gen,
                method='in_house', committed_cost=self.gen.development_cost,
                platform_name=name, feature_levels={})

        with self.assertRaises(InvalidPersistedDecisionError) as caught:
            process_round(self.game.id)
        self.assertIn('already names', str(caught.exception))

        # Refused before any mutation, and nothing was booked.
        self.assertEqual(TeamPlatform.objects.filter(
            team=self.team, platform_generation=self.gen).count(), 0)
        self.assertEqual(
            RoundResultFinancials.objects.filter(game=self.game).count(), 0)

    def test_the_allocator_never_creates_two_for_one_generation(self):
        """Independent of API validation, as the audit required."""
        from core.models.team_state import TeamPlatform
        rnd = Round.objects.get(game=self.game, round_number=1)
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=self.team, round=rnd, defaults={'status': 'locked'})
        for name in ('Duplicate A', 'Duplicate B'):
            DecisionPlatformDevelopment.objects.create(
                submission=submission, platform_generation=self.gen,
                method='in_house', committed_cost=self.gen.development_cost,
                platform_name=name, feature_levels={})
        self.process(1)
        self.assertEqual(
            TeamPlatform.objects.filter(
                team=self.team, platform_generation=self.gen).count(), 1,
            'the allocator created two platforms for one generation')
        booked = self.run_cost_path(1, capitalize=False)
        self.assertEqual(booked['rd_expense'], self.gen.development_cost,
                         'the team was charged twice for one generation')

    # -- positive controls ---------------------------------------------------

    def test_a_corrected_single_request_creates_one_platform(self):
        from core.models.team_state import TeamPlatform
        response = self.client_as_student().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/platforms/',
            [{'platform_generation': self.gen.id, 'method': 'in_house',
              'platform_name': 'Corrected', 'feature_levels': {}}],
            format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.process(1)
        self.assertEqual(TeamPlatform.objects.filter(
            team=self.team, platform_generation=self.gen).count(), 1)
        booked = self.run_cost_path(1, capitalize=False)
        self.assertEqual(booked['rd_expense'], self.gen.development_cost)

    def test_two_distinct_generations_are_still_accepted(self):
        other = self.generation(3, rounds=1)
        response = self.client_as_student().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/platforms/',
            [{'platform_generation': self.gen.id, 'method': 'in_house',
              'platform_name': 'First', 'feature_levels': {}},
             {'platform_generation': other.id, 'method': 'in_house',
              'platform_name': 'Second', 'feature_levels': {}}], format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 2)

    def test_a_retired_generation_may_be_requested_again(self):
        """The existing rule: only a non-retired platform blocks a request."""
        from core.models.team_state import TeamPlatform
        TeamPlatform.objects.create(
            team=self.team, platform_generation=self.gen, name='Old',
            status='retired')
        rnd = Round.objects.get(game=self.game, round_number=1)
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=self.team, round=rnd, defaults={'status': 'locked'})
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=self.gen,
            method='in_house', committed_cost=self.gen.development_cost,
            platform_name='Rebuilt', feature_levels={})
        self.process(1)
        self.assertEqual(
            sorted(TeamPlatform.objects.filter(
                team=self.team, platform_generation=self.gen)
                .values_list('name', 'status')),
            [('Old', 'retired'), ('Rebuilt', 'in_development')])


class HeldGenerationTests(GenerationRequestMixin, LifecycleFixture):
    """One platform per generation, against state as well as against payload.

    Two gaps the V2-046 repair left. A carried draft was never reconciled
    against another non-retired platform of the same generation, so an upgrade
    residue from runtime `f39b853` -- one funded platform and one draft for the
    same generation -- promoted into a second live platform. And a request for
    an already-held generation was accepted with a 200, persisted at its
    authoritative price, then silently skipped by the engine, which booked
    nothing: a stored decision replaced with no decision at all (V2-047).
    """

    def hold(self, status='active', name='Already Live'):
        from core.models.team_state import TeamPlatform
        return TeamPlatform.objects.create(
            team=self.team, platform_generation=self.gen, name=name,
            status=status,
            development_started_round=1 if status != 'unfunded_draft' else None,
            funded_round=1 if status != 'unfunded_draft' else None,
            development_rounds_remaining=0 if status == 'active' else None)

    def nonretired(self):
        from core.models.team_state import TeamPlatform
        return sorted(TeamPlatform.objects
                      .filter(team=self.team, platform_generation=self.gen)
                      .exclude(status='retired')
                      .values_list('name', 'status'))

    def request_row(self, name='Second Live'):
        return [{'platform_generation': self.gen.id, 'method': 'in_house',
                 'platform_name': name, 'feature_levels': {}}]

    # -- V2-047: the supported writes ---------------------------------------

    def test_the_per_type_surface_refuses_an_already_held_generation(self):
        self.hold()
        response = self.client_as_student().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/platforms/', self.request_row(), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('already holds', str(response.data))
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 0)

    def test_the_whole_submission_surface_refuses_it_too(self):
        self.hold()
        response = self.client_as_student().post(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/round/1/',
            {'platform_developments': self.request_row()}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('already holds', str(response.data))
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 0)

    def test_a_held_generation_is_refused_for_a_draft_too(self):
        self.hold(status='unfunded_draft', name='Carried Draft')
        response = self.client_as_student().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/platforms/', self.request_row(), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('already holds', str(response.data))

    def test_a_refusal_leaves_the_previously_accepted_payload_unchanged(self):
        other = self.generation(3, rounds=1)
        client = self.client_as_student()
        accepted = client.patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/platforms/',
            [{'platform_generation': other.id, 'method': 'in_house',
              'platform_name': 'Keeper', 'feature_levels': {}}], format='json')
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.hold()
        refused = client.patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/platforms/', self.request_row(), format='json')
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(
            list(DecisionPlatformDevelopment.objects.values_list(
                'platform_name', flat=True)), ['Keeper'])

    # -- V2-047: the stored-row bypass --------------------------------------

    def test_a_stored_held_generation_request_refuses_phase_1(self):
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        from core.models.results_financials import RoundResultFinancials
        self.hold()
        rnd = Round.objects.get(game=self.game, round_number=1)
        Round.objects.filter(pk=rnd.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=rnd, defaults={'status': 'locked'})
        submission = DecisionSubmission.objects.get(team=self.team, round=rnd)
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=self.gen,
            method='in_house', committed_cost=self.gen.development_cost,
            platform_name='Second Live', feature_levels={})
        with self.assertRaises(InvalidPersistedDecisionError) as caught:
            process_round(self.game.id)
        self.assertIn('already holds', str(caught.exception))
        self.assertEqual(self.nonretired(), [('Already Live', 'active')])
        self.assertEqual(
            RoundResultFinancials.objects.filter(game=self.game).count(), 0)

    # -- the upgrade residue -------------------------------------------------

    def test_an_active_plus_draft_residue_refuses_phase_1(self):
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        self.hold()
        self.hold(status='unfunded_draft', name='Legacy Draft')
        rnd = Round.objects.get(game=self.game, round_number=1)
        Round.objects.filter(pk=rnd.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=rnd, defaults={'status': 'locked'})
        with self.assertRaises(InvalidPersistedDecisionError) as caught:
            process_round(self.game.id)
        message = str(caught.exception)
        self.assertIn('more than one non-retired platform', message)
        self.assertIn('Already Live', message)
        self.assertIn('Legacy Draft', message)

    def test_two_draft_residue_refuses_phase_1(self):
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        self.hold(status='unfunded_draft', name='Draft One')
        self.hold(status='unfunded_draft', name='Draft Two')
        rnd = Round.objects.get(game=self.game, round_number=1)
        Round.objects.filter(pk=rnd.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=rnd, defaults={'status': 'locked'})
        with self.assertRaises(InvalidPersistedDecisionError):
            process_round(self.game.id)

    def test_the_allocator_never_promotes_a_draft_beside_a_live_platform(self):
        """The defence behind the refusal, exercised on its own."""
        self.hold()
        self.hold(status='unfunded_draft', name='Legacy Draft')
        self.set_cash_for_one_price()
        self.process(1)
        self.assertEqual(
            self.nonretired(),
            [('Already Live', 'active'), ('Legacy Draft', 'unfunded_draft')],
            'the carried draft was promoted beside a live platform')
        booked = self.run_cost_path(1, capitalize=False)
        self.assertEqual(booked['rd_expense'], D('0'),
                         'the residue draft was funded and booked')

    def set_cash_for_one_price(self):
        from core.models import Team
        Team.objects.filter(pk=self.team.pk).update(
            cash_on_hand=self.gen.development_cost + D('500000'))
        self.team.refresh_from_db()

    # -- the retired positive control ---------------------------------------

    def test_a_retired_generation_may_still_be_requested(self):
        from core.models.team_state import TeamPlatform
        TeamPlatform.objects.create(
            team=self.team, platform_generation=self.gen, name='Old',
            status='retired')
        response = self.client_as_student().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
            f'round/1/platforms/', self.request_row('Rebuilt'), format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 1)


class ConflictedDraftAllocatorTests(GenerationRequestMixin, LifecycleFixture):
    """Two carried drafts for one generation are invalid inventory, not a choice.

    The allocator built its `live_generations` set by excluding
    `unfunded_draft`, so a two-draft conflict was invisible to it and the
    de-duplication then promoted the first one -- picking a winner from
    inventory that should be refused outright.

    Phase 1 does refuse that state before the allocator is reached. These tests
    drive the lifecycle directly, without that refusal, because the defence has
    to hold on its own terms rather than because something upstream usually
    fires first.
    """

    def two_drafts(self):
        from core.models.team_state import TeamPlatform
        # `development_method` matters: without it the allocator declines the
        # candidate as unpriced, and the two-draft assertions below would pass
        # for the wrong reason rather than because the conflict was detected.
        return [TeamPlatform.objects.create(
            team=self.team, platform_generation=self.gen, name=name,
            status='unfunded_draft', development_method='in_house',
            development_started_round=None, funded_round=None,
            development_rounds_remaining=None)
            for name in ('Draft One', 'Draft Two')]

    def rows(self):
        from core.models.team_state import TeamPlatform
        return sorted(TeamPlatform.objects
                      .filter(team=self.team, platform_generation=self.gen)
                      .values_list('name', 'status', 'funded_round',
                                   'development_started_round'))

    def fund_generously(self):
        from core.models import Team
        Team.objects.filter(pk=self.team.pk).update(
            cash_on_hand=self.gen.development_cost * 10)
        self.team.refresh_from_db()

    def test_each_draft_would_be_fundable_on_its_own(self):
        """So the two-draft refusals below cannot pass for the wrong reason."""
        from core.services.rd_costs import allocate_platform_funding
        drafts = self.two_drafts()
        self.fund_generously()
        funded = allocate_platform_funding(
            self.team, [(('draft', drafts[0].id), self.gen, 'in_house')])
        self.assertEqual(funded, {('draft', drafts[0].id):
                                  self.gen.development_cost})

    def test_neither_conflicting_draft_is_promoted(self):
        self.two_drafts()
        self.fund_generously()
        self.process(1)
        self.assertEqual(
            self.rows(),
            [('Draft One', 'unfunded_draft', None, None),
             ('Draft Two', 'unfunded_draft', None, None)],
            'a conflicting draft was promoted, funded or given a start round')

    def test_neither_conflicting_draft_is_charged(self):
        self.two_drafts()
        self.fund_generously()
        self.process(1)
        booked = self.run_cost_path(1, capitalize=False)
        self.assertTrue(booked['result']['ran'], booked['result'])
        self.assertEqual(booked['rd_expense'], D('0'),
                         'a conflicting draft was charged')
        self.assertEqual(booked['platform_capex'], D('0'))

    def test_the_capitalisation_selection_is_the_same(self):
        self.two_drafts()
        self.fund_generously()
        self.process(1)
        booked = self.run_cost_path(1, capitalize=True)
        self.assertTrue(booked['result']['ran'], booked['result'])
        self.assertEqual(booked['platform_capex'], D('0'),
                         'a conflicting draft was capitalised')
        self.assertEqual(booked['capitalised_delta'], D('0'))

    def test_a_single_draft_still_funds_normally(self):
        """The control: the guard must bite only on conflicted inventory."""
        from core.models.team_state import TeamPlatform
        TeamPlatform.objects.create(
            team=self.team, platform_generation=self.gen, name='Only Draft',
            status='unfunded_draft', development_method='in_house')
        self.fund_generously()
        self.process(1)
        self.assertEqual(
            self.rows(), [('Only Draft', 'in_development', 1, 1)])
        booked = self.run_cost_path(1, capitalize=False)
        self.assertEqual(booked['rd_expense'], self.gen.development_cost)
