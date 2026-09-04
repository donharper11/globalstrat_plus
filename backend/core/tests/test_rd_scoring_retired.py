"""R10 / V2-053: spending is a financial consequence, not a score purchase.

R9 retired the processor that made a `DecisionRDInvestment` change a product.
What it did not do was stop the row being submitted, charged, and *scored* --
so a team could buy strategic-capability and market-alignment credit with money
that bought no capability at all.

This retires the decision and its two direct scoring paths. Three surfaces have
to hold, and they fail independently:

  * both supported writes refuse a new row, naming the route that replaced it;
  * the engine refuses an unprocessed persisted row before competitive
    mutation, rather than discarding it or charging it;
  * neither the performance index nor coherence reads the amount any more.

The last is the one a passing test suite is worst at noticing, because removing
a term makes tests pass more easily. So it is proved by mutation: restore the
old scoring and the result moves; leave it corrected and it does not.
"""
from decimal import Decimal as D

from django.test import TestCase

from core.models import DecisionSubmission, Round
from core.models.decisions import DecisionRDInvestment
from core.models.scenario import (FeatureDefinition, MarketDefinition,
                                  PlatformFeatureCeiling,
                                  PlatformGenerationDefinition)
from core.models.team_state import TeamPlatform, TeamPlatformFeatureLevel
from core.tests.test_operator_concurrency import build_minimal_game


class RetiredRDFixture(TestCase):

    def setUp(self):
        self.game, self.teams = build_minimal_game(f'r10-{id(self)}')
        self.team = self.teams[0]
        self.scenario = self.game.scenario
        self.market = MarketDefinition.objects.filter(
            scenario=self.scenario).first()
        self.gen = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen 1', description='d',
            generation_order=1, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)
        self.feature = FeatureDefinition.objects.create(
            scenario=self.scenario, code='R10', name='Retired feature',
            description='d', layer='platform', category='core',
            cost_curve_type='linear', cost_base=D('1000'),
            default_value=D('3'), max_value=D('10'))
        PlatformFeatureCeiling.objects.create(
            platform_generation=self.gen, feature=self.feature,
            ceiling_value=D('10'), starting_value=D('3'))
        self.platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=self.gen, name='P',
            status='in_development', development_method='in_house',
            development_started_round=0, funded_round=0,
            development_rounds_remaining=1)
        TeamPlatformFeatureLevel.objects.create(
            team_platform=self.platform, feature=self.feature,
            current_level=D('3'))
        self.round, _ = Round.objects.get_or_create(
            game=self.game, round_number=1, defaults={'status': 'open'})

    def client_as_student(self):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        user = User.objects.create(
            username=f'r10-{id(self)}-{User.objects.count()}',
            role='student', password_hash='x')
        course = Course.objects.create(
            course_code=f'R10{id(self) % 10000}{Course.objects.count()}',
            course_name='R10', instructor_id=None, is_active=True)
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

    def rd_row(self):
        return {'team_platform': self.platform.id, 'feature': self.feature.id,
                'method': 'in_house', 'target_level': 8, 'amount': '500000'}


class WriteSurfaceTests(RetiredRDFixture):

    def per_type(self, rows):
        return self.client_as_student().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}'
            f'/decisions/round/1/rd/', rows, format='json')

    def whole_submission(self, rows):
        return self.client_as_student().post(
            f'/api/games/{self.game.id}/teams/{self.team.id}'
            f'/decisions/round/1/', {'rd_investments': rows}, format='json')

    def test_the_per_type_write_refuses_a_new_investment(self):
        response = self.per_type([self.rd_row()])
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('retired', str(response.data).lower())

    def test_the_whole_submission_write_refuses_it_too(self):
        response = self.whole_submission([self.rd_row()])
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('retired', str(response.data).lower())

    def test_the_refusal_names_the_route_that_replaced_it(self):
        """A rule a team cannot act on is a bug report addressed to them."""
        message = str(self.per_type([self.rd_row()]).data).lower()
        self.assertIn('new platform', message)
        self.assertIn('re-base', message)

    def test_neither_refusal_persists_a_row(self):
        self.per_type([self.rd_row()])
        self.whole_submission([self.rd_row()])
        self.assertEqual(DecisionRDInvestment.objects.count(), 0)

    def test_clearing_r_and_d_is_still_allowed(self):
        """Refusing an empty list would strand a team holding a draft row."""
        response = self.per_type([])
        self.assertNotEqual(response.status_code, 400, response.data)


class EngineBoundaryTests(RetiredRDFixture):

    def plant(self):
        """A row that never passed a write surface -- restore, import, shell."""
        Round.objects.filter(pk=self.round.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=self.round, defaults={'status': 'locked'})
        return DecisionRDInvestment.objects.create(
            submission=DecisionSubmission.objects.get(
                team=self.team, round=self.round),
            team_platform=self.platform, feature=self.feature,
            method='in_house', target_level=8, amount=D('500000'))

    def test_a_planted_row_refuses_phase_1(self):
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        row = self.plant()
        with self.assertRaises(InvalidPersistedDecisionError) as caught:
            process_round(self.game.id)
        self.assertIn(str(row.pk), str(caught.exception))

    def test_nothing_competitive_is_written_and_nothing_is_charged(self):
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        from core.models.results_financials import RoundResultFinancials
        cash_before = self.team.cash_on_hand
        self.plant()
        with self.assertRaises(InvalidPersistedDecisionError):
            process_round(self.game.id)
        self.assertEqual(
            RoundResultFinancials.objects.filter(game=self.game).count(), 0)
        self.team.refresh_from_db()
        self.assertEqual(self.team.cash_on_hand, cash_before)

    def test_the_row_is_refused_not_discarded(self):
        """A silently dropped row is a decision vanishing while they pay."""
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        row = self.plant()
        with self.assertRaises(InvalidPersistedDecisionError):
            process_round(self.game.id)
        self.assertTrue(
            DecisionRDInvestment.objects.filter(pk=row.pk).exists())

    def test_a_round_without_such_a_row_still_resolves(self):
        """The control: the precondition must not refuse a healthy round."""
        from core.engine.advance_round import process_round
        from core.models.results_financials import RoundResultFinancials
        Round.objects.filter(pk=self.round.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=self.round, defaults={'status': 'locked'})
        process_round(self.game.id)
        self.assertGreater(
            RoundResultFinancials.objects.filter(game=self.game).count(), 0)


class NoDirectSpendScoringTests(RetiredRDFixture):
    """Mutation evidence: the removal is what changes the number."""

    def strategic_capability(self):
        from core.engine.performance import (_strategic_capability_component,
                                             scenario_rd_spend_target)
        from core.engine.utils import scenario_optimal_headcounts
        # The scenario's own pools, not a stand-in: staffing is a multiplicative
        # factor here, and an empty dict raises rather than scoring zero.
        return _strategic_capability_component(
            self.team, 1, scenario_rd_spend_target(self.scenario),
            scenario_optimal_headcounts(self.scenario))

    def submission(self):
        """A submission with staff, because staffing multiplies the score.

        Without headcount the staffing factor is zero and the whole component
        is zero whatever else changes -- so a comparison built on an unstaffed
        team compares 0 with 0 and cannot detect anything. The first version of
        this suite did exactly that, and the mutation control caught it.
        """
        from core.models.talent import DecisionTalent
        from core.engine.utils import scenario_optimal_headcounts
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=self.team, round=self.round, defaults={'status': 'locked'})
        optimal = scenario_optimal_headcounts(self.scenario)
        DecisionTalent.objects.update_or_create(
            submission=submission,
            defaults={f'{pool}_headcount': int(optimal[pool])
                      for pool in ('rd', 'commercial', 'operations')})
        return submission

    def with_a_legacy_row(self):
        submission = self.submission()
        DecisionRDInvestment.objects.create(
            submission=submission, team_platform=self.platform,
            feature=self.feature, method='in_house',
            target_level=8, amount=D('5000000'))
        return submission

    def test_a_legacy_row_no_longer_moves_strategic_capability(self):
        # The submission must exist in *both* readings. Creating it alongside
        # the row would change the code path -- a team with no submission at
        # all takes an early default -- and the comparison would then measure
        # submission-existence rather than the R&D amount.
        self.submission()
        before = self.strategic_capability()

        self.with_a_legacy_row()

        self.assertEqual(self.strategic_capability(), before,
                         'R10: spend must not earn capability credit.')

    def test_the_component_is_sensitive_enough_to_detect_a_change(self):
        """Guards the test above: a component pinned at one value proves nothing.

        Strategic capability is multiplied by staffing adequacy, so an
        unstaffed team scores zero no matter what else moves. This asserts the
        fixture is in a state where the score can move at all -- it is not
        zero, and adding a scored action changes it.
        """
        from core.models.decisions import DecisionPlatformDevelopment
        submission = self.submission()
        baseline = self.strategic_capability()
        self.assertGreater(baseline, D('0'),
                           'an unstaffed fixture cannot detect anything')

        DecisionPlatformDevelopment.objects.create(
            submission=submission, platform_generation=self.gen,
            method='in_house', committed_cost=self.gen.development_cost,
            platform_name='Sensitivity', feature_levels={})
        self.assertNotEqual(self.strategic_capability(), baseline,
                            'the component must respond to a scored action, '
                            'or the R&D assertion above is vacuous')

    def coherence_for_team(self):
        """The stored coherence score, through the engine's own entry point."""
        from core.engine.coherence import calculate_coherence
        from core.engine.utils import RoundContext
        from core.models.results_financials import RoundResultCoherence
        RoundResultCoherence.objects.filter(game=self.game).delete()
        context = RoundContext(self.game, 1)
        context.teams = [self.team]
        calculate_coherence(context, skip_rag=True)
        row = RoundResultCoherence.objects.get(
            game=self.game, round_number=1, team=self.team)
        return row.formula_score, dict(row.breakdown or {})

    def test_a_legacy_row_no_longer_moves_coherence(self):
        """Behavioural, not a source scan: the stored score must not move."""
        self.submission()
        before_score, before_breakdown = self.coherence_for_team()
        self.assertNotIn('rd_market_alignment', before_breakdown)

        self.with_a_legacy_row()

        after_score, after_breakdown = self.coherence_for_team()
        self.assertEqual(after_score, before_score,
                         'R10: an R&D row must not move coherence.')
        self.assertNotIn('rd_market_alignment', after_breakdown)

    def test_coherence_no_longer_reads_the_amount(self):
        from core.engine import coherence
        self.assertFalse(hasattr(coherence, '_score_rd_alignment'),
                         'R10 retires the component, not merely its inputs.')
        source = open(coherence.__file__).read()
        self.assertNotIn('rd_investments', source)

    def test_performance_no_longer_reads_the_amount(self):
        from core.engine import performance
        source = open(performance.__file__).read()
        self.assertNotIn('rd_investments', source)
