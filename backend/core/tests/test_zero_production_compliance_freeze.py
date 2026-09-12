"""A solvent, competently-playing team must not lose a whole round to a
compliance freeze it had no available decision to prevent.

The defect these tests pin, stated as the mechanism rather than the symptom:

`compliance_engine._trigger_applies` fires the `customs_documentation` regime
whenever a team has no `CustomsClassificationDecision` for a (round, market).
But `logistics.customs_classification` is progressive-disclosure gated to
round 5 (`core.utils.disclosure.DEFAULT_UNLOCK_ROUNDS`), and
`CustomsClassificationDecisionWriteSerializer` *refuses* the field before then.
The frontend agrees: `LogisticsPage.js` disables the control and strips customs
rows from the payload below its own `UNLOCK.customs_classification = 5`.

So in rounds 1-4 the engine punished a team for not filing a document the rules
forbade it to file. The regime's `enforcing_market` is `all` and its
`detention_consequence` is a one-round market-access hold, so for a firm whose
starter profile puts it in exactly one market -- which is every firm in the
shipped consumer-electronics scenario -- a single draw at 0.12 removed the firm
from its only market for the entire round: no demand rows, no revenue rows, no
`RoundResultProductMarket` row at all, revenue 0.00 against unchanged fixed
costs, and then the V2-022 commercial-inactivity controls on top.

That is not enforcement, it is a lottery with no counter-decision, and
`compliance_engine`'s own stated convention already rejects it: a trigger with
no determinable signal is *skipped, not faked*. A team forbidden to file the
document presents no signal to read.

The repair is deliberately narrow. It does not weaken the regime, and it does
not touch the V2-021/V2-022 inactivity classification: once the field unlocks,
the regime fires exactly as before, and an instructor who unlocks the field
early through `ClassProgressiveDisclosureOverride` re-arms it early too.
"""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models.core import Game, Team, Round
from core.models.decisions import DecisionSubmission, DecisionMarketing
from core.models.overrides import ClassProgressiveDisclosureOverride
from core.models.results import RoundResultAdoption
from core.models.scenario import (
    Scenario, MarketDefinition, SegmentDefinition, FirmStarterProfile,
    PlatformGenerationDefinition,
)
from core.models.sc_models import ComplianceRegime
from core.models.sc_state import ComplianceEnforcementEvent
from core.models.team_state import TeamPlatform, TeamProduct

from core.engine.compliance_engine import enforce_compliance, _trigger_applies
from core.engine.revenue import calculate_revenue
from core.engine.performance import (
    is_commercially_inactive, material_revenue_floor,
)
from core.serializers.sc_serializers import (
    CustomsClassificationDecisionWriteSerializer,
)


CUSTOMS_FIELD_PATH = 'logistics.customs_classification'


class _Ctx:
    """The minimal context `enforce_compliance` and `calculate_revenue` read."""

    def __init__(self, game, round_number, teams, scenario):
        self.game = game
        self.round_number = round_number
        self.teams = teams
        self.scenario = scenario
        self.markets = {}
        self.log = []


class CustomsFreezeBeforeUnlockTests(TestCase):
    """Rounds 1-4: the document cannot be filed, so the regime must not fire."""

    @classmethod
    def setUpTestData(cls):
        call_command('load_scenario',
                     file='scenarios/consumer_electronics_2026.yaml')
        cls.scenario = Scenario.objects.get(name='Consumer Electronics 2026')
        cls.creator = get_user_model().objects.create_user('zp', password='x')
        cls.na = MarketDefinition.objects.get(scenario=cls.scenario, code='NA')
        cls.segment = SegmentDefinition.objects.filter(
            scenario=cls.scenario, market=cls.na, segment_type='customer',
        ).first()
        cls.customs = ComplianceRegime.objects.get(
            scenario=cls.scenario, regime_id='customs_documentation')
        profile = FirmStarterProfile.objects.filter(scenario=cls.scenario).first()
        cls.game = Game.objects.create(
            scenario=cls.scenario, name='zero-production', created_by=cls.creator,
            status='active')
        # One firm, one market -- the shipped consumer-electronics shape, where
        # a single team-market freeze is a total commercial blackout.
        cls.team = Team.objects.create(
            game=cls.game, name='Solvent', firm_starter_profile=profile,
            performance_index=D('50'), cash_on_hand=D('40000000'),
            total_equity=D('40000000'))
        gen = PlatformGenerationDefinition.objects.filter(
            scenario=cls.scenario).order_by('generation_order').first()
        platform = TeamPlatform.objects.create(
            team=cls.team, platform_generation=gen, status='active')
        cls.product = TeamProduct.objects.create(
            team=cls.team, team_platform=platform, name='Handset',
            positioning='mainstream', created_round=1)

    def setUp(self):
        # Force the draw so the test measures the *trigger*, not the 0.12 dice.
        # Without this a green result could just be a lucky roll.
        self.customs.baseline_enforcement_probability_per_round = D('1.0')
        self.customs.save(
            update_fields=['baseline_enforcement_probability_per_round'])

    def _round(self, n):
        return Round.objects.create(
            game=self.game, round_number=n, status='open')

    # -- the defect -------------------------------------------------------

    def test_customs_trigger_is_not_evaluable_before_the_field_unlocks(self):
        """RED without the repair: returns (True, False, 'no customs ...').

        `logistics.customs_classification` unlocks at round 5, so in round 1
        the absence of the document carries no information about the team's
        conduct. The module's own rule for that case is `return None` --
        skip, don't fake.
        """
        rnd = self._round(1)
        verdict = _trigger_applies(self.customs, self.team, rnd, self.na)
        self.assertIsNone(
            verdict,
            'the customs trigger must be unevaluable while the team is '
            'forbidden to file the document; got %r' % (verdict,))

    def test_round_one_enforcement_cannot_freeze_a_single_market_firm(self):
        """RED without the repair: the firm's only market is frozen in round 1.

        This is the whole defect in one assertion. The probability is pinned at
        1.0, so before the repair this freeze is certain, and in the shipped
        replay it was a 12% draw per team per round.
        """
        rnd = self._round(1)
        ctx = _Ctx(self.game, 1, [self.team], self.scenario)

        enforce_compliance(ctx)

        self.assertNotIn(
            (self.team.id, self.na.id), ctx.compliance_freezes,
            'a team that cannot file a customs classification must not be '
            'frozen out of its only market for failing to file one')
        self.assertFalse(
            ComplianceEnforcementEvent.objects.filter(
                team=self.team, round=rnd, regime=self.customs).exists(),
            'no customs enforcement event may be recorded before the field '
            'the team would have used to comply has unlocked')

    def test_every_locked_round_is_covered_not_just_round_one(self):
        """Rounds 1-4 are all inside the gate; the replay lost rounds 1, 2 and 4."""
        for round_number in (1, 2, 3, 4):
            with self.subTest(round_number=round_number):
                rnd = self._round(round_number)
                ctx = _Ctx(self.game, round_number, [self.team], self.scenario)
                enforce_compliance(ctx)
                self.assertNotIn((self.team.id, self.na.id),
                                 ctx.compliance_freezes)
                Round.objects.filter(pk=rnd.pk).delete()

    # -- why it could not be avoided --------------------------------------

    def test_a_team_cannot_file_the_customs_document_before_round_five(self):
        """The other half of the defect: the decision is refused, not merely absent.

        Passes before and after the repair. It is here because the repair is
        only correct *because* of this: the engine was reading the absence of
        a row the write path refuses to create.
        """
        locked = self._round(1)
        serializer = CustomsClassificationDecisionWriteSerializer(data={
            'team': self.team.pk, 'round': locked.pk,
            'destination_market': self.na.pk, 'classification': 'general_trade',
        })
        self.assertFalse(
            serializer.is_valid(),
            'round 1 must refuse a customs classification, or the engine was '
            'right to expect one')
        self.assertIn(CUSTOMS_FIELD_PATH, str(serializer.errors))

        unlocked = self._round(5)
        serializer = CustomsClassificationDecisionWriteSerializer(data={
            'team': self.team.pk, 'round': unlocked.pk,
            'destination_market': self.na.pk, 'classification': 'general_trade',
        })
        self.assertTrue(
            serializer.is_valid(),
            'round 5 must accept it: %r' % (serializer.errors,))

    # -- the repair must stay narrow --------------------------------------

    def test_the_regime_still_fires_once_the_field_is_unlocked(self):
        """Guards against over-fixing. From round 5 the omission is a real choice."""
        rnd = self._round(5)
        ctx = _Ctx(self.game, 5, [self.team], self.scenario)

        enforce_compliance(ctx)

        self.assertIn(
            (self.team.id, self.na.id), ctx.compliance_freezes,
            'a team that could have filed the document and did not must still '
            'be enforced against')
        event = ComplianceEnforcementEvent.objects.filter(
            team=self.team, round=rnd, regime=self.customs).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.cost_usd, D('120000'))
        self.assertEqual(event.freeze_until_round, 5)

    def test_filing_the_document_prevents_the_freeze_once_unlocked(self):
        """The counter-decision works, which is what makes round 5+ legitimate."""
        from core.models.sc_decisions import CustomsClassificationDecision

        rnd = self._round(5)
        CustomsClassificationDecision.objects.create(
            team=self.team, round=rnd, destination_market=self.na,
            classification='general_trade')
        ctx = _Ctx(self.game, 5, [self.team], self.scenario)

        enforce_compliance(ctx)

        self.assertNotIn((self.team.id, self.na.id), ctx.compliance_freezes)

    def test_an_instructor_override_rearms_the_regime_early(self):
        """The gate is the *effective* unlock round, not the hardcoded default."""
        ClassProgressiveDisclosureOverride.objects.create(
            game=self.game, field_path=CUSTOMS_FIELD_PATH,
            override_unlock_round=1, created_by=self.creator,
            reason='unit test: field unlocked from round 1')
        rnd = self._round(1)
        ctx = _Ctx(self.game, 1, [self.team], self.scenario)

        enforce_compliance(ctx)

        self.assertIn(
            (self.team.id, self.na.id), ctx.compliance_freezes,
            'if the class unlocked the field in round 1 then the team could '
            'have filed, and the regime must fire')
        self.assertTrue(ComplianceEnforcementEvent.objects.filter(
            team=self.team, round=rnd, regime=self.customs).exists())

    # -- the consequence this defect had ----------------------------------

    def test_a_single_market_freeze_costs_the_entire_round(self):
        """Documents the blast radius: not a shipment hold, a whole lost round.

        Asserts today's behaviour on both sides of the repair. It is the reason
        the trigger mattered: one freeze on a one-market firm produces
        `units_produced = units_sold = revenue = 0` with no product row at all,
        and then the V2-022 classification calls that firm inactive.
        """
        rnd = self._round(6)
        sub = DecisionSubmission.objects.create(
            team=self.team, round=rnd, status='locked')
        DecisionMarketing.objects.create(
            submission=sub, team_product=self.product, market=self.na,
            retail_price=D('420'), promotion_budget=D('300000'),
            campaign_focus_feature_ids=[], channel_digital_pct=D('0.4'),
            channel_traditional_pct=D('0.3'), channel_trade_pct=D('0.3'),
            distribution_strategy='hybrid', distribution_investment=D('200000'),
            sales_team_count=10, demand_estimate=30000,
            production_volume=20000, production_source_market=self.na)
        RoundResultAdoption.objects.create(
            game=self.game, round_number=6, team=self.team, market=self.na,
            best_product=self.product, segment=self.segment,
            fit_score=D('0.5'), adjusted_fit_score=D('0.5'),
            market_readiness_pct=D('1'), adoption_pool=D('20000'),
            team_attractiveness=D('1'), team_share_pct=D('1'),
            new_adopters=D('20000'), cumulative_adopters=D('20000'))

        ctx = _Ctx(self.game, 6, [self.team], self.scenario)
        ctx.compliance_freezes = {(self.team.id, self.na.id)}
        calculate_revenue(ctx)

        # No revenue row at all -- which is why `financials.py` writes no
        # RoundResultProductMarket, and why the replay reported
        # `units_produced = 0` as a sum over an empty set.
        self.assertEqual(
            ctx.revenue, {},
            'a frozen one-market firm books no product-market row at all')

        # And the firm is then classified commercially inactive against a
        # cohort floor set by teams that were not frozen.
        floor = material_revenue_floor([D('0'), D('20000000'), D('15000000')])
        self.assertTrue(is_commercially_inactive(D('0'), floor))
