"""V2-020 — raising equity must resolve, and price off the right balance sheet.

`generate_financial_statements` priced new shares with `total_equity`, which is
not assigned until fifty lines later in the same per-team loop. The first team
to raise equity hit `UnboundLocalError`, and since the call runs inside
`_run_phase_1`, the round failed for everyone. Any later team silently used the
*previous* team's closing equity, pricing one company's shares off another's.

Nothing in the repository set `new_equity` above zero — every test and seed
command used `0` — so neither happened until Stage 2 screening varied the field.
These tests exist so that stays true.
"""
from decimal import Decimal as D

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.utils import timezone

from core.models import (DecisionSubmission, Game, Round, Scenario, Team)
from core.models.decisions import DecisionBudgetAllocation, DecisionFinancing
from core.models.scenario import FirmStarterProfile, MarketDefinition


class EquityIssuanceTests(TestCase):
    def setUp(self):
        owner = DjangoUser.objects.create(username=f'owner-eq-{id(self)}')
        self.scenario = Scenario.objects.create(
            name=f'Equity {id(self)}', industry_label='T', description='d',
            starting_cash=1000, num_rounds=4)
        market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HM', description='d',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='S', description='d',
            home_market=market, starting_cash=1000, starting_debt=0)
        self.game = Game.objects.create(
            scenario=self.scenario, name='Equity game', current_round=1,
            status='active', created_by=owner)
        self.round = Round.objects.create(
            game=self.game, round_number=1, status='open',
            opened_at=timezone.now())
        # Two teams with deliberately different equity, so pricing off the
        # wrong one is visible rather than a coincidence.
        self.first = Team.objects.create(
            game=self.game, name='First', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=D('1000000'),
            total_equity=D('1000000'), shares_outstanding=1000)
        self.second = Team.objects.create(
            game=self.game, name='Second', firm_starter_profile=profile,
            performance_index=100, cash_on_hand=D('50000000'),
            total_equity=D('50000000'), shares_outstanding=1000)

    def submit(self, team, new_equity=D('0')):
        sub, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=self.round, defaults={'status': 'draft'})
        DecisionBudgetAllocation.objects.filter(submission=sub).delete()
        DecisionBudgetAllocation.objects.create(
            submission=sub, rd_budget=D('0'), marketing_budget=D('0'),
            strategy_budget=D('0'), research_budget=D('0'))
        DecisionFinancing.objects.filter(submission=sub).delete()
        DecisionFinancing.objects.create(
            submission=sub, new_debt=D('0'), debt_repayment=D('0'),
            new_equity=new_equity, dividend_per_share=D('0'))
        sub.status = 'locked'
        sub.locked_at = timezone.now()
        sub.save(update_fields=['status', 'locked_at'])
        return sub

    def resolve(self):
        from core.engine.advance_round import _run_phase_1
        return _run_phase_1(self.game.id)

    def test_the_first_team_raising_equity_does_not_fail_the_round(self):
        """The crash: it took the whole game down, not just one team."""
        self.submit(self.first, new_equity=D('100000'))
        self.submit(self.second)
        self.resolve()  # must not raise

        from core.models import RoundResultFinancials
        self.assertEqual(
            RoundResultFinancials.objects.filter(
                game=self.game, round_number=1).count(), 2,
            'every team must still be scored')

    def test_shares_are_priced_off_the_issuing_team_s_own_equity(self):
        """The silent half: team two was priced with team one's balance sheet.

        `First` opens with $1,000,000 of equity over 1,000 shares — $1,000 a
        share. `Second` opens with $50,000,000 over 1,000 — $50,000 a share.
        Raising the same amount must therefore issue far fewer shares at
        `Second` than at `First`. Pricing off the wrong team inverts that.
        """
        raise_amount = D('1000000')
        self.submit(self.first, new_equity=raise_amount)
        self.submit(self.second, new_equity=raise_amount)
        self.resolve()

        self.first.refresh_from_db()
        self.second.refresh_from_db()
        first_new = self.first.shares_outstanding - 1000
        second_new = self.second.shares_outstanding - 1000

        self.assertGreater(first_new, 0, 'the cheaper company issued no shares')
        self.assertGreater(second_new, 0, 'the dearer company issued no shares')
        self.assertGreater(
            first_new, second_new,
            'the company with the lower share price must issue more shares for '
            'the same money; if it does not, the price came from elsewhere')

    def test_a_team_that_raises_nothing_is_unchanged(self):
        """The control."""
        self.submit(self.first)
        self.submit(self.second)
        self.resolve()
        self.first.refresh_from_db()
        self.assertEqual(self.first.shares_outstanding, 1000)

    def test_equity_is_not_priced_from_a_figure_computed_later(self):
        """Guards the shape of the bug, not just this instance.

        `total_equity` is the closing balance and is assigned after this point
        in the same loop. Reading any later-assigned name here reintroduces
        both failures at once.
        """
        import inspect
        from core.engine import financials
        source = inspect.getsource(financials.generate_financial_statements)
        pricing = source.split('subscription_rate = ')[1].split('new_shares')[0]
        self.assertNotIn('total_equity /', pricing,
                         'share pricing reads the closing equity again')
        self.assertIn('opening_equity', pricing)
