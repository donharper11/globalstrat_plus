"""
CC-17 — SC + compliance Phase-2 narrative tests (deterministic; no live LLM/RAG).

Covers the prompt builders (right facts + guardrail + RAG grounding), the store
functions (LLM content when present, factual template fallback when absent), and
the no-API-key fallback path.
"""
from decimal import Decimal as D
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models.core import Game, Team, Round
from core.models.scenario import Scenario, MarketDefinition, FirmStarterProfile, EventTemplateDefinition
from core.models.sc_models import ComplianceRegime
from core.models.sc_state import SCEventInstance, ComplianceEnforcementEvent
from core.engine import narratives as N


class CC17NarrativeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_scenario', file='scenarios/consumer_electronics_2026.yaml')
        cls.scenario = Scenario.objects.get(name='Consumer Electronics 2026')
        cls.creator = get_user_model().objects.create_user('cc17', password='x')
        cls.na = MarketDefinition.objects.get(scenario=cls.scenario, code='NA')
        cls.quake = EventTemplateDefinition.objects.get(
            scenario=cls.scenario, name='Taiwan Earthquake — Semiconductor Capacity Shock')
        cls.uflpa = ComplianceRegime.objects.get(scenario=cls.scenario, regime_id='uflpa')
        profile = FirmStarterProfile.objects.filter(scenario=cls.scenario).first()
        cls.game = Game.objects.create(scenario=cls.scenario, name='CC17', created_by=cls.creator,
                                       status='active', current_round=1)
        cls.team = Team.objects.create(game=cls.game, name='Nimbus', firm_starter_profile=profile,
                                       performance_index=D('100'), cash_on_hand=D('50000000'),
                                       total_equity=D('50000000'))
        cls.round = Round.objects.create(game=cls.game, round_number=1, status='open')
        cls.sc_event = SCEventInstance.objects.create(
            round=cls.round, event_template=cls.quake, affects_all_teams=True, resolution_data={})
        cls.comp_event = ComplianceEnforcementEvent.objects.create(
            team=cls.team, round=cls.round, regime=cls.uflpa, market=cls.na,
            cost_usd=D('500000'), freeze_until_round=2, reputation_impact=D('1.0'),
            triggered_by='xinjiang exposure 100% > 5%')

    # -- prompt builders -------------------------------------------------
    def test_sc_event_prompt_has_facts_grounding_and_guardrail(self):
        with patch.object(N, '_rag_snippet', return_value='REF-EXCERPT-XYZ'):
            calls = N._build_sc_event_calls(self.game, self.round)
        self.assertEqual(len(calls), 1)
        c = calls[0]
        self.assertEqual(c['id'], f'sc_event_{self.sc_event.id}')
        self.assertIn('Taiwan Earthquake', c['prompt'])
        self.assertIn('Capacity reduction: 40%', c['prompt'])      # from sc_effects
        self.assertIn('Taiwan Semiconductor Manufacturing Company', c['prompt'])  # affected supplier name
        self.assertIn('REF-EXCERPT-XYZ', c['prompt'])              # RAG grounding included
        self.assertIn('never invent or compute', c['system_prompt'])  # guardrail

    def test_compliance_prompt_has_facts_and_guardrail(self):
        with patch.object(N, '_rag_snippet', return_value='REF-COMP-123'):
            calls = N._build_compliance_calls(self.game, self.round)
        self.assertEqual(len(calls), 1)
        c = calls[0]
        self.assertEqual(c['id'], f'compliance_{self.comp_event.id}')
        self.assertIn('Uyghur Forced Labor Prevention Act', c['prompt'])
        self.assertIn('$500,000', c['prompt'])
        self.assertIn('frozen through round 2', c['prompt'])
        self.assertIn('REF-COMP-123', c['prompt'])
        self.assertIn('never invent or compute', c['system_prompt'])

    # -- store: LLM content -> stored -----------------------------------
    def test_store_uses_llm_content_when_present(self):
        results = {
            f'sc_event_{self.sc_event.id}': {'success': True, 'content': 'The quake shook Taiwan fabs.'},
            f'compliance_{self.comp_event.id}': {'success': True, 'content': 'Shipment detained under UFLPA.'},
        }
        N._store_sc_event_narratives(self.game, self.round, results)
        N._store_compliance_narratives(self.game, self.round, results)
        self.sc_event.refresh_from_db(); self.comp_event.refresh_from_db()
        self.assertEqual(self.sc_event.resolution_data['narrative'], 'The quake shook Taiwan fabs.')
        self.assertEqual(self.comp_event.narrative, 'Shipment detained under UFLPA.')

    # -- store: fallback template when no LLM ---------------------------
    def test_store_falls_back_to_template_when_no_llm(self):
        N._store_sc_event_narratives(self.game, self.round, {})     # empty results
        N._store_compliance_narratives(self.game, self.round, {})
        self.sc_event.refresh_from_db(); self.comp_event.refresh_from_db()
        # SC fallback uses the template description or a factual sentence.
        self.assertTrue(self.sc_event.resolution_data['narrative'])
        # Compliance fallback states regime + cost + freeze factually.
        self.assertIn('Uyghur Forced Labor Prevention Act', self.comp_event.narrative)
        self.assertIn('$500,000', self.comp_event.narrative)
        self.assertIn('frozen through round 2', self.comp_event.narrative)

    def test_generate_all_fallbacks_writes_sc_narratives_without_key(self):
        # With no DASHSCOPE_API_KEY, generate_round_narratives -> _generate_all_fallbacks,
        # which must still populate SC/compliance narratives (templates).
        with self.settings(DASHSCOPE_API_KEY=''):
            N.generate_round_narratives(self.game, self.round)
        self.sc_event.refresh_from_db(); self.comp_event.refresh_from_db()
        self.assertTrue(self.sc_event.resolution_data.get('narrative'))
        self.assertTrue(self.comp_event.narrative)
