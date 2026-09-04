"""Ruling 1: a ready platform is frozen.

No features added, no levels changed. Building a new platform, and re-basing a
product onto it, is the only route to a better product.

Why the rule matters more than it looks: before this, a team could hold one
platform all game and buy its way up the feature curve, so the platform
decision was a formality and the generation ladder decided nothing. Freezing it
makes *what to build, and when* the decision the round is actually about -- and
makes Stage 4's re-basing load-bearing rather than a convenience.

The three surfaces are tested separately because they fail independently: a
write can accept what the engine refuses, and an engine that ignores a row is
not the same as one that refuses it.
"""
from decimal import Decimal as D

from django.test import TestCase

from core.models import DecisionSubmission, Round
from core.models.decisions import DecisionRDInvestment
from core.models.scenario import (FeatureDefinition, MarketDefinition,
                                  PlatformGenerationDefinition)
from core.models.team_state import (PendingFeatureGain, TeamPlatform,
                                    TeamPlatformFeatureLevel)
from core.tests.test_operator_concurrency import build_minimal_game


class FreezeFixture(TestCase):

    def setUp(self):
        self.game, self.teams = build_minimal_game(f'freeze-{id(self)}')
        self.team = self.teams[0]
        self.scenario = self.game.scenario
        self.market = MarketDefinition.objects.filter(
            scenario=self.scenario).first()
        self.gen = self.generation(1)
        self.gen2 = self.generation(2)
        self.feature = FeatureDefinition.objects.create(
            scenario=self.scenario, code='FRZ', name='Frozen feature',
            description='d', layer='platform', category='core',
            cost_curve_type='linear', cost_base=D('1000'),
            default_value=D('3'), max_value=D('10'))
        # Different generations: one non-retired platform per generation, or
        # the duplicate-generation precondition refuses first and proves
        # nothing about the freeze.
        self.ready = self.platform('Ready Platform', 'active', self.gen)
        self.building = self.platform('Still Building', 'in_development',
                                      self.gen2)
        # The feature must be reachable on the ready platform's generation, or
        # the availability check refuses before the freeze check is consulted.
        from core.models.scenario import PlatformFeatureCeiling
        for g in (self.gen, self.gen2):
            PlatformFeatureCeiling.objects.create(
                platform_generation=g, feature=self.feature,
                ceiling_value=D('10'), starting_value=D('3'))
        TeamPlatformFeatureLevel.objects.create(
            team_platform=self.ready, feature=self.feature,
            current_level=D('3'))
        self.round, _ = Round.objects.get_or_create(
            game=self.game, round_number=1, defaults={'status': 'open'})

    def generation(self, order):
        return PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name=f'Gen {order}', description='d',
            generation_order=order, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)

    def platform(self, name, status, generation):
        return TeamPlatform.objects.create(
            team=self.team, platform_generation=generation, name=name,
            status=status, development_method='in_house',
            development_started_round=0, funded_round=0,
            development_rounds_remaining=0 if status == 'active' else 1)

    def student_client(self):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        user = User.objects.create(
            username=f'frz-{id(self)}-{User.objects.count()}',
            role='student', password_hash='x')
        course = Course.objects.create(
            course_code=f'FRZ{id(self) % 100000}{Course.objects.count()}',
            course_name='Freeze',
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

    def rd_row(self, platform):
        return {'team_platform': platform.id, 'feature': self.feature.id,
                'method': 'in_house', 'target_level': 8, 'amount': '500000'}


class FreezeWriteSurfaceTests(FreezeFixture):
    """Both supported writes refuse, so a team is told at submission."""

    def per_type(self, rows):
        return self.student_client().patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}'
            f'/decisions/round/1/rd/', rows, format='json')

    def whole_submission(self, rows):
        return self.student_client().post(
            f'/api/games/{self.game.id}/teams/{self.team.id}'
            f'/decisions/round/1/', {'rd_investments': rows}, format='json')

    def test_the_per_type_write_refuses_an_upgrade_to_a_ready_platform(self):
        response = self.per_type([self.rd_row(self.ready)])

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('frozen', str(response.data))

    def test_the_whole_submission_write_refuses_it_too(self):
        response = self.whole_submission([self.rd_row(self.ready)])

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('frozen', str(response.data))

    def test_a_refused_write_persists_nothing(self):
        self.per_type([self.rd_row(self.ready)])
        self.whole_submission([self.rd_row(self.ready)])

        self.assertEqual(DecisionRDInvestment.objects.count(), 0)

    def test_the_refusal_says_what_to_do_instead(self):
        """A rule a team cannot act on is a bug report addressed to them."""
        response = self.per_type([self.rd_row(self.ready)])

        message = str(response.data)
        self.assertIn('re-base', message.lower())
        self.assertIn('new platform', message.lower())

    def test_a_platform_still_in_development_is_not_frozen_by_this_rule(self):
        """The rule is about *ready* platforms; it must not over-reach.

        Its feature set is still fixed at request time by the cap and cost
        checks -- this only proves the freeze itself does not fire early.
        """
        from core.services.rd_costs import frozen_platform_problem
        self.assertIsNone(frozen_platform_problem(self.building))
        self.assertIsNotNone(frozen_platform_problem(self.ready))


class FreezeEngineBoundaryTests(FreezeFixture):
    """A stored row is refused before competitive mutation, not ignored."""

    def lock_everyone(self):
        Round.objects.filter(pk=self.round.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=self.round, defaults={'status': 'locked'})

    def smuggle_in(self, platform):
        """A row that never passed a write surface -- restore, import, shell."""
        self.lock_everyone()
        submission = DecisionSubmission.objects.get(
            team=self.team, round=self.round)
        return DecisionRDInvestment.objects.create(
            submission=submission, team_platform=platform,
            feature=self.feature, method='in_house',
            target_level=8, amount=D('500000'))

    def test_phase_1_refuses_a_stored_upgrade_to_a_ready_platform(self):
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        row = self.smuggle_in(self.ready)

        with self.assertRaises(InvalidPersistedDecisionError) as caught:
            process_round(self.game.id)

        message = str(caught.exception)
        self.assertIn('already ready', message)
        self.assertIn(str(row.pk), message)
        self.assertIn('Ready Platform', message)

    def test_nothing_competitive_is_written_when_it_refuses(self):
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        from core.models.results_financials import RoundResultFinancials
        self.smuggle_in(self.ready)

        with self.assertRaises(InvalidPersistedDecisionError):
            process_round(self.game.id)

        self.assertEqual(
            RoundResultFinancials.objects.filter(game=self.game).count(), 0)

    def test_the_stored_level_is_unchanged_by_the_refused_round(self):
        from core.engine.advance_round import (InvalidPersistedDecisionError,
                                               process_round)
        self.smuggle_in(self.ready)

        with self.assertRaises(InvalidPersistedDecisionError):
            process_round(self.game.id)

        level = TeamPlatformFeatureLevel.objects.get(
            team_platform=self.ready, feature=self.feature)
        self.assertEqual(level.current_level, D('3'))

    def test_a_round_with_no_such_row_still_resolves(self):
        """The control: the precondition must not refuse a healthy round."""
        from core.engine.advance_round import process_round
        from core.models.results_financials import RoundResultFinancials
        self.lock_everyone()

        process_round(self.game.id)

        self.assertGreater(
            RoundResultFinancials.objects.filter(game=self.game).count(), 0)


class UpgradePathRetiredTests(FreezeFixture):
    """The mechanic is gone, not merely gated."""

    def test_the_feature_investment_processor_no_longer_exists(self):
        from core.engine import rd_processing
        self.assertFalse(
            hasattr(rd_processing, '_process_feature_investments'),
            'Ruling 1 retires the upgrade path. A gated-but-present '
            'implementation is the thing that comes back.')

    def test_no_pending_feature_gain_is_created_by_a_resolved_round(self):
        """Feature time lags retire with the path that created them."""
        from core.engine.advance_round import process_round
        Round.objects.filter(pk=self.round.pk).update(status='closed')
        for team in self.teams:
            DecisionSubmission.objects.update_or_create(
                team=team, round=self.round, defaults={'status': 'locked'})

        process_round(self.game.id)

        self.assertEqual(PendingFeatureGain.objects.count(), 0)
