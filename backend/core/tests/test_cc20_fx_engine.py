"""
CC-20 — FX hedge lifecycle tests.

Proves the hedge lifecycle the engine previously ignored: an FX hedge decision
OPENS a HedgePosition (locking the current rate on a notional = hedge_ratio% of
foreign receivables), positions are MARKED to market each round, and they SETTLE
at maturity — booking realized P&L (correct sign) into context.sc_fx_hedge_pnl,
which generate_financial_statements adds to pre-tax income.
"""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models.core import Game, Team, Round
from core.models.scenario import Scenario, MarketDefinition, FirmStarterProfile
from core.models.sc_decisions import FXHedgeDecision
from core.models.sc_state import HedgePosition
from core.engine.fx_engine import process_fx_hedges
from core.engine.utils import MarketEffectiveState


class _Ctx:
    def __init__(self, game, round_number, teams, scenario):
        self.game = game
        self.round_number = round_number
        self.teams = teams
        self.scenario = scenario
        self.markets = {}
        self.market_revenue = {}
        self.log = []


class CC20FXHedgeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_scenario', file='scenarios/consumer_electronics_2026.yaml')
        cls.scenario = Scenario.objects.get(name='Consumer Electronics 2026')
        cls.creator = get_user_model().objects.create_user('cc20', password='x')
        cls.usd_market = MarketDefinition.objects.get(scenario=cls.scenario, code='NA')  # USD
        profile = FirmStarterProfile.objects.filter(scenario=cls.scenario).first()
        cls.game = Game.objects.create(scenario=cls.scenario, name='CC20', created_by=cls.creator,
                                       status='active')
        cls.team = Team.objects.create(game=cls.game, name='FX', firm_starter_profile=profile,
                                       performance_index=D('100'), cash_on_hand=D('50000000'),
                                       total_equity=D('50000000'))

    def _ctx(self, r, usd_rate):
        Round.objects.get_or_create(game=self.game, round_number=r, defaults={'status': 'open'})
        ctx = _Ctx(self.game, r, [self.team], self.scenario)
        st = MarketEffectiveState(self.usd_market)
        st.effective_exchange_rate = usd_rate
        ctx.markets = {self.usd_market.id: st}
        ctx.market_revenue = {
            (self.team.id, self.usd_market.id): {'local_revenue': D('1000000'), 'market': self.usd_market},
        }
        return ctx

    def test_open_marktomarket_settle_gain(self):
        r1 = Round.objects.create(game=self.game, round_number=1, status='open')
        FXHedgeDecision.objects.create(team=self.team, round=r1, currency_pair='USD_CNY',
                                       hedge_ratio=100, tenor_days=90)  # 1 round tenor

        # Round 1: open at rate 1.0
        process_fx_hedges(self._ctx(1, 1.0))
        pos = HedgePosition.objects.get(team=self.team, currency_pair='USD_CNY')
        self.assertEqual(pos.status, 'open')
        self.assertEqual(pos.notional, D('1000000.00'))       # 100% of 1,000,000 USD receivables
        self.assertEqual(float(pos.locked_rate), 1.0)
        self.assertEqual(pos.mtm_current, D('0.00'))          # rate == locked at open
        self.assertEqual(pos.maturity_round.round_number, 2)

        # Round 2: USD weakens to 0.9 → receivables hedge gains, and it matures.
        ctx2 = self._ctx(2, 0.9)
        process_fx_hedges(ctx2)
        pos.refresh_from_db()
        self.assertEqual(pos.status, 'matured')
        self.assertEqual(pos.realized_pnl, D('100000.00'))    # 1,000,000 × (1.0 − 0.9)
        self.assertEqual(ctx2.sc_fx_hedge_pnl[self.team.id], D('100000.00'))

    def test_settle_loss_when_foreign_strengthens(self):
        r1 = Round.objects.create(game=self.game, round_number=1, status='open')
        FXHedgeDecision.objects.create(team=self.team, round=r1, currency_pair='USD_CNY',
                                       hedge_ratio=50, tenor_days=90)
        process_fx_hedges(self._ctx(1, 1.0))                  # open, notional = 500,000
        pos = HedgePosition.objects.get(team=self.team, currency_pair='USD_CNY')
        self.assertEqual(pos.notional, D('500000.00'))

        ctx2 = self._ctx(2, 1.1)                              # USD strengthens → hedge loses
        process_fx_hedges(ctx2)
        pos.refresh_from_db()
        self.assertEqual(pos.realized_pnl, D('-50000.00'))    # 500,000 × (1.0 − 1.1)
        self.assertEqual(ctx2.sc_fx_hedge_pnl[self.team.id], D('-50000.00'))

    def test_no_basis_currency_is_skipped(self):
        # JPY has no market in this scenario → no rate basis → no position.
        r1 = Round.objects.create(game=self.game, round_number=1, status='open')
        FXHedgeDecision.objects.create(team=self.team, round=r1, currency_pair='JPY_CNY',
                                       hedge_ratio=100, tenor_days=90)
        process_fx_hedges(self._ctx(1, 1.0))
        self.assertFalse(HedgePosition.objects.filter(team=self.team, currency_pair='JPY_CNY').exists())

    def test_realized_pnl_flows_into_net_income(self):
        """The settled FX P&L reaches the income statement (pre-tax, non-operating)."""
        from core.engine.financials import generate_financial_statements
        from core.models.results_financials import RoundResultFinancials
        Round.objects.get_or_create(game=self.game, round_number=3, defaults={'status': 'open'})
        ctx = _Ctx(self.game, 3, [self.team], self.scenario)
        # Everything else zero; only FX hedge P&L is non-zero.
        ctx.opex = {}; ctx.interest = {}; ctx.tax = {}
        ctx.cogs = {}; ctx.logistics = {}; ctx.inventory_costs = {}
        ctx.revenue = {}; ctx.market_revenue = {}
        ctx.sc_fx_hedge_pnl = {self.team.id: D('100000.00')}
        generate_financial_statements(ctx)
        fin = RoundResultFinancials.objects.get(game=self.game, team=self.team, round_number=3)
        self.assertEqual(fin.net_income, D('100000.00'))          # +FX gain, all else 0

    def test_zero_exposure_opens_nothing(self):
        r1 = Round.objects.create(game=self.game, round_number=1, status='open')
        FXHedgeDecision.objects.create(team=self.team, round=r1, currency_pair='USD_CNY',
                                       hedge_ratio=100, tenor_days=90)
        ctx = self._ctx(1, 1.0)
        ctx.market_revenue = {}   # no foreign receivables
        process_fx_hedges(ctx)
        self.assertFalse(HedgePosition.objects.filter(team=self.team).exists())

    def test_calibrated_ratio_matrix_has_no_dominant_hedge(self):
        """0/25/50/75/100% trade expected return for downside protection."""
        ratios = (0, 25, 50, 75, 100)
        rates = (D('0.8'), D('0.9'), D('1.0'), D('1.1'), D('1.2'))
        outcomes = {ratio: [] for ratio in ratios}

        for path_index, terminal_rate in enumerate(rates):
            game = Game.objects.create(
                scenario=self.scenario, name=f'FX matrix {path_index}',
                created_by=self.creator, status='active')
            r1 = Round.objects.create(game=game, round_number=1, status='open')
            teams = []
            for ratio in ratios:
                team = Team.objects.create(
                    game=game, name=f'FX {ratio}',
                    firm_starter_profile=self.team.firm_starter_profile,
                    performance_index=D('100'), cash_on_hand=D('50000000'),
                    total_equity=D('50000000'))
                teams.append(team)
                FXHedgeDecision.objects.create(
                    team=team, round=r1, currency_pair='USD_CNY',
                    hedge_ratio=ratio, tenor_days=90)

            def context(round_number, rate):
                Round.objects.get_or_create(
                    game=game, round_number=round_number,
                    defaults={'status': 'open'})
                ctx = _Ctx(game, round_number, teams, self.scenario)
                state = MarketEffectiveState(self.usd_market)
                state.effective_exchange_rate = rate
                ctx.markets = {self.usd_market.id: state}
                ctx.market_revenue = {
                    (team.id, self.usd_market.id): {
                        'local_revenue': D('1000000'),
                        'market': self.usd_market,
                    } for team in teams
                }
                return ctx

            opened = context(1, D('1.0'))
            process_fx_hedges(opened)
            settled = context(2, terminal_rate)
            process_fx_hedges(settled)
            for team, ratio in zip(teams, ratios):
                # Economic value of the receivable plus opening premium and
                # settlement P&L, all generated by the production engine.
                outcomes[ratio].append(
                    D('1000000') * terminal_rate
                    + opened.sc_fx_hedge_pnl.get(team.id, D('0'))
                    + settled.sc_fx_hedge_pnl.get(team.id, D('0')))

        self.assertEqual(outcomes[0], [
            D('800000'), D('900000'), D('1000000'), D('1100000'), D('1200000')])
        self.assertEqual(outcomes[100], [D('997500')] * 5)
        winners = [max(ratios, key=lambda ratio: outcomes[ratio][i])
                   for i in range(len(rates))]
        self.assertEqual(winners, [100, 100, 0, 0, 0])
