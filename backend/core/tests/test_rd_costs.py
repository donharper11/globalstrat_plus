"""The cost a team is shown is the cost the server computes and charges.

GSP-CRV2-10 Stage 1 measured what happens without this: a platform authored at
$15,000,000 obtained for `committed_cost: 0`, active, charged $0.00 (V2-037),
and a feature raised to its ceiling for `amount: 0` charged nothing in any
round. The prices were authored all along; nothing compared them to what was
submitted, because the display path and the charge path were separate code.

These tests pin the rule on both write surfaces, at the engine boundary, and in
the budget check that platform development used to escape entirely (V2-038).
"""
from decimal import Decimal as D

from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.models import DecisionSubmission, Round, User
from core.models.course import Course, Enrollment, Section
from core.models.decisions import (DecisionBudgetAllocation,
                                   DecisionPlatformDevelopment,
                                   DecisionRDInvestment)
from core.models.scenario import (FeatureLevelCost, PlatformFeatureCeiling,
                                  PlatformGenerationDefinition)
from core.models.team_state import (TeamPlatform, TeamPlatformFeatureLevel)
from core.services import rd_costs
from core.tests.test_operator_concurrency import build_minimal_game


class RDCostFixture(TestCase):
    def setUp(self):
        self.game, self.teams = build_minimal_game(f'rdcost-{id(self)}')
        self.team = self.teams[0]
        self.scenario = self.game.scenario
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open')

        self.gen = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen 2 probe', description='d',
            generation_order=2, unlock_round=0,
            development_cost=D('15000000'), license_cost=D('35000000'),
            development_rounds=2)
        self.platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=self.gen, name='P',
            status='active')
        # A generation the team does NOT hold, for the platform-development
        # cases. The team holds `self.gen` so the feature-upgrade cases have a
        # platform to invest in, and a development request naming a held
        # generation is now refused before its price is examined (V2-047), so
        # the two cases need different generations.
        self.unheld_gen = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen 2 unheld', description='d',
            generation_order=3, unlock_round=0,
            development_cost=D('15000000'), license_cost=D('35000000'),
            development_rounds=2)

        from core.models.scenario import FeatureDefinition
        self.feature = FeatureDefinition.objects.create(
            scenario=self.scenario, code='FEAT', name='Feature',
            description='d', layer='platform', category='core',
            cost_curve_type='linear', cost_base=D('100000'))
        PlatformFeatureCeiling.objects.create(
            platform_generation=self.gen, feature=self.feature,
            ceiling_value=D('14'), starting_value=D('8'))
        TeamPlatformFeatureLevel.objects.create(
            team_platform=self.platform, feature=self.feature,
            current_level=D('11'))
        cumulative = D('0')
        for level, cost in ((12, D('100000')), (13, D('200000')),
                            (14, D('300000'))):
            cumulative += cost
            FeatureLevelCost.objects.create(
                feature=self.feature, platform_generation=self.gen,
                level=level, incremental_cost=cost, cumulative_cost=cumulative)
        self.upgrade_price = D('600000')     # 100k + 200k + 300k

        self.student = User.objects.create(
            username=f'student-{id(self)}', role='student', password_hash='x')
        course = Course.objects.create(
            course_code=f'RD{id(self) % 100000}', course_name='RD',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=self.student.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True)

    def client_as_student(self):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(self.student)}')
        return client

    def url(self, kind):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
                f'round/{self.round.round_number}/{kind}/')

    def whole_url(self):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}/decisions/'
                f'round/{self.round.round_number}/')


class AuthoritativePriceTests(RDCostFixture):

    # -- the calculator ----------------------------------------------------

    def test_method_selects_the_authored_price(self):
        self.assertEqual(
            rd_costs.platform_development_cost(self.gen, 'in_house'),
            D('15000000'))
        self.assertEqual(
            rd_costs.platform_development_cost(self.gen, 'license'),
            D('35000000'))

    def test_an_unknown_method_is_refused_rather_than_priced_at_zero(self):
        with self.assertRaises(rd_costs.UnauthoredCost):
            rd_costs.platform_development_cost(self.gen, 'barter')

    def test_a_feature_upgrade_sums_the_authored_levels(self):
        self.assertEqual(
            rd_costs.feature_upgrade_cost(self.feature, self.gen, 11, 14),
            self.upgrade_price)

    def test_a_target_at_or_below_the_current_level_costs_nothing(self):
        self.assertEqual(
            rd_costs.feature_upgrade_cost(self.feature, self.gen, 11, 11), 0)

    def test_an_unpriced_level_is_refused_not_partially_charged(self):
        # Asking for level 15, which no FeatureLevelCost row prices. Charging
        # only for the levels that happen to exist is how a partly-authored
        # table becomes a discount.
        with self.assertRaises(rd_costs.UnauthoredCost):
            rd_costs.feature_upgrade_cost(self.feature, self.gen, 11, 15)

    # -- the write surfaces ------------------------------------------------

    def test_per_type_surface_refuses_a_platform_priced_at_zero(self):
        response = self.client_as_student().patch(
            self.url('platforms'),
            [{'platform_generation': self.unheld_gen.id, 'method': 'in_house',
              'committed_cost': '0', 'platform_name': 'Free',
              'feature_levels': {}}], format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('15,000,000', str(response.data))
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 0)

    def test_whole_submission_surface_refuses_the_same_payload(self):
        response = self.client_as_student().post(
            self.whole_url(),
            {'platform_developments': [
                {'platform_generation': self.unheld_gen.id, 'method': 'in_house',
                 'committed_cost': '0', 'platform_name': 'Free',
                 'feature_levels': {}}]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('15,000,000', str(response.data))
        self.assertEqual(DecisionPlatformDevelopment.objects.count(), 0)

    def test_an_omitted_cost_is_filled_with_the_authored_price(self):
        response = self.client_as_student().patch(
            self.url('platforms'),
            [{'platform_generation': self.unheld_gen.id, 'method': 'license',
              'platform_name': 'Licensed', 'feature_levels': {}}],
            format='json')
        self.assertEqual(response.status_code, 200, response.data)
        row = DecisionPlatformDevelopment.objects.get()
        self.assertEqual(row.committed_cost, D('35000000'))

    def test_the_authored_price_is_accepted_unchanged(self):
        response = self.client_as_student().patch(
            self.url('platforms'),
            [{'platform_generation': self.unheld_gen.id, 'method': 'in_house',
              'committed_cost': '15000000', 'platform_name': 'Paid',
              'feature_levels': {}}], format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(DecisionPlatformDevelopment.objects.get().committed_cost,
                         D('15000000'))

    def test_a_free_feature_upgrade_is_refused_on_both_surfaces(self):
        row = {'team_platform': self.platform.id, 'feature': self.feature.id,
               'method': 'in_house', 'amount': '0', 'target_level': 14,
               'calculated_cost': '0'}
        per_type = self.client_as_student().patch(
            self.url('rd'), [row], format='json')
        whole = self.client_as_student().post(
            self.whole_url(), {'rd_investments': [row]}, format='json')
        self.assertEqual(per_type.status_code, 400)
        self.assertEqual(whole.status_code, 400)
        self.assertIn('600,000', str(per_type.data))
        self.assertEqual(DecisionRDInvestment.objects.count(), 0)

    def test_a_correctly_priced_upgrade_is_accepted_and_stored(self):
        response = self.client_as_student().patch(
            self.url('rd'),
            [{'team_platform': self.platform.id, 'feature': self.feature.id,
              'method': 'in_house', 'target_level': 14}], format='json')
        self.assertEqual(response.status_code, 200, response.data)
        row = DecisionRDInvestment.objects.get()
        self.assertEqual(row.calculated_cost, self.upgrade_price)
        self.assertEqual(row.amount, self.upgrade_price)

    # -- the engine boundary ------------------------------------------------

    def test_a_row_written_behind_the_api_refuses_the_round(self):
        submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='locked')
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=self.gen,
            method='in_house', committed_cost=D('0'), platform_name='Smuggled',
            feature_levels={})
        violations = rd_costs.persisted_cost_violations(self.game, self.round)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]['field'], 'committed_cost')
        self.assertEqual(violations[0]['stored'], '0.00')
        self.assertEqual(D(violations[0]['authored']), D('15000000'))
        described = rd_costs.describe_cost_violations(violations)
        self.assertIn('DecisionPlatformDevelopment', described)
        self.assertIn('Gen 2 probe', described)

    def test_a_correctly_priced_row_raises_no_violation(self):
        submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='locked')
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=self.gen,
            method='license', committed_cost=D('35000000'),
            platform_name='Paid', feature_levels={})
        self.assertEqual(
            rd_costs.persisted_cost_violations(self.game, self.round), [])

    # -- one budget rule ----------------------------------------------------

    def test_platform_development_counts_against_cash_and_the_rd_budget(self):
        submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        DecisionBudgetAllocation.objects.create(
            submission=submission, rd_budget=D('1000'),
            marketing_budget=D('1000'), strategy_budget=D('1000'))
        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=self.gen,
            method='in_house', committed_cost=D('15000000'),
            platform_name='Paid', feature_levels={})

        assessment = rd_costs.budget_assessment(submission, self.team)
        self.assertEqual(assessment['lines']['platform_development'],
                         '15000000.00')
        self.assertFalse(assessment['within_cash'])
        self.assertFalse(assessment['within_rd_budget'])
        problems = rd_costs.describe_budget_problems(assessment)
        self.assertEqual(len(problems), 2)
        self.assertIn('platform development', problems[0])

    def test_a_submission_within_its_means_passes_the_budget_rule(self):
        submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        DecisionBudgetAllocation.objects.create(
            submission=submission, rd_budget=D('700000'),
            marketing_budget=D('1000'), strategy_budget=D('1000'))
        DecisionRDInvestment.objects.create(
            submission=submission, team_platform=self.platform,
            feature=self.feature, method='in_house',
            amount=self.upgrade_price, target_level=14,
            calculated_cost=self.upgrade_price)
        assessment = rd_costs.budget_assessment(submission, self.team)
        self.assertTrue(assessment['within_cash'])
        self.assertTrue(assessment['within_rd_budget'])
        self.assertEqual(rd_costs.describe_budget_problems(assessment), [])
