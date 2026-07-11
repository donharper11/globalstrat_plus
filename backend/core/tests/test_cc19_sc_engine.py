"""
CC-19: SC engine tests — event firing, structured contingency execution,
resilience scoring, determinism. Runs against the real CE scenario.
"""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models.core import Game, Team, Round
from core.models.scenario import Scenario, FirmStarterProfile, EventTemplateDefinition
from core.models.sc_models import Supplier
from core.models.sc_decisions import SourcingDecision, SourcingAllocation, ContingencyPlan
from core.models.sc_state import SupplierState, SCEventInstance, ResilienceScoreHistory
from core.engine.sc_engine import run_sc_engine, _seed


class _Ctx:
    def __init__(self, game, round_number, teams):
        self.game = game
        self.round_number = round_number
        self.teams = teams
        self.log = []


class CC19SCEngineTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_scenario', file='scenarios/consumer_electronics_2026.yaml')
        cls.scenario = Scenario.objects.get(name='Consumer Electronics 2026')
        # Silence probabilistic firing by default so contingency tests are isolated.
        EventTemplateDefinition.objects.filter(
            scenario=cls.scenario, category='supply_chain').update(probability_per_round=0)
        cls.creator = get_user_model().objects.create_user('cc19', password='x')
        profile = FirmStarterProfile.objects.filter(scenario=cls.scenario).first()
        cls.game = Game.objects.create(scenario=cls.scenario, name='CC19 Game', created_by=cls.creator, status='active')
        cls.teamA = Team.objects.create(game=cls.game, name='A', firm_starter_profile=profile,
                                        performance_index=D('100'), cash_on_hand=D('50000000'), total_equity=D('50000000'))
        cls.teamB = Team.objects.create(game=cls.game, name='B', firm_starter_profile=profile,
                                        performance_index=D('100'), cash_on_hand=D('50000000'), total_equity=D('50000000'))
        semis = list(Supplier.objects.filter(scenario=cls.scenario, specialization__contains=['semiconductor']))
        cls.primary, cls.backup = semis[0], semis[1]

    def _source_both(self, rnd):
        for t in (self.teamA, self.teamB):
            SourcingDecision.objects.create(team=t, round=rnd, multi_sourcing_strategy='single_source',
                                            tier_2_3_visibility_investment='none')
            SourcingAllocation.objects.create(team=t, round=rnd, critical_input_category='semiconductor',
                                              supplier=self.primary, allocation_pct=100, payment_terms='', volume_commitment_units=0)

    def test_resilience_scored(self):
        rnd = Round.objects.create(game=self.game, round_number=3, status='open')
        self._source_both(rnd)
        run_sc_engine(_Ctx(self.game, 3, [self.teamA, self.teamB]))
        for t in (self.teamA, self.teamB):
            rs = ResilienceScoreHistory.objects.filter(team=t, round=rnd).first()
            self.assertIsNotNone(rs)
            self.assertGreaterEqual(float(rs.score), 0.0)
            self.assertIn('multi_sourcing', rs.components)
            self.assertIn('geographic_diversity', rs.weights_used or {})

    def test_contingency_reduces_impact(self):
        prev = Round.objects.create(game=self.game, round_number=4, status='processed')
        rnd = Round.objects.create(game=self.game, round_number=5, status='open')
        self._source_both(rnd)
        # Team A has a backup rule to a healthy supplier; Team B does not.
        ContingencyPlan.objects.create(team=self.teamA, round=rnd,
            alt_supplier_activation_rules=[{'input_category': 'semiconductor', 'trigger': 'disruption',
                                            'backup_supplier_id': self.backup.id, 'shift_pct': 50}],
            mode_switch_triggers=[])
        # Carried-forward disruption of the primary (recovery>0 → carries into round 5).
        SupplierState.objects.create(round=prev, supplier=self.primary, capacity_multiplier=D('0.4'),
                                     quality_modifier=D('0'), reliability_modifier=D('0'),
                                     additional_lead_time_days=30, disruption_cost_multiplier=D('1.5'),
                                     recovery_rounds_remaining=2)
        run_sc_engine(_Ctx(self.game, 5, [self.teamA, self.teamB]))
        a = Team.objects.get(pk=self.teamA.pk).cash_on_hand
        b = Team.objects.get(pk=self.teamB.pk).cash_on_hand
        self.assertLess(a, D('50000000'))          # both took a hit
        self.assertLess(b, D('50000000'))
        self.assertGreater(a, b)                    # A's backup rule reduced its loss

    def test_events_fire_and_populate_state(self):
        rnd = Round.objects.create(game=self.game, round_number=6, status='open')
        # Force the Taiwan-earthquake event to fire this round.
        tmpl = EventTemplateDefinition.objects.get(scenario=self.scenario, name__icontains='earthquake')
        EventTemplateDefinition.objects.filter(pk=tmpl.pk).update(probability_per_round=1, earliest_round=1)
        run_sc_engine(_Ctx(self.game, 6, [self.teamA, self.teamB]))
        self.assertTrue(SCEventInstance.objects.filter(round=rnd, event_template=tmpl).exists())
        # tsmc_taiwan is in the earthquake's affected_suppliers → SupplierState created, capacity reduced
        tsmc = Supplier.objects.get(scenario=self.scenario, supplier_id='tsmc_taiwan')
        st = SupplierState.objects.filter(round=rnd, supplier=tsmc).first()
        self.assertIsNotNone(st)
        self.assertLess(float(st.capacity_multiplier), 1.0)
        self.assertGreater(st.recovery_rounds_remaining, 0)

    def test_seed_deterministic(self):
        self.assertEqual(_seed(1, 2, 3), _seed(1, 2, 3))
        self.assertNotEqual(_seed(1, 2, 3), _seed(1, 3, 3))
