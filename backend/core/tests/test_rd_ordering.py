"""A4 cohort: R&D outcomes must not depend on submitted row order."""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.engine.rd_processing import process_rd
from core.models.core import Game, Round, Team
from core.models.scenario import FirmStarterProfile, PlatformFeatureCeiling, Scenario
from core.models.team_state import PendingFeatureGain, TeamPlatform, TeamPlatformFeatureLevel
from core.serializers.decisions import DecisionSubmissionSerializer


class RDOrderingCohortTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_scenario', file='scenarios/consumer_electronics_2026.yaml')
        cls.scenario = Scenario.objects.get(name='Consumer Electronics 2026')
        cls.user = get_user_model().objects.create_user('rd-order', password='x')
        cls.profile = FirmStarterProfile.objects.filter(
            scenario=cls.scenario).order_by('id').first()

    def setUp(self):
        self.game = Game.objects.create(
            scenario=self.scenario, name='A4 R&D ordering cohort',
            created_by=self.user, status='active', current_round=1)
        self.round = Round.objects.create(game=self.game, round_number=1, status='open')
        generation = PlatformFeatureCeiling.objects.filter(
            platform_generation__scenario=self.scenario,
            ceiling_value__gt=1,
        ).values_list('platform_generation', flat=True).first()
        ceilings = list(PlatformFeatureCeiling.objects.filter(
            platform_generation_id=generation,
            ceiling_value__gt=1,
        ).select_related('feature').order_by('feature_id')[:3])
        self.features = [ceiling.feature for ceiling in ceilings]
        self.teams = []
        self.platforms = []
        for label in ('forward', 'reverse'):
            team = Team.objects.create(
                game=self.game, name=label, firm_starter_profile=self.profile,
                cash_on_hand=D('50000000'), total_equity=D('50000000'),
                performance_index=D('55'))
            platform = TeamPlatform.objects.create(
                team=team, platform_generation_id=generation,
                name=f'{label} platform', status='active')
            for feature in self.features:
                TeamPlatformFeatureLevel.objects.create(
                    team_platform=platform, feature=feature,
                    current_level=feature.default_value)
            self.teams.append(team)
            self.platforms.append(platform)

    def _payload(self, platform, features):
        return {
            'team': platform.team_id,
            'round': self.round.id,
            'rd_investments': [{
                'team_platform': platform.id,
                'feature': feature.id,
                'method': 'in_house',
                'amount': '750000.00',
                'calculated_cost': '750000.00',
            } for feature in features],
        }

    def test_forward_and_reverse_distinct_feature_payloads_match(self):
        payloads = (
            self._payload(self.platforms[0], self.features),
            self._payload(self.platforms[1], reversed(self.features)),
        )
        for payload in payloads:
            serializer = DecisionSubmissionSerializer(data=payload)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            serializer.save()

        context = type('Context', (), {
            'game': self.game, 'scenario': self.scenario, 'round_number': 1,
            'teams': self.teams, 'org_modifiers': {}, 'log': [],
        })()
        process_rd(context)

        def outcome(platform):
            levels = list(TeamPlatformFeatureLevel.objects.filter(
                team_platform=platform).order_by('feature_id').values_list(
                    'feature_id', 'current_level'))
            pending = list(PendingFeatureGain.objects.filter(
                team_platform=platform).order_by('feature_id').values_list(
                    'feature_id', 'gain_amount', 'applies_round'))
            return levels, pending

        self.assertEqual(outcome(self.platforms[0]), outcome(self.platforms[1]))

    def test_reversed_duplicate_target_payloads_are_uniformly_rejected(self):
        feature = self.features[0]
        rows = [
            {'team_platform': self.platforms[0].id, 'feature': feature.id,
             'method': 'license', 'amount': '0', 'target_level': 2,
             'calculated_cost': '100000.00'},
            {'team_platform': self.platforms[0].id, 'feature': feature.id,
             'method': 'in_house', 'amount': '750000.00',
             'calculated_cost': '750000.00'},
        ]
        messages = []
        for ordered_rows in (rows, list(reversed(rows))):
            payload = {'team': self.teams[0].id, 'round': self.round.id,
                       'rd_investments': ordered_rows}
            serializer = DecisionSubmissionSerializer(data=payload)
            self.assertFalse(serializer.is_valid())
            messages.append(str(serializer.errors['rd_investments'][0]))
        self.assertEqual(messages[0], messages[1])
        self.assertIn('Only one R&D investment', messages[0])
