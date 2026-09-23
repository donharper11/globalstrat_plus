"""W-CE2-03's residue, decision 14: one affordability rule, two paths.

W-CE2-03 stopped the deadline fulfilling an *acquisition* the lock had refused.
Its own §7.1 disclosed what it did not do, and the third walkthrough then
measured it: a draft made unaffordable by a plant build or by marketing still
resolved in full, so Nova Circuit closed at **-$7,431,324.09** and Aurora
Devices at **-$6,468,269.34** on drafts the lock had refused with the figures
on the page. From there neither team could lock again (W-CE3-02), which is why
the two defects are one story.

Decision 13 has made the affordability rule satisfiable, so decision 14 applies
it here: `close_round` withdraws the team's own discretionary commitments, in
the order `deadline_affordability.WITHDRAWAL_ORDER` states, until
`rd_costs.budget_assessment` -- the function the lock refuses on, and nothing
else -- says the draft fits.

Every test below is written against the real deadline path
(`close_round` then `process_round`), not against the service in isolation.
"""
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone

from core.engine.utils import _config_cache
from core.models import DecisionAuditEvent, DecisionSubmission, Round
from core.models.decisions import (DecisionBudgetAllocation, DecisionESG,
                                   DecisionFinancing, DecisionMarketing,
                                   DecisionPlant)
from core.models.messaging import TeamNotification
from core.models.results_financials import RoundResultFinancials
from core.models.scenario import (EntryModeDefinition, MarketDefinition,
                                  PlatformGenerationDefinition)
from core.models.team_state import (TeamMarketPresence, TeamPlant, TeamPlatform,
                                    TeamProduct, TeamProductMarket)
from core.tests.test_operator_concurrency import build_minimal_game

OPENING_CASH = D('1000000')     # what `build_minimal_game` gives a team
PLANT_COST = D('1500000')       # more than the team holds


class DeadlineRuleBase(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, self.teams = build_minimal_game(f'dm-{id(self)}')
        self.team, self.rival = self.teams
        self.scenario = self.game.scenario
        self.home = MarketDefinition.objects.get(
            scenario=self.scenario, code='HM')
        # A market a plant can actually be built in, so the negative tests
        # below are not passing because nothing would have been built anyway.
        self.home.plant_build_cost = PLANT_COST
        self.home.allows_manufacturing = True
        self.home.plant_capacity_units = 10000
        self.home.plant_build_rounds = 1
        self.home.save(update_fields=['plant_build_cost',
                                      'allows_manufacturing',
                                      'plant_capacity_units',
                                      'plant_build_rounds'])
        self.mode = EntryModeDefinition.objects.create(
            scenario=self.scenario, name='Export', code='EXPORT',
            description='d', capital_requirement=0, control_level=1,
            risk_level=1, local_presence_score=1)
        generation = PlatformGenerationDefinition.objects.create(
            scenario=self.scenario, name='Gen 1', description='d',
            generation_order=1, unlock_round=0,
            development_cost=D('1000000'), license_cost=D('2000000'),
            development_rounds=1)
        self.round, _ = Round.objects.get_or_create(
            game=self.game, round_number=1,
            defaults={'status': 'open', 'opened_at': timezone.now(),
                      'deadline': timezone.now()})
        self.submissions = {}
        for team in self.teams:
            TeamMarketPresence.objects.create(
                team=team, market=self.home, entry_mode=self.mode,
                established_round=0, initial_investment=0, status='active')
            platform = TeamPlatform.objects.create(
                team=team, platform_generation=generation,
                name=f'{team.name} platform', status='active',
                development_method='in_house', development_started_round=0,
                funded_round=0, development_rounds_remaining=0)
            product = TeamProduct.objects.create(
                team=team, team_platform=platform, name=f'{team.name} One',
                positioning='mainstream', status='active', created_round=0)
            TeamProductMarket.objects.create(
                team_product=product, market=self.home, first_offered_round=0)
            submission = DecisionSubmission.objects.create(
                team=team, round=self.round, status='draft')
            DecisionBudgetAllocation.objects.create(
                submission=submission, rd_budget=D('0'),
                marketing_budget=D('0'), strategy_budget=D('0'),
                research_budget=D('0'))
            DecisionFinancing.objects.create(submission=submission)
            DecisionMarketing.objects.create(
                submission=submission, team_product=product, market=self.home,
                retail_price=D('400'), promotion_budget=D('0'),
                campaign_focus_feature_ids=[1], channel_digital_pct=D('0.34'),
                channel_traditional_pct=D('0.33'),
                channel_trade_pct=D('0.33'), distribution_strategy='mass_retail',
                distribution_investment=D('0'), sales_team_count=0,
                distribution_channel_detail={}, production_volume=0,
                production_source_market=self.home, demand_estimate=0)
            self.submissions[team.id] = submission
            self.products = getattr(self, 'products', {})
            self.products[team.id] = product

    def submission(self, team=None):
        return self.submissions[(team or self.team).id]

    def queue_plant(self, team=None):
        return DecisionPlant.objects.create(
            submission=self.submission(team), market=self.home,
            action='build', capacity_units=10000)

    def spend_on_marketing(self, amount, team=None):
        row = self.submission(team).marketing_decisions.first()
        row.promotion_budget = amount
        row.save(update_fields=['promotion_budget'])
        return row

    def blockers(self, team=None):
        from core.views.decisions import lock_blockers_for
        return lock_blockers_for(self.submission(team), language='en')

    def close_and_process(self):
        from core.engine.advance_round import close_round, process_round
        result = close_round(self.game.id, reason='deadline')
        process_round(self.game.id)
        return result

    def statement(self, team=None):
        return RoundResultFinancials.objects.get(
            game=self.game, round_number=1, team=team or self.team)


class ThePlantBuildResidueTests(DeadlineRuleBase):
    """The case W-CE2-03 disclosed and could not close."""

    def test_the_lock_refuses_this_draft(self):
        """The control, and the sentence the walkthrough's team read."""
        self.queue_plant()

        self.assertTrue(
            any('exceeds available funds' in b for b in self.blockers()),
            self.blockers())

    def test_the_deadline_does_not_build_the_plant(self):
        self.queue_plant()

        self.close_and_process()

        self.assertFalse(TeamPlant.objects.filter(
            team=self.team, market=self.home).exists())

    def test_nothing_is_charged_for_the_withdrawn_build(self):
        self.queue_plant()

        self.close_and_process()

        mine, control = self.statement(), self.statement(self.rival)
        self.assertEqual(mine.investing_cash_flow,
                         control.investing_cash_flow)

    def test_the_team_does_not_close_the_round_in_the_red(self):
        self.queue_plant()

        self.close_and_process()

        self.team.refresh_from_db()
        self.assertGreaterEqual(self.team.cash_on_hand, D('0'))
        self.assertGreaterEqual(self.statement().cash_closing, D('0'))

    def test_the_team_is_told_what_was_withdrawn_and_that_nothing_was_charged(self):
        self.queue_plant()

        self.close_and_process()

        texts = list(TeamNotification.objects.filter(
            team_id=self.team.id).values_list('notification_text', flat=True))
        self.assertTrue(any('plant construction' in t for t in texts), texts)
        self.assertTrue(
            any('nothing was charged for them' in t for t in texts), texts)

    def test_the_withdrawal_is_on_the_audit_trail_as_a_system_action(self):
        self.queue_plant()

        self.close_and_process()

        event = DecisionAuditEvent.objects.filter(
            team=self.team,
            action='deadline_withdrew_commitments').first()
        self.assertIsNotNone(event)
        self.assertIsNone(event.user)
        self.assertEqual(event.endpoint, 'engine:close_round')
        self.assertEqual(
            [step['step'] for step in event.payload['withdrawn']],
            ['plant_builds'])


class TheMarketingResidueTests(DeadlineRuleBase):
    """The other half of §7.1: an overspend made of promotion budget."""

    def test_the_promotion_budget_is_withdrawn_and_not_charged(self):
        self.spend_on_marketing(D('1500000'))

        self.close_and_process()

        mine, control = self.statement(), self.statement(self.rival)
        self.assertEqual(mine.marketing_expense, control.marketing_expense)
        self.team.refresh_from_db()
        self.assertGreaterEqual(self.team.cash_on_hand, D('0'))


class OnlyAsMuchAsNeededIsWithdrawnTests(DeadlineRuleBase):
    """The rule stops the moment the draft fits. It is not a punishment."""

    def test_an_affordable_draft_is_untouched(self):
        self.spend_on_marketing(D('400000'))
        DecisionESG.objects.create(
            submission=self.submission(), environmental_investment=D('50000'),
            social_investment=D('0'))

        self.close_and_process()

        self.assertEqual(self.statement().marketing_expense, D('400000'))
        self.assertFalse(DecisionAuditEvent.objects.filter(
            team=self.team,
            action='deadline_withdrew_commitments').exists())

    def test_the_first_step_that_makes_it_fit_is_the_last_one_applied(self):
        """A plant is withdrawn; the ESG and promotion behind it survive."""
        self.queue_plant()
        self.spend_on_marketing(D('300000'))
        DecisionESG.objects.create(
            submission=self.submission(), environmental_investment=D('100000'),
            social_investment=D('0'))

        self.close_and_process()

        event = DecisionAuditEvent.objects.get(
            team=self.team,
            action='deadline_withdrew_commitments')
        self.assertEqual([s['step'] for s in event.payload['withdrawn']],
                         ['plant_builds'])
        self.assertEqual(self.statement().marketing_expense, D('300000'))
        self.assertEqual(self.submission().esg.environmental_investment,
                         D('100000'))

    def test_a_team_that_locked_its_own_submission_is_never_touched(self):
        self.spend_on_marketing(D('400000'))
        DecisionSubmission.objects.filter(pk=self.submission().pk).update(
            status='locked', locked_at=timezone.now())

        self.close_and_process()

        self.assertEqual(self.statement().marketing_expense, D('400000'))
        self.assertFalse(DecisionAuditEvent.objects.filter(
            team=self.team,
            action='deadline_withdrew_commitments').exists())

    def test_financing_the_team_decided_is_counted_before_anything_is_cut(self):
        """Decision 13 and 14 are one rule: the deadline reads the same funds."""
        self.queue_plant()
        DecisionFinancing.objects.filter(
            submission=self.submission()).update(new_debt=D('1000000'))

        self.close_and_process()

        self.assertTrue(TeamPlant.objects.filter(
            team=self.team, market=self.home).exists())


class NothingLeftToWithdrawTests(DeadlineRuleBase):
    """A team whose available funds are simply negative."""

    def test_the_round_still_closes_and_resolves(self):
        self.team.cash_on_hand = D('-500000')
        self.team.save(update_fields=['cash_on_hand'])
        self.spend_on_marketing(D('100000'))

        result = self.close_and_process()

        self.assertEqual(result['status'], 'closed')
        self.round.refresh_from_db()
        self.assertEqual(self.round.status, 'processed')

    def test_it_is_closed_with_nothing_discretionary_in_it(self):
        self.team.cash_on_hand = D('-500000')
        self.team.save(update_fields=['cash_on_hand'])
        self.spend_on_marketing(D('100000'))

        self.close_and_process()

        self.assertEqual(self.statement().marketing_expense, D('0'))
        event = DecisionAuditEvent.objects.get(
            team=self.team,
            action='deadline_withdrew_commitments')
        self.assertFalse(event.payload['within_available_funds'])


class TheAcquisitionGateIsUnchangedTests(DeadlineRuleBase):
    """W-CE2-03's mechanism keeps its own job, and its decision row."""

    def target(self, cost):
        from core.models.scenario import AcquisitionTarget
        return AcquisitionTarget.objects.create(
            scenario=self.scenario, market=self.home, target_name='Orbit',
            description='d', base_acquisition_cost=cost,
            market_share_gained=D('0.05'), min_round_available=1,
            integration_rounds=1)

    def test_an_unaffordable_bid_is_still_withheld_with_its_row_kept(self):
        from core.models.decisions import DecisionAcquisition
        from core.models.team_state import TeamAcquisition
        target = self.target(D('1500000'))
        DecisionAcquisition.objects.create(
            submission=self.submission(), acquisition_target=target)

        self.close_and_process()

        self.assertFalse(TeamAcquisition.objects.filter(
            team=self.team, acquisition_target=target).exists())
        self.assertTrue(DecisionAcquisition.objects.filter(
            submission=self.submission(),
            acquisition_target=target).exists())

    def test_nothing_else_is_withdrawn_to_pay_for_a_bid_that_will_not_happen(self):
        from core.models.decisions import DecisionAcquisition
        target = self.target(D('1500000'))
        DecisionAcquisition.objects.create(
            submission=self.submission(), acquisition_target=target)
        self.spend_on_marketing(D('300000'))

        self.close_and_process()

        self.assertEqual(self.statement().marketing_expense, D('300000'))
        self.assertFalse(DecisionAuditEvent.objects.filter(
            team=self.team,
            action='deadline_withdrew_commitments').exists())


class TheChineseNoticeTests(DeadlineRuleBase):

    def test_the_team_is_told_in_its_own_language(self):
        from core.models import User
        from core.models.course import Course, Enrollment, Section
        user = User.objects.create(
            username=f'dm-zh-{id(self)}', role='student', password_hash='x')
        course = Course.objects.create(
            course_code=f'DM{id(self) % 10000}', course_name='DM',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        Enrollment.objects.create(
            user_id=user.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True, language='zh-CN',
            enrolled_at=timezone.now())
        self.queue_plant()

        self.close_and_process()

        texts = list(TeamNotification.objects.filter(
            team_id=self.team.id).values_list('notification_text', flat=True))
        self.assertTrue(any('工厂建设' in t for t in texts), texts)
        self.assertTrue(any('未产生任何费用' in t for t in texts), texts)
