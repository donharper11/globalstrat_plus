"""W-CE2-03: the deadline executed the spend the lock had refused.

Aurora Devices was told, with the figures on the page before the click, that
it could not lock -- *Committed spend of $38,000,000.00 exceeds available
cash of $25,446,310.88* -- and could not clear the blocker because nothing
could withdraw the acquisition that caused it (W-CE2-02). When the deadline
closed the round, `_lock_all_submissions` locked the draft as it stood and
the engine charged the acquisition in full: `strategy_expense $37.95M`
against $23.4M of opening cash, and the round ended at **-$12,369,069.71**.

No ruling covers auto-lock at the deadline, and applying the whole lock
validator there would be wrong: most of its blockers are "this section is
empty", and a team that did nothing must still be resolved. What is
implemented here is the one rule the refusal itself names, in the one place
the engine already refuses a commitment for a team's financial condition:

    `acquisitions.process_acquisitions` already withholds an acquisition
    from a team in financial distress, and from a team whose target another
    team took, with a notification and "No cost has been charged" -- and
    `costs.calculate_operating_expenses` charges the base acquisition cost
    only for an acquisition that was actually fulfilled.

The same gate now covers affordability: a submission whose committed spend
exceeds the team's available cash -- `rd_costs.budget_assessment`, the exact
check whose sentence the lock refuses with -- does not have its acquisitions
fulfilled. It is uniform: a team that locked its own submission passed that
check at the lock, so the gate can only fire on a draft the lock would have
refused. Nothing is charged, nothing else in the round changes, and the
team's decision row survives as its record.

What this does NOT do is recorded for the owner in the completion report: a
draft made unaffordable by outlays other than an acquisition -- a plant
build, marketing -- still resolves and can still end a team in the red,
because those are charged from the decision row rather than from a
fulfilment the engine can withhold, and the V2-024 parity assertion holds
`decision_outlays` and `costs` to the same rows.
"""
from decimal import Decimal as D

from django.test import TestCase
from django.utils import timezone

from core.engine.utils import _config_cache
from core.models import DecisionSubmission, Round
from core.models.decisions import (DecisionAcquisition,
                                   DecisionBudgetAllocation)
from core.models.messaging import TeamNotification
from core.models.results_financials import RoundResultFinancials
from core.models.scenario import (AcquisitionTarget, EntryModeDefinition,
                                  MarketDefinition)
from core.models.team_state import TeamAcquisition, TeamMarketPresence
from core.tests.test_operator_concurrency import build_minimal_game

OPENING_CASH = D('1000000')      # what `build_minimal_game` gives a team
UNAFFORDABLE = D('1500000')      # more than the team holds
AFFORDABLE = D('400000')


class DeadlineAffordabilityBase(TestCase):

    def setUp(self):
        _config_cache.clear()
        self.addCleanup(_config_cache.clear)
        self.game, self.teams = build_minimal_game(f'da-{id(self)}')
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
                      'deadline': timezone.now()})
        self.submissions = {}
        for team in self.teams:
            submission = DecisionSubmission.objects.create(
                team=team, round=self.round, status='draft')
            DecisionBudgetAllocation.objects.create(
                submission=submission, rd_budget=D('0'),
                marketing_budget=D('0'), strategy_budget=D('0'),
                research_budget=D('0'))
            self.submissions[team.id] = submission

    def target(self, cost, name='Orbit'):
        return AcquisitionTarget.objects.create(
            scenario=self.scenario, market=self.home, target_name=name,
            description='d', base_acquisition_cost=cost,
            market_share_gained=D('0.05'), min_round_available=1,
            integration_rounds=1)

    def queue(self, target, team=None):
        return DecisionAcquisition.objects.create(
            submission=self.submissions[(team or self.team).id],
            acquisition_target=target)

    def close_and_process(self):
        """Exactly the deadline path: close the round, then resolve it."""
        from core.engine.advance_round import close_round, process_round
        close_round(self.game.id, reason='deadline')
        process_round(self.game.id)

    def statement(self, team=None):
        return RoundResultFinancials.objects.get(
            game=self.game, round_number=1, team=team or self.team)


class DeadlineDoesNotExecuteWhatTheLockRefusesTests(DeadlineAffordabilityBase):

    def test_the_lock_would_have_refused_this_draft(self):
        """The control: this is the sentence the walkthrough's team saw."""
        from core.views.decisions import lock_blockers_for
        self.queue(self.target(UNAFFORDABLE))

        blockers = lock_blockers_for(
            self.submissions[self.team.id], language='en')

        self.assertTrue(any('exceeds available funds' in b for b in blockers),
                        blockers)

    def test_the_acquisition_is_not_fulfilled_and_nothing_is_charged(self):
        target = self.target(UNAFFORDABLE)
        self.queue(target)

        self.close_and_process()

        self.assertFalse(TeamAcquisition.objects.filter(
            team=self.team, acquisition_target=target).exists())
        mine, control = self.statement(), self.statement(self.rival)
        self.assertEqual(mine.strategy_expense, control.strategy_expense)

    def test_the_team_does_not_end_the_round_in_the_red(self):
        self.queue(self.target(UNAFFORDABLE))

        self.close_and_process()

        self.team.refresh_from_db()
        self.assertGreaterEqual(self.team.cash_on_hand, D('0'))
        self.assertGreaterEqual(self.statement().cash_closing, D('0'))

    def test_the_team_is_told_why_and_that_nothing_was_charged(self):
        self.queue(self.target(UNAFFORDABLE))

        self.close_and_process()

        texts = list(TeamNotification.objects.filter(
            team_id=self.team.id).values_list('notification_text', flat=True))
        self.assertTrue(any('Orbit' in text for text in texts), texts)
        self.assertTrue(any('No cost has been charged' in text
                            for text in texts), texts)

    def test_the_decision_row_is_kept_as_the_teams_record(self):
        target = self.target(UNAFFORDABLE)
        self.queue(target)

        self.close_and_process()

        self.assertTrue(DecisionAcquisition.objects.filter(
            submission=self.submissions[self.team.id],
            acquisition_target=target).exists())


class AnAffordableAcquisitionIsUnaffectedTests(DeadlineAffordabilityBase):

    def test_a_deadline_locked_draft_the_lock_would_accept_still_acquires(self):
        target = self.target(AFFORDABLE)
        self.queue(target)

        self.close_and_process()

        self.assertTrue(TeamAcquisition.objects.filter(
            team=self.team, acquisition_target=target).exists())
        self.assertEqual(
            self.statement().strategy_expense
            - self.statement(self.rival).strategy_expense,
            AFFORDABLE)

    def test_a_team_that_locked_its_own_submission_is_unaffected(self):
        target = self.target(AFFORDABLE)
        self.queue(target)
        DecisionSubmission.objects.filter(
            pk=self.submissions[self.team.id].pk).update(
                status='locked', locked_at=timezone.now())

        self.close_and_process()

        self.assertTrue(TeamAcquisition.objects.filter(
            team=self.team, acquisition_target=target).exists())
