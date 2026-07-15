"""
Unit tests for the engine pipeline (CC-05).
Tests gaussian_fit, level_gain, preference matching, Bass adoption, events.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from core.engine.utils import gaussian_fit, calculate_level_gain, clamp


# ---------------------------------------------------------------------------
# Test 1: Gaussian Fit Function
# ---------------------------------------------------------------------------

class TestGaussianFit(TestCase):

    def test_exact_match(self):
        """actual == ideal → fit = 1.0"""
        self.assertEqual(gaussian_fit(5.0, 5.0, 1.0), 1.0)

    def test_distance_decay(self):
        """actual far from ideal → fit approaches 0"""
        fit = gaussian_fit(1.0, 9.0, 1.0)
        self.assertLess(fit, 0.01)

    def test_high_tolerance_gentle_decay(self):
        """High tolerance → gentle decay"""
        strict = gaussian_fit(3.0, 5.0, 0.5)
        lenient = gaussian_fit(3.0, 5.0, 3.0)
        self.assertGreater(lenient, strict)

    def test_zero_tolerance_exact_only(self):
        """Zero tolerance → exact match only"""
        self.assertEqual(gaussian_fit(5.0, 5.0, 0), 1.0)
        self.assertEqual(gaussian_fit(5.1, 5.0, 0), 0.0)

    def test_symmetric(self):
        """Fit is symmetric around ideal."""
        fit_above = gaussian_fit(7.0, 5.0, 2.0)
        fit_below = gaussian_fit(3.0, 5.0, 2.0)
        self.assertAlmostEqual(fit_above, fit_below, places=10)

    def test_always_between_zero_and_one(self):
        """Fit should always be in [0, 1]."""
        for actual in range(0, 11):
            for ideal in range(0, 11):
                for tol in [0.1, 0.5, 1.0, 3.0, 10.0]:
                    fit = gaussian_fit(float(actual), float(ideal), tol)
                    self.assertGreaterEqual(fit, 0.0)
                    self.assertLessEqual(fit, 1.0)


# ---------------------------------------------------------------------------
# Test 2: Level Gain Calculation
# ---------------------------------------------------------------------------

class TestLevelGain(TestCase):

    def test_linear_gain(self):
        """Linear curve: gain = investment / cost_base"""
        gain = calculate_level_gain(1000000, 3.0, 'linear', 500000)
        self.assertAlmostEqual(gain, 2.0)

    def test_diminishing_higher_level_less_gain(self):
        """Diminishing: higher current level → less gain per dollar"""
        low_level = calculate_level_gain(1000000, 2.0, 'diminishing', 500000)
        high_level = calculate_level_gain(1000000, 8.0, 'diminishing', 500000)
        self.assertGreater(low_level, high_level)

    def test_exponential_higher_level_less_gain(self):
        """Exponential: much steeper cost growth"""
        low_level = calculate_level_gain(1000000, 0.0, 'exponential', 500000)
        high_level = calculate_level_gain(1000000, 9.0, 'exponential', 500000)
        self.assertGreater(low_level, high_level)

    def test_step_discrete_levels(self):
        """Step: gain is always an integer (floored)."""
        gain = calculate_level_gain(1000000, 0.0, 'step', 600000)
        self.assertEqual(gain, 1.0)  # floor(1000000/600000) = 1

    def test_gain_never_negative(self):
        """Gain should never be negative"""
        gain = calculate_level_gain(0, 5.0, 'linear', 500000)
        self.assertGreaterEqual(gain, 0)

    def test_zero_cost_base_returns_zero(self):
        """Zero cost_base → no gain (avoid divide by zero)."""
        gain = calculate_level_gain(1000000, 5.0, 'linear', 0)
        self.assertEqual(gain, 0.0)

    def test_negative_investment_returns_zero(self):
        """Negative investment → zero gain."""
        gain = calculate_level_gain(-500, 5.0, 'linear', 500000)
        self.assertEqual(gain, 0.0)

    def test_unknown_curve_fallback(self):
        """Unknown curve type falls back to linear."""
        gain = calculate_level_gain(1000000, 3.0, 'unknown_type', 500000)
        self.assertAlmostEqual(gain, 2.0)


# ---------------------------------------------------------------------------
# Test 3: Clamp
# ---------------------------------------------------------------------------

class TestClamp(TestCase):

    def test_within_range(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_below_min(self):
        self.assertEqual(clamp(-5, 0, 10), 0)

    def test_above_max(self):
        self.assertEqual(clamp(15, 0, 10), 10)

    def test_at_boundaries(self):
        self.assertEqual(clamp(0, 0, 10), 0)
        self.assertEqual(clamp(10, 0, 10), 10)


# ---------------------------------------------------------------------------
# Test 4: Integration tests requiring DB
# ---------------------------------------------------------------------------

class TestEngineIntegration(TestCase):
    """
    Integration tests for the engine pipeline.
    These require database fixtures. They verify that the engine modules
    can be imported and called without errors on minimal data.
    """

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from core.models.scenario import Scenario, MarketDefinition, FirmStarterProfile
        User = get_user_model()
        cls.user = User.objects.create_user(
            username='testengine', password='testpass',
        )
        cls.scenario = Scenario.objects.create(
            name='Test Scenario', industry_label='Test',
            description='Test scenario', starting_cash=1000000,
        )
        cls.home_market = MarketDefinition.objects.create(
            scenario=cls.scenario, name='Home', code='HM',
            description='Home market', currency_code='USD',
            exchange_rate_base=1, base_growth_rate=Decimal('0.05'),
            entry_cost_base=100000, tax_rate=Decimal('0.2'),
            regulatory_difficulty=3, infrastructure_quality=8,
        )
        cls.starter_profile = FirmStarterProfile.objects.create(
            scenario=cls.scenario, profile_name='Default',
            description='Default starter', home_market=cls.home_market,
            starting_cash=1000000,
        )

    def _make_game(self, **kwargs):
        from core.models.core import Game
        defaults = dict(
            name='Test Game', scenario=self.scenario,
            status='active', created_by=self.user,
        )
        defaults.update(kwargs)
        return Game.objects.create(**defaults)

    def _make_team(self, game, **kwargs):
        from core.models.core import Team
        defaults = dict(
            name='Team A', game=game,
            firm_starter_profile=self.starter_profile,
            performance_index=55, cash_on_hand=1000000,
            total_equity=1000000,
        )
        defaults.update(kwargs)
        return Team.objects.create(**defaults)

    def test_imports(self):
        """All engine modules (CC-5 + CC-6 + CC-7 + CC-11) import without error."""
        from core.engine.events import fire_events, update_market_conditions, process_event_responses
        from core.engine.events import generate_event_narrative, generate_event_context, _rag_enhance_event
        from core.engine.rd_processing import process_rd
        from core.engine.strategy_effects import apply_strategy_effects
        from core.engine.preference_engine import calculate_fit_scores
        from core.engine.campaign_engine import apply_campaign_multipliers
        from core.engine.readiness_engine import apply_readiness_gating
        from core.engine.bass_engine import run_bass_adoption
        from core.engine.advance_round import advance_round
        from core.engine.utils import (
            RoundContext, MarketEffectiveState, SegmentEffectiveState,
            gaussian_fit, calculate_level_gain, clamp, get_config,
        )
        # CC-6 modules
        from core.engine.revenue import calculate_revenue
        from core.engine.costs import (
            calculate_cogs, calculate_logistics_tariffs,
            calculate_operating_expenses, calculate_interest,
            calculate_tax, calculate_inventory_costs,
        )
        from core.engine.financials import generate_financial_statements
        from core.engine.performance import calculate_performance_index
        from core.engine.coherence import calculate_coherence
        from core.engine.leaderboard import update_leaderboard
        self.assertTrue(True)

    def test_round_context_initialization(self):
        """RoundContext initializes with correct structure."""
        from core.engine.utils import RoundContext

        game = self._make_game()
        context = RoundContext(game, 1)
        self.assertEqual(context.game, game)
        self.assertEqual(context.round_number, 1)
        self.assertEqual(context.scenario, self.scenario)
        self.assertIsInstance(context.markets, dict)
        self.assertIsInstance(context.segments, dict)
        self.assertIsInstance(context.fit_scores, dict)
        self.assertIsInstance(context.adoption, dict)
        self.assertIsInstance(context.events_fired, list)
        self.assertIsInstance(context.log, list)

    def test_process_round_with_no_current_round(self):
        """Processing raises ValueError when the game has no current round.

        Updated 2026-07-15: the engine now processes the round the game is on
        (game.current_round) rather than searching for status='open', so a
        deadline can close a round before it is processed. The old assertion
        looked for the message 'No open round'.
        """
        from core.engine.advance_round import process_round

        game = self._make_game()
        with self.assertRaises(ValueError) as ctx:
            process_round(game.id)
        self.assertIn('No round', str(ctx.exception))

    def test_process_round_auto_locks_an_unlocked_team(self):
        """An unlocked team is auto-locked, not rejected.

        Updated 2026-07-15: this previously asserted advance_round raised
        'has not locked'. The engine has never raised that — it auto-locks
        whatever a team had. The guard against advancing with teams still
        pending lives in the instructor view, which offers a force override.
        This test never ran before, because the test database could not be
        created (see globalstrat.test_runner).
        """
        from core.engine.advance_round import close_round
        from core.models.core import Round
        from core.models.decisions import DecisionSubmission

        game = self._make_game(current_round=1)
        team = self._make_team(game)
        rnd = Round.objects.create(game=game, round_number=1, status='open')

        self.assertFalse(
            DecisionSubmission.objects.filter(team=team, round=rnd).exists())

        close_round(game.id)

        submission = DecisionSubmission.objects.get(team=team, round=rnd)
        self.assertEqual(submission.status, 'locked')
        self.assertIsNotNone(submission.locked_at)


# ---------------------------------------------------------------------------
# Test 5: CC-06 Financial Models
# ---------------------------------------------------------------------------

class TestFinancialModels(TestCase):
    """Test that CC-06 result models can be created."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from core.models.scenario import Scenario, MarketDefinition, FirmStarterProfile
        User = get_user_model()
        cls.user = User.objects.create_user(username='testfin', password='testpass')
        cls.scenario = Scenario.objects.create(
            name='Fin Test', industry_label='Test',
            description='Test', starting_cash=1000000,
        )
        cls.market = MarketDefinition.objects.create(
            scenario=cls.scenario, name='Home', code='HM',
            description='Home', currency_code='USD',
            exchange_rate_base=1, base_growth_rate=Decimal('0.05'),
            entry_cost_base=100000, tax_rate=Decimal('0.2'),
            regulatory_difficulty=3, infrastructure_quality=8,
        )
        cls.starter = FirmStarterProfile.objects.create(
            scenario=cls.scenario, profile_name='Default',
            description='Default', home_market=cls.market,
            starting_cash=1000000,
        )
        from core.models.core import Game, Team, Round
        cls.game = Game.objects.create(
            name='Fin Game', scenario=cls.scenario,
            status='active', created_by=cls.user,
        )
        cls.team = Team.objects.create(
            name='Team Fin', game=cls.game,
            firm_starter_profile=cls.starter,
            performance_index=55, cash_on_hand=1000000,
            total_equity=1000000,
        )

    def test_round_result_financials_create(self):
        from core.models.results_financials import RoundResultFinancials
        obj = RoundResultFinancials.objects.create(
            game=self.game, round_number=1, team=self.team,
            total_revenue=Decimal('1000000'),
            net_income=Decimal('200000'),
            cash_opening=Decimal('1000000'),
            cash_closing=Decimal('1200000'),
        )
        self.assertEqual(obj.total_revenue, Decimal('1000000'))

    def test_leaderboard_entry_create(self):
        from core.models.results_financials import LeaderboardEntry
        obj = LeaderboardEntry.objects.create(
            game=self.game, round_number=1, team=self.team,
            rank=1, performance_index=Decimal('56.20'),
            total_revenue=Decimal('1000000'),
            net_income=Decimal('200000'),
            market_share_summary={'HM': 0.45},
        )
        self.assertEqual(obj.rank, 1)
        self.assertEqual(obj.market_share_summary['HM'], 0.45)

    def test_performance_index_create(self):
        from core.models.results_financials import RoundResultPerformanceIndex
        obj = RoundResultPerformanceIndex.objects.create(
            game=self.game, round_number=1, team=self.team,
            satisfaction_score=Decimal('0.5600'),
            index_change=Decimal('1.20'),
            index_value=Decimal('56.20'),
        )
        self.assertEqual(obj.index_change, Decimal('1.20'))

    def test_coherence_create(self):
        from core.models.results_financials import RoundResultCoherence
        obj = RoundResultCoherence.objects.create(
            game=self.game, round_number=1, team=self.team,
            formula_score=Decimal('72.00'),
            rag_score=None,
            blended_score=Decimal('72.00'),
            breakdown={'positioning_price': {'score': 0.85}},
        )
        self.assertIsNone(obj.rag_score)
        self.assertEqual(obj.blended_score, Decimal('72.00'))

    def test_market_intelligence_brief_create(self):
        from core.models.results_financials import MarketIntelligenceBrief
        obj = MarketIntelligenceBrief.objects.create(
            game=self.game, round_number=2, team=None,
            market=self.market, brief_level='basic',
            brief_content='Market outlook for next round.',
        )
        self.assertEqual(obj.brief_level, 'basic')


# ---------------------------------------------------------------------------
# Test 6: Coherence alignment matrices
# ---------------------------------------------------------------------------

class TestCoherenceScoring(TestCase):

    def test_aligned_pricing(self):
        """Price within positioning range → full score."""
        from core.engine.coherence import PRICE_RANGES
        rng = PRICE_RANGES['mainstream']
        price = 400
        self.assertTrue(rng[0] <= price <= rng[1])

    def test_misaligned_pricing(self):
        """Premium price in budget range → out of range."""
        from core.engine.coherence import PRICE_RANGES
        rng = PRICE_RANGES['budget']
        price = 800
        self.assertFalse(rng[0] <= price <= rng[1])

    def test_distribution_alignment_matrix(self):
        """Premium + exclusive = 1.0, premium + mass = 0.2."""
        from core.engine.coherence import DISTRIBUTION_ALIGNMENT
        self.assertEqual(DISTRIBUTION_ALIGNMENT[('premium', 'exclusive_retail')], 1.0)
        self.assertEqual(DISTRIBUTION_ALIGNMENT[('premium', 'mass_retail')], 0.2)

    def test_budget_mass_retail_alignment(self):
        from core.engine.coherence import DISTRIBUTION_ALIGNMENT
        self.assertEqual(DISTRIBUTION_ALIGNMENT[('budget', 'mass_retail')], 1.0)

    def test_ultra_premium_mass_retail_misalignment(self):
        from core.engine.coherence import DISTRIBUTION_ALIGNMENT
        self.assertEqual(DISTRIBUTION_ALIGNMENT[('ultra_premium', 'mass_retail')], 0.0)


# ---------------------------------------------------------------------------
# Test 7: CC-07 Event narrative generation
# ---------------------------------------------------------------------------

class TestEventNarrativeGeneration(TestCase):

    def test_generate_event_narrative_market_placeholder(self):
        """Template {market} placeholder resolved to market name."""
        from core.engine.events import generate_event_narrative
        from unittest.mock import MagicMock

        template = MagicMock()
        template.description_template = 'Trade disruption in {market} affects supply chains.'
        template.impacts = MagicMock()
        template.impacts.order_by.return_value.first.return_value = None

        market = MagicMock()
        market.name = 'Western Europe'

        result = generate_event_narrative(template, market, 3, None)
        self.assertIn('Western Europe', result)
        self.assertNotIn('{market}', result)

    def test_generate_event_narrative_no_market(self):
        """No target market → 'global markets'."""
        from core.engine.events import generate_event_narrative
        from unittest.mock import MagicMock

        template = MagicMock()
        template.description_template = 'Disruption in {market}.'
        template.impacts = MagicMock()
        template.impacts.order_by.return_value.first.return_value = None

        result = generate_event_narrative(template, None, 1, None)
        self.assertIn('global markets', result)

    def test_generate_event_narrative_value_placeholder(self):
        """Template {value} resolved from impact."""
        from core.engine.events import generate_event_narrative
        from unittest.mock import MagicMock
        from decimal import Decimal

        impact = MagicMock()
        impact.impact_type = 'demand_shock'
        impact.impact_value = Decimal('1.15')

        template = MagicMock()
        template.description_template = 'Demand surges by {value}% in {market}.'
        template.impacts = MagicMock()
        template.impacts.order_by.return_value.first.return_value = impact

        result = generate_event_narrative(template, None, 1, None)
        self.assertIn('15', result)  # abs((1.15 - 1) * 100) = 15
        self.assertNotIn('{value}', result)

    def test_generate_event_narrative_round_placeholder(self):
        """Template {round} resolved to round number."""
        from core.engine.events import generate_event_narrative
        from unittest.mock import MagicMock

        template = MagicMock()
        template.description_template = 'Event in round {round}.'
        template.impacts = MagicMock()
        template.impacts.order_by.return_value.first.return_value = None

        result = generate_event_narrative(template, None, 5, None)
        self.assertIn('5', result)

    def test_generate_event_context_demand_shock(self):
        """Context generation for demand shock."""
        from core.engine.events import generate_event_context
        from unittest.mock import MagicMock

        impact = MagicMock()
        impact.impact_type = 'demand_shock'
        impact.impact_value = 1.2

        result = generate_event_context(None, [impact])
        self.assertIn('surging', result)

    def test_generate_event_context_cost_change(self):
        """Context generation for cost change."""
        from core.engine.events import generate_event_context
        from unittest.mock import MagicMock

        impact = MagicMock()
        impact.impact_type = 'cost_change'
        impact.impact_value = 0.05

        result = generate_event_context(None, [impact])
        self.assertIn('increased', result)

    def test_generate_event_context_max_sentences(self):
        """Context limited to 3 sentences max."""
        from core.engine.events import generate_event_context
        from unittest.mock import MagicMock

        impacts = []
        for _ in range(5):
            impact = MagicMock()
            impact.impact_type = 'cost_change'
            impact.impact_value = 0.1
            impacts.append(impact)

        result = generate_event_context(None, impacts)
        # Should have at most 3 parts
        sentences = [s.strip() for s in result.split('.') if s.strip()]
        self.assertLessEqual(len(sentences), 6)  # 3 parts × 2 sentences each


# ---------------------------------------------------------------------------
# Test 8: CC-07 Event response processing
# ---------------------------------------------------------------------------

class TestEventResponseProcessing(TestCase):

    def test_imports(self):
        """CC-7 event functions import without error."""
        from core.engine.events import (
            generate_event_narrative,
            generate_event_context,
            process_event_responses,
        )
        self.assertTrue(True)

    def test_process_event_responses_no_events(self):
        """process_event_responses with empty events_fired does nothing."""
        from core.engine.events import process_event_responses
        from unittest.mock import MagicMock

        context = MagicMock()
        context.events_fired = []
        process_event_responses(context)
        # No errors, no log entries added
        self.assertEqual(context.log.append.call_count, 0)


# ---------------------------------------------------------------------------
# Test 9: CC-07 RAG infrastructure
# ---------------------------------------------------------------------------

class TestRAGInfrastructure(TestCase):

    def test_rag_model_import(self):
        """ResearchQueryLog model imports."""
        from core.models.rag import ResearchQueryLog
        self.assertTrue(True)

    def test_rag_client_import(self):
        """Qdrant client module imports."""
        from core.rag.client import get_qdrant_client, ensure_collection, search_articles
        self.assertTrue(True)

    def test_rag_embeddings_import(self):
        """Embedding module imports."""
        from core.rag.embeddings import get_embedding
        self.assertTrue(True)

    def test_rag_views_import(self):
        """RAG views import."""
        from core.rag.views import ActiveEventsView, EventHistoryView, ResearchQueryView
        self.assertTrue(True)

    def test_research_query_log_create(self):
        """ResearchQueryLog can be created."""
        from django.contrib.auth import get_user_model
        from core.models.core import Game, Team
        from core.models.scenario import Scenario, MarketDefinition, FirmStarterProfile
        from core.models.rag import ResearchQueryLog

        User = get_user_model()
        user = User.objects.create_user(username='testrag', password='testpass')
        scenario = Scenario.objects.create(
            name='RAG Test', industry_label='Test',
            description='Test', starting_cash=1000000,
        )
        market = MarketDefinition.objects.create(
            scenario=scenario, name='Home', code='HM',
            description='Home', currency_code='USD',
            exchange_rate_base=1, base_growth_rate=Decimal('0.05'),
            entry_cost_base=100000, tax_rate=Decimal('0.2'),
            regulatory_difficulty=3, infrastructure_quality=8,
        )
        starter = FirmStarterProfile.objects.create(
            scenario=scenario, profile_name='Default',
            description='Default', home_market=market,
            starting_cash=1000000,
        )
        game = Game.objects.create(
            name='RAG Game', scenario=scenario,
            status='active', created_by=user,
        )
        team = Team.objects.create(
            name='Team RAG', game=game,
            firm_starter_profile=starter,
            performance_index=55, cash_on_hand=1000000,
            total_equity=1000000,
        )

        log = ResearchQueryLog.objects.create(
            team=team,
            round_number=1,
            query_text='market entry strategies',
            response_text='No relevant research found.',
        )
        self.assertEqual(log.round_number, 1)
        self.assertIn('market entry', log.query_text)


# ---------------------------------------------------------------------------
# Test 10: CC-11 Article Ingestion Pipeline
# ---------------------------------------------------------------------------

class TestArticleIngestion(TestCase):

    def test_ingest_module_imports(self):
        """CC-11 ingestion module imports."""
        from core.rag.ingest import (
            extract_text_from_pdf, extract_text_from_docx,
            chunk_article, assign_tags, ingest_article,
        )
        self.assertTrue(True)

    def test_chunk_article_small(self):
        """Small text produces a single chunk."""
        from core.rag.ingest import chunk_article
        pages = [(1, 'This is a short article about market entry strategies.')]
        chunks = chunk_article(pages)
        self.assertGreaterEqual(len(chunks), 1)
        self.assertIn('market entry', chunks[0]['text'].lower())

    def test_chunk_article_with_sections(self):
        """Text with section headers is chunked by section."""
        from core.rag.ingest import chunk_article
        text = (
            "Some preamble text about global strategy.\n\n"
            "Introduction\n\n"
            "This paper examines market entry modes for emerging markets.\n\n"
            "Methodology\n\n"
            "We conducted interviews with 50 MNE executives.\n\n"
            "Conclusion\n\n"
            "Joint ventures are the preferred entry mode for high-risk markets.\n\n"
            "References\n\n"
            "Smith 2020, Jones 2021"
        )
        pages = [(1, text)]
        chunks = chunk_article(pages)
        # References should be excluded
        chunk_texts = ' '.join(c['text'] for c in chunks)
        self.assertNotIn('Smith 2020', chunk_texts)

    def test_assign_tags_market_entry(self):
        """Market entry keywords produce market_entry tag."""
        from core.rag.ingest import assign_tags
        tags = assign_tags(
            'article_market_entry_strategy.pdf',
            'This article examines foreign market entry modes.',
        )
        self.assertIn('market_entry', tags)

    def test_assign_tags_multiple(self):
        """Multiple keyword matches produce multiple tags."""
        from core.rag.ingest import assign_tags
        tags = assign_tags(
            'international_business/article_sustainability.pdf',
            'CSR and corporate social responsibility in emerging markets.',
        )
        self.assertIn('sustainability', tags)
        self.assertIn('emerging_market', tags)
        self.assertIn('international_business', tags)

    def test_assign_tags_fallback_general(self):
        """No keyword matches → 'general' tag."""
        from core.rag.ingest import assign_tags
        tags = assign_tags('unknown.pdf', 'Lorem ipsum dolor sit amet.')
        self.assertIn('general', tags)

    def test_enhance_query_market_expansion(self):
        """Query with 'asia' gets APAC expansion."""
        from core.rag.views import enhance_query
        result = enhance_query('market entry in asia')
        self.assertIn('APAC', result)

    def test_enhance_query_no_expansion(self):
        """Query without market keyword returns original."""
        from core.rag.views import enhance_query
        result = enhance_query('competitive strategy framework')
        self.assertEqual(result, 'competitive strategy framework')

    def test_fallback_brief(self):
        """Fallback brief returns structured excerpts."""
        from core.rag.views import _fallback_brief
        results = [
            {'title': 'Test Article', 'text': 'Some research content about strategy.'},
        ]
        brief = _fallback_brief(results)
        self.assertIn('Test Article', brief)
        self.assertIn('synthesis unavailable', brief)

    def test_coherence_rag_disabled(self):
        """RAG coherence returns None when RAG disabled."""
        from core.engine.coherence import _calculate_rag_coherence
        from unittest.mock import MagicMock
        context = MagicMock()
        context.scenario = MagicMock()
        team = MagicMock()
        # get_config returns False for rag_enabled
        with patch('core.engine.coherence.get_config', return_value=False):
            score, feedback = _calculate_rag_coherence(context, team, 50.0)
        self.assertIsNone(score)
        self.assertIsNone(feedback)

    def test_compile_decision_summary_empty(self):
        """Empty decisions produce fallback summary."""
        from core.engine.coherence import _compile_decision_summary
        from django.contrib.auth import get_user_model
        from core.models.core import Game, Team
        from core.models.scenario import Scenario, MarketDefinition, FirmStarterProfile
        from unittest.mock import MagicMock

        User = get_user_model()
        user = User.objects.create_user(username='testsummary', password='testpass')
        scenario = Scenario.objects.create(
            name='Summary Test', industry_label='Test',
            description='Test', starting_cash=1000000,
        )
        market = MarketDefinition.objects.create(
            scenario=scenario, name='Home', code='HM',
            description='Home', currency_code='USD',
            exchange_rate_base=1, base_growth_rate=Decimal('0.05'),
            entry_cost_base=100000, tax_rate=Decimal('0.2'),
            regulatory_difficulty=3, infrastructure_quality=8,
        )
        starter = FirmStarterProfile.objects.create(
            scenario=scenario, profile_name='Default',
            description='Default', home_market=market,
            starting_cash=1000000,
        )
        game = Game.objects.create(
            name='Summary Game', scenario=scenario,
            status='active', created_by=user,
        )
        team = Team.objects.create(
            name='Team Summary', game=game,
            firm_starter_profile=starter,
            performance_index=55, cash_on_hand=1000000,
            total_equity=1000000,
        )
        context = MagicMock()
        context.round_number = 1
        summary = _compile_decision_summary(team, context)
        self.assertIn('No significant decisions', summary)
