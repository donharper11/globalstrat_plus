"""Published competition tie-break order is enforced by the engine."""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.engine.leaderboard import update_leaderboard
from core.models.core import Game, Round, Team
from core.models.results_financials import LeaderboardEntry, RoundResultFinancials
from core.models.scenario import FirmStarterProfile, MarketDefinition, Scenario
from core.models.sc_state import ResilienceScoreHistory


class LeaderboardTieBreakTest(TestCase):
    def test_cumulative_cash_then_revenue_then_final_resilience(self):
        user = get_user_model().objects.create_user('tie-test')
        scenario = Scenario.objects.create(
            name='Tie scenario', industry_label='Tie', description='Tie',
            starting_cash=1000)
        market = MarketDefinition.objects.create(
            scenario=scenario, name='Home', code='HOME', currency_code='USD',
            exchange_rate_base=1, base_growth_rate=0, entry_cost_base=0,
            tax_rate=0, regulatory_difficulty=1, infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=scenario, profile_name='Same', description='Same',
            home_market=market, starting_cash=1000)
        game = Game.objects.create(
            scenario=scenario, name='Tie game', created_by=user,
            status='active', current_round=2)
        r1 = Round.objects.create(game=game, round_number=1, status='processed')
        r2 = Round.objects.create(game=game, round_number=2, status='open')

        specs = [
            # name, cumulative OCF, cumulative revenue, final resilience
            ('cash-wins', 600, 100, D('0.1')),
            ('revenue-loses-to-cash', 500, 1000, D('0.9')),
            ('resilience-high', 400, 800, D('0.8')),
            ('resilience-low', 400, 800, D('0.2')),
            ('exact-tie-a', 300, 700, D('0.5')),
            ('exact-tie-b', 300, 700, D('0.5')),
        ]
        teams = []
        for name, ocf, revenue, resilience in specs:
            team = Team.objects.create(
                game=game, name=name, firm_starter_profile=profile,
                performance_index=D('55'), cash_on_hand=1000, total_equity=1000)
            teams.append(team)
            # Split totals across rounds to prove cumulative, not current-only.
            for number in (1, 2):
                RoundResultFinancials.objects.create(
                    game=game, round_number=number, team=team,
                    operating_cash_flow=D(ocf) / 2,
                    total_revenue=D(revenue) / 2)
            ResilienceScoreHistory.objects.create(
                team=team, round=r2, score=resilience)

        context = type('Context', (), {
            'game': game, 'scenario': scenario, 'round_number': 2,
            'teams': teams, 'financials': {}, 'log': [],
        })()
        update_leaderboard(context)

        ranked = list(LeaderboardEntry.objects.filter(
            game=game, round_number=2).order_by('rank').values_list(
                'team__name', flat=True))
        self.assertEqual(ranked, [
            'cash-wins', 'revenue-loses-to-cash',
            'resilience-high', 'resilience-low',
            'exact-tie-a', 'exact-tie-b'])
        tie_ranks = list(LeaderboardEntry.objects.filter(
            game=game, round_number=2,
            team__name__startswith='exact-tie').values_list('rank', flat=True))
        self.assertEqual(tie_ranks, [5, 5])
