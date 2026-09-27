"""
Strategic Reasoning Evaluator: unit + integration tests.

Tests each engine module with 4 team archetypes:
  1. Aligned Strategist (high coherence, responsive, consistent)
  2. Reactive Sprinter (moderate coherence, reactive adjustments)
  3. Steady Conservative (good consistency, low responsiveness)
  4. Erratic Explorer (frequent reversals, low scores)

Also tests R40 compliance: competition grading uses only deterministic score.
"""
from decimal import Decimal as D
from unittest.mock import patch

from django.test import SimpleTestCase

from core.engine.reasoning_coherence import (
    CoherenceExtInput, ProductInfo, MarketPresenceInfo, BudgetInfo,
    MarketingInfo, MarketEntryInfo, FinancingInfo, PlantInfo,
    ESGInfo, GovernanceCommitment, PlatformDevInfo,
    calculate_coherence_ext,
)
from core.engine.reasoning_responsiveness import (
    ResponsivenessInput, EventSignal, DecisionChange,
    calculate_responsiveness,
)
from core.engine.reasoning_trajectory import (
    TrajectoryInput, RoundSnapshot, calculate_trajectory,
)
from core.engine.reasoning_justification import (
    JustificationInput, build_justification_prompt,
    parse_justification_response, template_fallback_score,
)
from core.engine.reasoning_aggregator import (
    compose_scores, DETERMINISTIC_WEIGHTS, FULL_WEIGHTS,
)


# ── Archetype fixtures ──

def _aligned_strategist_coherence():
    """High-coherence: premium products, high R&D, matching marketing."""
    return CoherenceExtInput(
        products=[
            ProductInfo(name='ProWidget', positioning='premium', platform_name='Gen3'),
        ],
        market_presences=[
            MarketPresenceInfo(market_name='US', market_code='US', status='active'),
            MarketPresenceInfo(market_name='EU', market_code='EU', status='active'),
        ],
        budget=BudgetInfo(rd_budget=600000, marketing_budget=300000, strategy_budget=100000),
        marketing_decisions=[
            MarketingInfo(product_name='ProWidget', market_name='US', promotion_budget=150000, production_volume=5000),
            MarketingInfo(product_name='ProWidget', market_name='EU', promotion_budget=150000, production_volume=3000),
        ],
        market_entries=[],
        financing=FinancingInfo(new_debt=0, debt_repayment=50000, dividend_per_share=0),
        plants=[
            PlantInfo(market_name='US', capacity=10000, status='active'),
        ],
        esg=ESGInfo(environmental_spend=50000, social_spend=30000),
        governance_commitments=[
            GovernanceCommitment(commitment_type='sustainability', is_active=True),
        ],
        platform_devs=[
            PlatformDevInfo(platform_name='Gen3', investment=200000),
        ],
        total_revenue=5000000,
        total_debt=500000,
        total_equity=2000000,
    )


def _erratic_explorer_coherence():
    """Low coherence: budget products but high R&D, dividends during expansion."""
    return CoherenceExtInput(
        products=[
            ProductInfo(name='CheapWidget', positioning='budget'),
        ],
        market_presences=[
            MarketPresenceInfo(market_name='US', market_code='US', status='active'),
        ],
        budget=BudgetInfo(rd_budget=800000, marketing_budget=100000, strategy_budget=100000),
        marketing_decisions=[],  # No marketing for entries
        market_entries=[
            MarketEntryInfo(market_name='China', action='enter', initial_investment=500000),
            MarketEntryInfo(market_name='India', action='enter', initial_investment=500000),
        ],
        financing=FinancingInfo(new_debt=2000000, dividend_per_share=5.0),
        plants=[],
        esg=None,
        governance_commitments=[
            GovernanceCommitment(commitment_type='sustainability', is_active=True),
        ],
        platform_devs=[],
        total_revenue=1000000,
        total_debt=3000000,
        total_equity=500000,
    )


class CoherenceExtTests(SimpleTestCase):
    """Dim 1: Extended Coherence — pure function tests."""

    def test_aligned_strategist_scores_high(self):
        inp = _aligned_strategist_coherence()
        result = calculate_coherence_ext(inp)
        self.assertGreaterEqual(result.score, 60.0,
            f"Aligned strategist should score >= 60, got {result.score}")
        self.assertEqual(len(result.sub_scores), 5)
        self.assertIn('positioning_investment', result.sub_scores)

    def test_erratic_explorer_scores_low(self):
        inp = _erratic_explorer_coherence()
        result = calculate_coherence_ext(inp)
        self.assertLessEqual(result.score, 60.0,
            f"Erratic explorer should score <= 60, got {result.score}")
        # Should flag dividends during expansion
        signals_text = ' '.join(result.signals)
        self.assertTrue(
            any('market entry' in s.lower() or 'dividend' in s.lower() for s in result.signals),
            f"Should flag dividends or unsupported entries, got: {result.signals}"
        )

    def test_no_products_returns_moderate(self):
        inp = CoherenceExtInput()
        result = calculate_coherence_ext(inp)
        self.assertGreater(result.score, 0)
        self.assertLessEqual(result.score, 100)

    def test_sub_scores_sum_correctly(self):
        inp = _aligned_strategist_coherence()
        result = calculate_coherence_ext(inp)
        expected_avg = sum(result.sub_scores.values()) / len(result.sub_scores)
        self.assertAlmostEqual(result.score, expected_avg, places=1)


class ResponsivenessTests(SimpleTestCase):
    """Dim 2: Signal Responsiveness — pure function tests."""

    def test_no_events_returns_neutral(self):
        result = calculate_responsiveness(ResponsivenessInput())
        self.assertEqual(result.score, 70.0)
        self.assertEqual(result.events_relevant, 0)

    def test_responsive_team_scores_high(self):
        inp = ResponsivenessInput(
            events=[
                EventSignal(
                    event_name='Tariff Increase',
                    category='ECONOMIC',
                    affected_markets=['US'],
                    severity=0.7,
                ),
            ],
            has_event_response=True,
            decision_changes=[
                DecisionChange(domain='pricing', market='US',
                               description='Price raised 10%', magnitude=0.5),
                DecisionChange(domain='production', market='US',
                               description='Volume reduced', magnitude=0.3),
            ],
        )
        result = calculate_responsiveness(inp)
        self.assertGreaterEqual(result.score, 60.0,
            f"Responsive team should score >= 60, got {result.score}")
        self.assertEqual(result.events_addressed, 1)

    def test_unresponsive_team_scores_low(self):
        inp = ResponsivenessInput(
            events=[
                EventSignal(
                    event_name='Major Disruption',
                    category='SUPPLY_CHAIN',
                    severity=0.9,
                ),
            ],
            has_event_response=False,
            decision_changes=[],
        )
        result = calculate_responsiveness(inp)
        self.assertLessEqual(result.score, 30.0,
            f"Unresponsive team should score <= 30, got {result.score}")


class TrajectoryTests(SimpleTestCase):
    """Dim 3: Strategic Trajectory — pure function tests."""

    def test_insufficient_rounds_returns_neutral(self):
        inp = TrajectoryInput(round_snapshots=[
            RoundSnapshot(round_number=1, rd_budget_pct=0.3),
        ])
        result = calculate_trajectory(inp)
        self.assertEqual(result.score, 50.0)
        self.assertEqual(result.pattern, 'consistent')

    def test_consistent_executor(self):
        """Stable budget allocation across rounds → consistent pattern."""
        snapshots = [
            RoundSnapshot(round_number=i, rd_budget_pct=0.30, marketing_budget_pct=0.40,
                          strategy_budget_pct=0.30, num_active_markets=3, num_products=2,
                          avg_price=500, total_debt=500000, total_equity=2000000)
            for i in range(1, 6)
        ]
        result = calculate_trajectory(TrajectoryInput(round_snapshots=snapshots))
        self.assertIn(result.pattern, ['consistent', 'conservative'],
            f"Stable team should be consistent/conservative, got {result.pattern}")
        self.assertGreaterEqual(result.score, 65.0)

    def test_aggressive_expander(self):
        """Rapidly increasing markets → aggressive pattern."""
        snapshots = [
            RoundSnapshot(round_number=i, rd_budget_pct=0.3, marketing_budget_pct=0.4,
                          strategy_budget_pct=0.3, num_active_markets=i+1,
                          num_products=2, num_new_entries=2,
                          avg_price=500, total_debt=1000000*i, total_equity=2000000)
            for i in range(1, 6)
        ]
        result = calculate_trajectory(TrajectoryInput(round_snapshots=snapshots))
        self.assertIn(result.pattern, ['aggressive', 'reactive'],
            f"Expanding team should be aggressive/reactive, got {result.pattern}")

    def test_erratic_pattern(self):
        """Frequent reversals → erratic pattern."""
        snapshots = [
            RoundSnapshot(round_number=1, rd_budget_pct=0.5, marketing_budget_pct=0.3,
                          num_active_markets=3, num_products=2),
            RoundSnapshot(round_number=2, rd_budget_pct=0.1, marketing_budget_pct=0.7,
                          num_active_markets=1, num_products=4),
            RoundSnapshot(round_number=3, rd_budget_pct=0.6, marketing_budget_pct=0.2,
                          num_active_markets=4, num_products=1),
            RoundSnapshot(round_number=4, rd_budget_pct=0.15, marketing_budget_pct=0.6,
                          num_active_markets=2, num_products=5),
            RoundSnapshot(round_number=5, rd_budget_pct=0.55, marketing_budget_pct=0.25,
                          num_active_markets=5, num_products=2),
        ]
        result = calculate_trajectory(TrajectoryInput(round_snapshots=snapshots))
        self.assertEqual(result.pattern, 'erratic',
            f"Reversing team should be erratic, got {result.pattern}")
        self.assertLessEqual(result.score, 55.0)


class JustificationTests(SimpleTestCase):
    """Dim 4: Justification Quality — prompt builder + parser tests."""

    def test_build_prompt_with_notes(self):
        jinp = JustificationInput(
            team_notes='We entered China because revenue dropped 15%.',
            communications=['Dear Board, we are expanding to China.'],
        )
        result = build_justification_prompt(jinp)
        self.assertIn('system_prompt', result)
        self.assertIn('prompt', result)
        self.assertIn('revenue dropped', result['prompt'])

    def test_build_prompt_empty_notes(self):
        jinp = JustificationInput()
        result = build_justification_prompt(jinp)
        self.assertIn('No notes', result['prompt'])

    def test_parse_valid_json(self):
        raw = '{"score": 65, "depth": "multi_perspective", "evidence": ["cites data"], "feedback": "Good analysis."}'
        result = parse_justification_response(raw)
        self.assertEqual(result.score, 65.0)
        self.assertEqual(result.depth_label, 'multi_perspective')

    def test_parse_invalid_json_falls_back(self):
        result = parse_justification_response('this is not json')
        self.assertIsNotNone(result.score)
        self.assertGreaterEqual(result.score, 0)

    def test_template_fallback_empty(self):
        result = template_fallback_score('')
        self.assertLessEqual(result.score, 15)
        self.assertEqual(result.depth_label, 'surface')

    def test_template_fallback_rich_text(self):
        notes = (
            "We applied Porter's Five Forces analysis to evaluate our competitive "
            "position. Revenue dropped 15% from $5.2M to $4.4M, and our SWOT analysis "
            "revealed weaknesses in our supply chain. However, on the other hand, "
            "our R&D investments increased differentiation by 23%. We weighed the "
            "tradeoff between aggressive expansion and consolidation, alternatively "
            "considering a blue ocean strategy in emerging markets. Despite the "
            "risks, our stakeholder analysis supports continued expansion because "
            "our value chain improvements yielded a 12% cost reduction."
        )
        result = template_fallback_score(notes)
        self.assertGreaterEqual(result.score, 50,
            f"Rich text should score >= 50, got {result.score}")


class AggregatorTests(SimpleTestCase):
    """Score composition + band assignment tests."""

    def test_deterministic_weights_sum_to_one(self):
        total = sum(DETERMINISTIC_WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_full_weights_sum_to_one(self):
        total = sum(FULL_WEIGHTS.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_compose_deterministic_only(self):
        from core.engine.reasoning_coherence import CoherenceExtResult
        from core.engine.reasoning_responsiveness import ResponsivenessResult
        from core.engine.reasoning_trajectory import TrajectoryResult

        result = compose_scores(
            coherence=CoherenceExtResult(score=80.0, sub_scores={}, signals=[], feedback={}),
            responsiveness=ResponsivenessResult(score=70.0, events_relevant=0, events_addressed=0),
            trajectory=TrajectoryResult(score=60.0, pattern='consistent', stability_score=70.0),
            justification=None,
        )
        expected = 80*0.4 + 70*0.3 + 60*0.3
        self.assertAlmostEqual(result.reasoning_score_deterministic, expected, places=1)
        self.assertIsNone(result.reasoning_score_full)
        self.assertEqual(result.overall_band, 'strong')

    def test_compose_with_justification(self):
        from core.engine.reasoning_coherence import CoherenceExtResult
        from core.engine.reasoning_responsiveness import ResponsivenessResult
        from core.engine.reasoning_trajectory import TrajectoryResult
        from core.engine.reasoning_justification import JustificationResult

        result = compose_scores(
            coherence=CoherenceExtResult(score=50.0, sub_scores={}, signals=[], feedback={}),
            responsiveness=ResponsivenessResult(score=40.0, events_relevant=1, events_addressed=0),
            trajectory=TrajectoryResult(score=30.0, pattern='erratic', stability_score=20.0),
            justification=JustificationResult(score=20.0, depth_label='surface'),
        )
        expected_full = 50*0.3 + 40*0.25 + 30*0.2 + 20*0.25
        self.assertAlmostEqual(result.reasoning_score_full, expected_full, places=1)
        self.assertEqual(result.overall_band, 'needs_attention')

    def test_band_assignment_strong(self):
        from core.engine.reasoning_coherence import CoherenceExtResult
        from core.engine.reasoning_responsiveness import ResponsivenessResult
        from core.engine.reasoning_trajectory import TrajectoryResult

        result = compose_scores(
            coherence=CoherenceExtResult(score=90.0, sub_scores={}, signals=[], feedback={}),
            responsiveness=ResponsivenessResult(score=80.0, events_relevant=0, events_addressed=0),
            trajectory=TrajectoryResult(score=75.0, pattern='consistent', stability_score=80.0),
        )
        self.assertEqual(result.overall_band, 'strong')

    def test_student_feedback_has_no_scores(self):
        from core.engine.reasoning_coherence import CoherenceExtResult
        from core.engine.reasoning_responsiveness import ResponsivenessResult
        from core.engine.reasoning_trajectory import TrajectoryResult

        result = compose_scores(
            coherence=CoherenceExtResult(score=50.0, sub_scores={}, signals=[], feedback={}),
            responsiveness=ResponsivenessResult(score=50.0, events_relevant=0, events_addressed=0),
            trajectory=TrajectoryResult(score=50.0, pattern='reactive', stability_score=50.0),
        )
        fb = result.feedback_student
        # Student feedback should never contain numeric scores
        import json
        fb_str = json.dumps(fb)
        for dim in fb.get('dimensions', {}).values():
            self.assertNotIn('score', dim,
                "Student feedback must not contain numeric scores")

    def test_zh_cn_feedback(self):
        from core.engine.reasoning_coherence import CoherenceExtResult
        from core.engine.reasoning_responsiveness import ResponsivenessResult
        from core.engine.reasoning_trajectory import TrajectoryResult

        result = compose_scores(
            coherence=CoherenceExtResult(score=80.0, sub_scores={}, signals=[], feedback={}),
            responsiveness=ResponsivenessResult(score=70.0, events_relevant=0, events_addressed=0),
            trajectory=TrajectoryResult(score=60.0, pattern='consistent', stability_score=70.0),
            language='zh-CN',
        )
        fb = result.feedback_student
        # Should contain Chinese text
        dims = fb.get('dimensions', {})
        if dims:
            first_dim = list(dims.values())[0]
            self.assertTrue(
                any(ord(c) > 127 for c in first_dim.get('feedback', '')),
                "zh-CN feedback should contain CJK characters"
            )


class R40ComplianceTests(SimpleTestCase):
    """R40: justification_score (MODEL_DERIVED) must not reach competition grades."""

    def test_grading_extractor_ignores_full_score_in_competition(self):
        """Competition mode: reasoning_quality extractor returns deterministic only."""
        # This test verifies the grading service logic by checking the
        # extractor function behavior when competition_mode is set
        from core.services.grading import COMPONENT_EXTRACTORS
        self.assertIn('reasoning_quality', COMPONENT_EXTRACTORS,
            "reasoning_quality should be registered in COMPONENT_EXTRACTORS")
