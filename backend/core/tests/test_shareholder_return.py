"""W-CE-14: "Shareholder return 999,966.5 %" after one ordinary round.

The walkthrough's team had a $33 share price and paid $0.50 a share, and its
results page showed a cumulative shareholder return of 9999.665 -- the API
figure, which the page multiplies by 100. Nothing was mis-scaled on the page:
the stored number was wrong.

`generate_financial_statements` computed

    (share_price + cumulative_dividends - initial_share_price) / initial_share_price

with `cumulative_dividends` the sum of `dividends_paid`, which is the money
the team paid out -- $500,000 for a million shares at $0.50 -- added to a
per-share price. $500,000 of dividends against a $50 base is 9,999.665, to
four places, which is the number on the screen. It also measured against
`starting_cash / 1,000,000` -- the cash the scenario gives, spread over a
million shares -- rather than against the share price the team was shown at
the start of the game (`bootstrap` publishes `total_equity / shares` as the
round-0 price, which differs whenever a starter profile carries debt).

The return is a per-share quantity throughout: dividends are counted per
share, and the base is the round-0 price the team saw, with the old
`starting_cash / 1,000,000` kept only for a game that has no round-0 row.

`financials.shareholder_return_cumulative` is in the hashed `financials`
section, so a round that pays a dividend now resolves to a different
competitive hash than it did before this change. No section changes shape.
"""
from decimal import ROUND_HALF_UP, Decimal as D

from django.test import TestCase
from django.utils import timezone

from core.engine.utils import _config_cache
from core.models import DecisionSubmission, Round
from core.models.decisions import (DecisionBudgetAllocation,
                                   DecisionFinancing)
from core.models.results_financials import RoundResultFinancials
from core.tests.test_operator_concurrency import build_minimal_game

DIVIDEND_PER_SHARE = D('0.50')
ROUND_ZERO_PRICE = D('0.8000')   # what the team saw: not starting_cash / 1e6


def _q(value):
    return value.quantize(D('0.0001'), rounding=ROUND_HALF_UP)


class ShareholderReturnTests(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, self.teams = build_minimal_game(f'sr-{id(self)}')
        self.team, self.rival = self.teams
        self.round, _ = Round.objects.get_or_create(
            game=self.game, round_number=1,
            defaults={'status': 'closed', 'opened_at': timezone.now(),
                      'deadline': timezone.now()})
        for team in self.teams:
            submission = DecisionSubmission.objects.create(
                team=team, round=self.round, status='locked')
            DecisionBudgetAllocation.objects.create(
                submission=submission, rd_budget=D('0'), marketing_budget=D('0'),
                strategy_budget=D('0'), research_budget=D('0'))
            DecisionFinancing.objects.create(
                submission=submission,
                dividend_per_share=(DIVIDEND_PER_SHARE if team is self.team
                                    else D('0')))

    def publish_round_zero(self, price):
        for team in self.teams:
            RoundResultFinancials.objects.create(
                game=self.game, round_number=0, team=team,
                cash_closing=team.cash_on_hand, total_equity=team.total_equity,
                share_price=price)

    def resolve(self):
        from core.engine.advance_round import process_round
        process_round(self.game.id)

    def statement(self, team):
        return RoundResultFinancials.objects.get(
            game=self.game, round_number=1, team=team)

    def test_dividends_are_counted_per_share_against_the_published_starting_price(self):
        self.publish_round_zero(ROUND_ZERO_PRICE)
        self.resolve()
        mine = self.statement(self.team)
        self.team.refresh_from_db()

        # What the team paid out, in dollars, and what that is per share.
        shares = D(str(self.team.shares_outstanding))
        self.assertEqual(mine.dividends_paid, _q(DIVIDEND_PER_SHARE * shares))
        per_share = mine.dividends_paid / shares

        expected = _q((mine.share_price + per_share - ROUND_ZERO_PRICE)
                      / ROUND_ZERO_PRICE)
        self.assertEqual(mine.shareholder_return_cumulative, expected)
        # An ordinary round is an ordinary return, not tens of thousands.
        self.assertLess(abs(mine.shareholder_return_cumulative), D('10'))

    def test_the_dividend_is_the_only_difference_between_the_two_teams(self):
        """The rival is the control: same base, same price, no dividend."""
        self.publish_round_zero(ROUND_ZERO_PRICE)
        self.resolve()
        mine, control = self.statement(self.team), self.statement(self.rival)
        self.team.refresh_from_db()

        per_share = mine.dividends_paid / D(str(self.team.shares_outstanding))
        # Paying the dividend lowers the price by what was paid and returns
        # it per share, so the two teams' returns differ by (per-share
        # dividend - price drop) / base -- to the four places stored.
        gap = _q((mine.share_price + per_share - control.share_price)
                 / ROUND_ZERO_PRICE)
        self.assertEqual(
            _q(mine.shareholder_return_cumulative
               - control.shareholder_return_cumulative),
            gap)

    def test_a_game_without_a_round_zero_row_keeps_the_old_base(self):
        """`starting_cash / 1,000,000` remains the base where nothing was
        published at round 0, so no existing game changes its base."""
        self.resolve()
        mine = self.statement(self.team)
        self.team.refresh_from_db()

        base = _q(self.game.scenario.starting_cash / D('1000000'))
        per_share = mine.dividends_paid / D(str(self.team.shares_outstanding))
        expected = _q((mine.share_price + per_share - base) / base)
        self.assertEqual(mine.shareholder_return_cumulative, expected)
