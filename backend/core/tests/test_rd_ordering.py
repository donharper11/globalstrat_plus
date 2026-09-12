"""A4 cohort: R&D outcomes must not depend on submitted row order.

The cohort question outlived the decision it was written against. R10 retired
feature-level R&D investment outright, so there is no longer an accepted
payload whose *outcome* could depend on row order: every row is refused on
every supported write surface (V2-053).

What the cohort asked is still a live question, one level earlier. **The
refusal itself must not depend on the order the rows arrive in.** An
order-sensitive refusal would mean two teams submitting the same decision,
typed in a different sequence, being told different things — and, worse, would
be the signature of a rule that reads only the first row it happens to see.

So these tests are repaired to the rule now in force rather than to the rule
they were written against: both orderings are refused, refused *identically*,
and neither writes a row.
"""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models.core import Game, Round, Team
from core.models.decisions import DecisionRDInvestment
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

    def _stored_capability(self):
        """Every capability row the retired decision used to be able to move."""
        levels = list(TeamPlatformFeatureLevel.objects.order_by(
            'team_platform_id', 'feature_id').values_list(
                'team_platform_id', 'feature_id', 'current_level'))
        pending = list(PendingFeatureGain.objects.order_by(
            'team_platform_id', 'feature_id').values_list(
                'team_platform_id', 'feature_id', 'gain_amount', 'applies_round'))
        return levels, pending

    def _refuse(self, payload):
        """Submit a payload that the rule refuses; return the refusal."""
        serializer = DecisionSubmissionSerializer(data=payload)
        self.assertFalse(
            serializer.is_valid(),
            'a feature-level R&D payload was accepted; R10 retired it')
        self.assertIn('rd_investments', serializer.errors)
        return str(serializer.errors['rd_investments'])

    def test_forward_and_reverse_distinct_feature_payloads_match(self):
        """Distinct features, opposite order: the same refusal, and no writes."""
        before = self._stored_capability()

        forward = self._refuse(self._payload(self.platforms[0], self.features))
        reverse = self._refuse(
            self._payload(self.platforms[1], list(reversed(self.features))))

        self.assertEqual(forward, reverse)
        # The refusal has to be actionable, or it is a bug report addressed to
        # the team: it names the route that replaced the retired decision.
        self.assertIn('new platform', forward.lower())
        self.assertEqual(DecisionRDInvestment.objects.count(), 0,
                         'a refused R&D payload persisted a row')
        self.assertEqual(self._stored_capability(), before,
                         'a refused R&D payload moved stored capability')

    def test_reversed_duplicate_target_payloads_are_uniformly_rejected(self):
        """Two rows on one feature: still refused the same way either way round.

        This is the case the cohort was built for. The duplicate rule is a
        cross-row rule, so it is the one most exposed to reading a payload in
        the order it arrived rather than as a set.
        """
        feature = self.features[0]
        rows = [
            {'team_platform': self.platforms[0].id, 'feature': feature.id,
             'method': 'license', 'amount': '0', 'target_level': 2,
             'calculated_cost': '100000.00'},
            {'team_platform': self.platforms[0].id, 'feature': feature.id,
             'method': 'in_house', 'amount': '750000.00',
             'calculated_cost': '750000.00'},
        ]
        before = self._stored_capability()

        messages = [
            self._refuse({'team': self.teams[0].id, 'round': self.round.id,
                          'rd_investments': ordered})
            for ordered in (rows, list(reversed(rows)))
        ]

        self.assertEqual(messages[0], messages[1])
        self.assertEqual(DecisionRDInvestment.objects.count(), 0)
        self.assertEqual(self._stored_capability(), before)
