"""W-CE3-02 / W-CE-23's remainder: a team must always be able to lock a round.

The third walkthrough resolved six rounds and **no team locked a round after
round 3**. Two of the four playing teams went cash-negative at round 4 and were
deadline-closed in every round afterwards; they never submitted a decision
again. The cause, in one line: the affordability blocker compared committed
spend with *cash on hand*, and once a team's cash is negative no spend can ever
be small enough. Driven on Nova Circuit at round 4 with cash -$7,431,324.09 and
every declared budget zeroed, the Summary still refused --

    Committed spend of $8,800,000.00 exceeds available cash of $-7,431,324.09

-- and raising $30,000,000 of new debt did not move the available-cash figure
by a cent, because the check never read the financing row.

Integrator decision 13 under R48: **the lock must always be reachable.**
Available funds count the financing the team has already decided this round,
and the blocker names what the team can actually change. Standing commitments
a screen cannot reduce may not, by themselves, make the lock unreachable.

What the repair does NOT do, and each of these has a test below that fails if
it is weakened:

* it does not count money the round will refuse to hand over. A team in
  financial distress cannot raise new debt (`engine/financials`), so its debt
  is not counted here either; an equity raise is counted at the subscription
  rate the engine will actually apply;
* it does not weaken V2-024. `funding_requirement`'s `available_funding` is
  still opening cash plus new debt as submitted, so no team's maximum equity
  raise moves;
* it does not change a price, a cap or a competitive rule.
"""
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone

from core.engine.utils import _config_cache
from core.models import DecisionSubmission, Round
from core.models.decisions import (DecisionBudgetAllocation, DecisionESG,
                                   DecisionFinancing, DecisionMarketing,
                                   DecisionProductRetire)
from core.models.scenario import (EntryModeDefinition, MarketDefinition,
                                  PlatformGenerationDefinition)
from core.models.team_state import (TeamMarketPresence, TeamPlatform,
                                    TeamProduct, TeamProductMarket)
from core.services import funding_need
from core.services.rd_costs import budget_assessment
from core.tests.test_operator_concurrency import build_minimal_game

OPENING_CASH = D('1000000')     # what `build_minimal_game` gives a team
IN_THE_RED = D('-7431324.09')   # Nova Circuit's round-4 cash, to the cent
STANDING = D('200000')          # an ESG commitment already made this round


class LockReachableBase(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, self.teams = build_minimal_game(f'lr-{id(self)}')
        self.team, self.rival = self.teams
        self.scenario = self.game.scenario
        self.home = MarketDefinition.objects.get(
            scenario=self.scenario, code='HM')
        self.mode = EntryModeDefinition.objects.create(
            scenario=self.scenario, name='Export', code='EXPORT',
            description='d', capital_requirement=0, control_level=1,
            risk_level=1, local_presence_score=1)
        for team in self.teams:
            TeamMarketPresence.objects.create(
                team=team, market=self.home, entry_mode=self.mode,
                established_round=0, initial_investment=0, status='active')
        self.round, _ = Round.objects.get_or_create(
            game=self.game, round_number=1,
            defaults={'status': 'open', 'opened_at': timezone.now(),
                      'deadline': timezone.now() + timezone.timedelta(hours=4)})
        self.submission = DecisionSubmission.objects.create(
            team=self.team, round=self.round, status='draft')
        DecisionBudgetAllocation.objects.create(
            submission=self.submission, rd_budget=D('0'),
            marketing_budget=D('0'), strategy_budget=D('0'),
            research_budget=D('0'))
        # A submission the lock would otherwise accept, so that what is left
        # blocking it is the affordability rule and nothing else. Each of
        # these is a requirement `lock_blockers_for` states in its own right.
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen 1', description='d',
            generation_order=1, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)
        platform = TeamPlatform.objects.create(
            team=self.team, platform_generation=generation,
            name='Aurora platform', status='active',
            development_method='in_house', development_started_round=0,
            funded_round=0, development_rounds_remaining=0)
        self.product = TeamProduct.objects.create(
            team=self.team, team_platform=platform, name='Aurora',
            positioning='mainstream', status='active', created_round=0)
        TeamProductMarket.objects.create(
            team_product=self.product, market=self.home, first_offered_round=0)
        DecisionMarketing.objects.create(
            submission=self.submission, team_product=self.product,
            market=self.home, retail_price=D('400'), promotion_budget=D('0'),
            campaign_focus_feature_ids=[1], channel_digital_pct=D('0.34'),
            channel_traditional_pct=D('0.33'), channel_trade_pct=D('0.33'),
            distribution_strategy='mass_retail', distribution_investment=D('0'),
            sales_team_count=0, distribution_channel_detail={},
            production_volume=0, production_source_market=self.home,
            demand_estimate=0)
        DecisionProductRetire.objects.create(
            submission=self.submission, team_product=self.product,
            timing='end_of_round')
        self.client = self.client_for(self.team)

    def client_for(self, team):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        user = User.objects.create(
            username=f'lr-{id(self)}-{User.objects.count()}',
            role='student', password_hash='x')
        course = Course.objects.create(
            course_code=f'LR{id(self) % 10000}{Course.objects.count()}',
            course_name='LR', instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=user.user_id, section_id=section.section_id,
            team_id=team.id, is_active=True, enrolled_at=timezone.now())
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    @property
    def base(self):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/decisions/round/1/')

    def go_into_the_red(self, cash=IN_THE_RED, distressed=True):
        """The state a deadline-closed team opens the next round in."""
        self.team.cash_on_hand = cash
        self.team.is_in_distress = distressed
        self.team.save(update_fields=['cash_on_hand', 'is_in_distress'])

    def commit_something_standing(self, amount=STANDING):
        DecisionESG.objects.create(
            submission=self.submission, environmental_investment=amount,
            social_investment=D('0'))

    def finance(self, **fields):
        defaults = dict(new_debt=D('0'), new_equity=D('0'),
                        debt_repayment=D('0'), dividend_per_share=D('0'))
        defaults.update(fields)
        DecisionFinancing.objects.update_or_create(
            submission=self.submission, defaults=defaults)

    def assessment(self):
        self.team.refresh_from_db()
        return budget_assessment(self.submission, self.team)

    def blockers(self, language='en'):
        from core.views.decisions import lock_blockers_for
        self.team.refresh_from_db()
        return lock_blockers_for(self.submission, language=language)


class ANegativeCashTeamCanStillReachTheLockTests(LockReachableBase):

    def test_the_old_comparison_would_have_refused_whatever_was_raised(self):
        """The control: committed spend against cash on hand alone."""
        self.go_into_the_red(distressed=False)
        self.commit_something_standing()
        self.finance(new_debt=D('30000000'))

        assessment = self.assessment()

        self.assertLess(D(assessment['cash_on_hand']), D('0'))
        self.assertLess(D(assessment['committed_total']),
                        D(assessment['available_funds']))
        self.assertTrue(assessment['within_cash'])

    def test_financing_moves_the_available_figure(self):
        self.go_into_the_red(distressed=False)
        before = D(self.assessment()['available_funds'])
        self.finance(new_debt=D('30000000'))

        after = D(self.assessment()['available_funds'])

        self.assertEqual(after - before, D('30000000'))
        self.assertEqual(D(self.assessment()['financing_decided']),
                         D('30000000'))

    def test_a_team_in_the_red_that_raises_enough_can_lock(self):
        self.go_into_the_red(distressed=False)
        self.commit_something_standing()
        # Exactly the gap: the cash back to zero plus the $200,000 standing
        # commitment. Funded with equity, which is what V2-024 allows this
        # team to raise and no more -- $7.6M of debt against $1M of equity
        # would breach the debt ceiling, a different rule that still holds.
        self.finance(new_equity=-IN_THE_RED + STANDING)

        self.assertEqual(self.blockers(), [])
        response = self.client.post(f'{self.base}lock/', format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'locked')

    def test_a_team_that_raises_nothing_is_refused_and_told_what_to_change(self):
        self.go_into_the_red(distressed=False)
        self.commit_something_standing()
        self.finance()

        blockers = self.blockers()

        self.assertTrue(blockers)
        sentence = next(b for b in blockers if 'available funds' in b)
        # The figure it is refused against, the financing counted, and the one
        # line the team can actually cut -- decision 13's requirement.
        self.assertIn('$0.00 of financing decided this round', sentence)
        self.assertIn('the strategy budget', sentence)
        self.assertIn(f'${STANDING:,.2f}', sentence)

    def test_with_nothing_left_to_cut_the_refusal_names_the_raise_needed(self):
        self.go_into_the_red(distressed=False)
        self.finance()

        blockers = self.blockers()

        sentence = next(b for b in blockers if 'Available funds' in b)
        self.assertIn('Nothing committed can be cut any further', sentence)
        self.assertIn(f'${-IN_THE_RED:,.2f}', sentence)

    def test_the_zero_dividend_blocker_does_not_fire_on_a_zero_dividend(self):
        """W-CE3-16, the same dead end: nothing is below zero to reduce to."""
        self.go_into_the_red(distressed=False)
        self.finance(new_equity=-IN_THE_RED)
        self.team.total_equity = D('-5000000')
        self.team.save(update_fields=['total_equity'])

        self.assertEqual(
            [b for b in self.blockers() if 'dividend' in b.lower()], [])

    def test_there_is_a_raise_that_clears_every_blocker(self):
        """Decision 13, stated as the property: no unreachable state."""
        self.go_into_the_red(distressed=False)
        self.commit_something_standing()
        for raise_amount in (D('0'), D('100000'), -IN_THE_RED + STANDING):
            self.finance(new_equity=raise_amount)
            remaining = self.blockers()
            if raise_amount == -IN_THE_RED + STANDING:
                self.assertEqual(remaining, [], remaining)
            else:
                self.assertTrue(remaining)


class MoneyTheRoundWillNotHandOverIsNotCountedTests(LockReachableBase):
    """The counter-rule. Counting a refused raise is the same defect."""

    def test_new_debt_is_not_counted_for_a_team_in_distress(self):
        self.go_into_the_red(distressed=True)
        self.finance(new_debt=D('30000000'))

        assessment = self.assessment()

        self.assertEqual(D(assessment['financing_decided']), D('0'))
        self.assertTrue(assessment['debt_refused_in_distress'])

    def test_the_team_is_told_why_its_debt_did_not_count(self):
        self.go_into_the_red(distressed=True)
        self.commit_something_standing()
        self.finance(new_debt=D('30000000'))

        blockers = self.blockers()

        self.assertTrue(any('financial distress' in b for b in blockers),
                        blockers)
        self.assertTrue(any('Raise equity instead' in b for b in blockers),
                        blockers)

    def test_equity_still_reaches_a_distressed_team_and_clears_the_lock(self):
        self.go_into_the_red(distressed=True)
        self.commit_something_standing()
        self.finance(new_equity=-IN_THE_RED + STANDING)

        assessment = self.assessment()

        self.assertGreater(D(assessment['financing_decided']), D('0'))
        self.assertTrue(assessment['within_cash'])
        self.assertEqual(self.blockers(), [])

    def test_the_subscription_the_engine_will_apply_is_published(self):
        """Counted at the decided amount; what will arrive is still stated.

        V2-024 caps the raise at the shortfall itself, so netting the equity
        subscription haircut inside available funds would make that gap
        uncloseable by equity -- the dead end decision 13 forbids. The
        subscribed figure is published instead, so a screen can warn where it
        must not refuse.
        """
        from core.engine.financials import subscription_rate
        self.go_into_the_red(distressed=False)
        self.finance(new_equity=D('1000000'))

        assessment = self.assessment()
        rate = D(str(subscription_rate(self.team, self.game, 1)))

        self.assertEqual(D(assessment['financing_decided']), D('1000000'))
        self.assertEqual(D(assessment['new_equity']),
                         (D('1000000') * rate).quantize(D('0.01')))
        self.assertLess(D(assessment['new_equity']), D('1000000'))

    def test_a_repayment_larger_than_the_debt_is_capped_as_the_engine_caps_it(self):
        self.team.total_debt = D('500000')
        self.team.save(update_fields=['total_debt'])
        self.finance(debt_repayment=D('900000'))

        assessment = self.assessment()

        # Only the $500,000 it actually owes leaves.
        self.assertEqual(D(assessment['available_funds']),
                         OPENING_CASH - D('500000'))


class TheEquityFundingRuleIsUnchangedTests(LockReachableBase):
    """V2-024 may not be widened by this repair."""

    def test_the_maximum_raise_still_reads_cash_plus_new_debt_only(self):
        self.commit_something_standing()
        self.finance(new_debt=D('250000'), new_equity=D('100000'))

        requirement = funding_need.assess_submission(self.submission)

        self.assertEqual(D(requirement['available_funding']),
                         OPENING_CASH + D('250000'))
        self.assertEqual(D(requirement['eligible_uses']), STANDING)
        self.assertEqual(D(requirement['maximum_new_equity']), D('0'))
        self.assertFalse(requirement['within_limit'])

    def test_an_over_large_raise_is_still_a_blocker(self):
        self.commit_something_standing()
        self.finance(new_equity=D('50000000'))

        self.assertTrue(any('exceeds the funding shortfall' in b
                            for b in self.blockers()), self.blockers())


class TheChineseRefusalTests(LockReachableBase):

    def test_the_refusal_is_in_the_readers_language(self):
        self.go_into_the_red(distressed=False)
        self.commit_something_standing()
        self.finance()

        blockers = self.blockers(language='zh-CN')

        sentence = next(b for b in blockers if '可用资金' in b)
        self.assertIn('战略预算', sentence)
        self.assertNotIn('available funds', sentence)

    def test_the_nothing_left_to_cut_refusal_is_translated(self):
        self.go_into_the_red(distressed=False)
        self.finance()

        blockers = self.blockers(language='zh-CN')

        self.assertTrue(any('无法再削减' in b for b in blockers), blockers)
