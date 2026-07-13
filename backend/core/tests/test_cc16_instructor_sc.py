"""
CC-16 — Instructor Supply-Chain Panel backend tests.

Covers: instructor event injection actually disrupts the next round advance;
the per-team panel aggregation; the SC event catalog; and instructor-only
tenancy (students are forbidden).
"""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from core.models.core import Game, Team, Round
from core.models.scenario import (
    Scenario, FirmStarterProfile, EventTemplateDefinition,
)
from core.models.sc_models import Supplier
from core.models.sc_decisions import SourcingDecision, SourcingAllocation
from core.models.sc_state import SupplierState, SCEventInstance, ResilienceScoreHistory
from core.models import User as CoreUser
from core.views.instructor_sc import (
    InstructorSCPanelView, InstructorSCEventCatalogView, InstructorInjectSCEventView,
)


class CC16InstructorSCTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_scenario', file='scenarios/consumer_electronics_2026.yaml')
        cls.scenario = Scenario.objects.get(name='Consumer Electronics 2026')
        EventTemplateDefinition.objects.filter(
            scenario=cls.scenario, category='supply_chain').update(probability_per_round=0)

        cls.instructor = CoreUser.objects.create(username='cc16_inst', password_hash='x', role='instructor')
        cls.student = CoreUser.objects.create(username='cc16_stu', password_hash='x', role='student')
        cls.creator = get_user_model().objects.create_user('cc16_creator', password='x')

        profile = FirmStarterProfile.objects.filter(scenario=cls.scenario).first()
        cls.game = Game.objects.create(scenario=cls.scenario, name='CC16 Game',
                                       created_by=cls.creator, status='active', current_round=1)
        cls.tsmc = Supplier.objects.get(scenario=cls.scenario, supplier_id='tsmc_taiwan')
        cls.samsung = Supplier.objects.get(scenario=cls.scenario, supplier_id='samsung_foundry_korea')
        cls.team = Team.objects.create(game=cls.game, name='Alpha', firm_starter_profile=profile,
                                       performance_index=D('100'), cash_on_hand=D('50000000'),
                                       total_equity=D('50000000'))
        cls.round1 = Round.objects.create(game=cls.game, round_number=1, status='open')
        # A sourcing decision so the panel + capacity logic have something to read.
        SourcingDecision.objects.create(team=cls.team, round=cls.round1,
                                        multi_sourcing_strategy='single_source',
                                        tier_2_3_visibility_investment='none')
        SourcingAllocation.objects.create(team=cls.team, round=cls.round1,
                                          critical_input_category='semiconductor',
                                          supplier=cls.tsmc, allocation_pct=100,
                                          payment_terms='', volume_commitment_units=0)
        cls.quake = EventTemplateDefinition.objects.get(
            scenario=cls.scenario, name='Taiwan Earthquake — Semiconductor Capacity Shock')
        cls.factory = APIRequestFactory()

    def _call(self, view, method, user, data=None):
        req = getattr(self.factory, method)('/x/', data or {}, format='json',
                                            HTTP_X_USER_ID=str(user.user_id))
        return view.as_view()(req, game_id=self.game.id)

    # -- injection actually disrupts the next round ---------------------
    def test_inject_creates_pending_then_fires_on_advance(self):
        resp = self._call(InstructorInjectSCEventView, 'post', self.instructor,
                          {'event_template_id': self.quake.id})
        self.assertEqual(resp.status_code, 201, resp.data)
        inst = SCEventInstance.objects.get(id=resp.data['sc_event_instance_id'])
        self.assertTrue(inst.fired_by_instructor)
        self.assertTrue(inst.resolution_data.get('pending'))
        # No supplier disruption yet — it's only queued.
        self.assertFalse(SupplierState.objects.filter(round=self.round1, supplier=self.tsmc).exists())

        # Advance the round via the real SC engine step.
        from core.engine.sc_engine import run_sc_state

        class _Ctx:
            def __init__(s):
                s.game = self.game; s.round_number = 1; s.teams = [self.team]
                s.scenario = self.scenario; s.markets = {}; s.log = []
        run_sc_state(_Ctx())

        # Now tsmc is disrupted (40% capacity reduction => 0.6 multiplier) and the
        # instructor event is marked applied.
        st = SupplierState.objects.get(round=self.round1, supplier=self.tsmc)
        self.assertEqual(float(st.capacity_multiplier), 0.6)
        inst.refresh_from_db()
        self.assertFalse(inst.resolution_data.get('pending'))
        self.assertTrue(inst.resolution_data.get('applied'))

    def test_panel_shows_pending_injection(self):
        # Inject, then the panel must confirm the queued (not-yet-fired) event.
        r = self._call(InstructorInjectSCEventView, 'post', self.instructor,
                       {'event_template_id': self.quake.id})
        self.assertEqual(r.status_code, 201, r.data)
        resp = self._call(InstructorSCPanelView, 'get', self.instructor)
        self.assertEqual(len(resp.data['pending_injections']), 1)
        self.assertTrue(resp.data['pending_injections'][0]['event'].startswith('Taiwan'))
        self.assertEqual(resp.data['pending_injections'][0]['fires_on_round'], 1)
        # Not counted as an active disruption yet (hasn't fired).
        self.assertEqual(resp.data['active_disruptions'], [])

    # -- panel aggregation ---------------------------------------------
    def test_panel_returns_per_team_snapshot(self):
        ResilienceScoreHistory.objects.create(
            team=self.team, round=self.round1, score=D('42.5'),
            components={'multi_sourcing': 0.0, 'geographic_diversity': 0.0},
            weights_used={'multi_sourcing': 0.3}, disruption_impact={'capacity_factor': 1.0})
        resp = self._call(InstructorSCPanelView, 'get', self.instructor)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['round_number'], 1)
        team = resp.data['teams'][0]
        self.assertEqual(team['team_name'], 'Alpha')
        self.assertEqual(team['multi_sourcing_strategy'], 'single_source')
        self.assertIn('semiconductor', team['single_source_flags'])   # 100% one supplier
        self.assertEqual(team['resilience']['score'], 42.5)
        self.assertEqual(team['sourcing'][0]['country'], 'TW')

    def test_catalog_lists_sc_events_with_effect_summary(self):
        resp = self._call(InstructorSCEventCatalogView, 'get', self.instructor)
        self.assertEqual(resp.status_code, 200)
        names = [e['name'] for e in resp.data['events']]
        self.assertIn('Taiwan Earthquake — Semiconductor Capacity Shock', names)
        quake = next(e for e in resp.data['events'] if e['name'].startswith('Taiwan'))
        self.assertIn('capacity', quake['effect_summary'])

    # -- tenancy --------------------------------------------------------
    def test_student_forbidden(self):
        r1 = self._call(InstructorSCPanelView, 'get', self.student)
        self.assertEqual(r1.status_code, 403)
        r2 = self._call(InstructorInjectSCEventView, 'post', self.student,
                        {'event_template_id': self.quake.id})
        self.assertEqual(r2.status_code, 403)
