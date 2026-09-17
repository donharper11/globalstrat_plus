"""R32 — the inactivity control enforces on the standings, not the carried index.

Owner ruling R32 (2026-09-17), `handoff_readiness_v2/OWNER_RULINGS_2026-09-17.md`:

    Keep the classification and keep the rule that an inactive firm must not
    outrank one that competed — but enforce it on the standings, not by
    overwriting the team's carried score.

Before R32, `performance.py::_enforce_inactive_revenue_invariant` replaced a
commercially inactive firm's carried performance index with
`min(active indexes) − 0.01`. That is not a cap on the round's change: the drop
was bounded only by how far the firm had climbed above the weakest rival still
competing, so on one identical event a leader lost **17.81** points where a
mid-table firm lost **5.00** (V2-110 Part D, V2-119). The strongest single
decision lever measured anywhere in this programme is worth about 12.40, so the
control could decide a competition on one round — the V2-024 class of defect.

What these tests hold, in the order the ruling states them:

1. **The anti-free-rider property survives** (V2-021 / V2-022). A commercially
   inactive firm never finishes above a firm that competed, however far ahead
   it was carrying. It is now enforced where a finishing order actually lives —
   `leaderboard.py`'s published sort key — instead of by rewriting a score.
2. **Severity no longer scales with success.** The same event costs a leader
   and a mid-table firm the same bounded amount.
3. **The composite cap is untouched**: still 0.25, still exactly −5.00 on the
   round. R32 changes only the second control.
4. **The standings are insertion-order invariant** (V2-012). The old guard
   compared against a `min(active_indexes)` captured before it began mutating;
   the replacement derives from a set membership test and mutates nothing.
"""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.engine.leaderboard import update_leaderboard
from core.engine.performance import (
    COMMERCIAL_INACTIVITY_COMPOSITE_CAP, calculate_performance_index,
)
from core.models.core import Game, Team
from core.models.results_financials import (
    LeaderboardEntry, RoundResultPerformanceIndex,
)
from core.models.scenario import FirmStarterProfile, MarketDefinition, Scenario
from core.tests.test_scoring_dispositions import ScoringFixture


def _context(**attributes):
    """A resolution context stub carrying only what the step under test reads."""
    return type('Ctx', (), attributes)()


class StandingsFixture(TestCase):
    """A minimal game whose ranking inputs are all explicit."""

    def setUp(self):
        user = get_user_model().objects.create_user(f'r32-{id(self)}')
        self.scenario = Scenario.objects.create(
            name=f'R32 standings {id(self)}', industry_label='T',
            description='d', starting_cash=1000)
        self.market = MarketDefinition.objects.create(
            scenario=self.scenario, name='Home', code='HOME',
            currency_code='USD', exchange_rate_base=1, base_growth_rate=0,
            entry_cost_base=0, tax_rate=0, regulatory_difficulty=1,
            infrastructure_quality=1)
        self.profile = FirmStarterProfile.objects.create(
            scenario=self.scenario, profile_name='S', description='d',
            home_market=self.market, starting_cash=1000, starting_debt=0)
        self.game = Game.objects.create(
            scenario=self.scenario, name='R32 game', created_by=user,
            status='active', current_round=4)

    def _team(self, name, index):
        return Team.objects.create(
            game=self.game, name=name, firm_starter_profile=self.profile,
            performance_index=D(index), cash_on_hand=D('1000'),
            total_equity=D('1000'))

    def _rank(self, teams, inactive, round_number=4):
        """Run the ranking step and return {team name: rank}."""
        context = _context(
            game=self.game, scenario=self.scenario, round_number=round_number,
            teams=list(teams), financials={}, log=[],
            commercially_inactive_team_ids=frozenset(t.id for t in inactive),
        )
        update_leaderboard(context)
        return {
            entry.team.name: entry.rank
            for entry in LeaderboardEntry.objects.filter(
                game=self.game, round_number=round_number,
            ).select_related('team')
        }


class InactiveFirmNeverOutranksAnActiveOne(StandingsFixture):
    """V2-021 / V2-022's anti-free-rider property, proven on the standings."""

    def test_a_far_ahead_inactive_firm_ranks_below_the_firm_that_competed(self):
        leader = self._team('inactive-leader', '90.00')
        rival = self._team('active-rival', '60.00')

        ranks = self._rank([leader, rival], inactive=[leader])

        self.assertEqual(ranks['active-rival'], 1)
        self.assertEqual(ranks['inactive-leader'], 2)

    def test_the_inactive_firm_keeps_the_index_it_carried(self):
        """The property is enforced on rank; the score is not rewritten."""
        leader = self._team('inactive-leader', '90.00')
        rival = self._team('active-rival', '60.00')

        self._rank([leader, rival], inactive=[leader])

        leader.refresh_from_db()
        self.assertEqual(leader.performance_index, D('90.00'))
        self.assertEqual(
            LeaderboardEntry.objects.get(
                game=self.game, round_number=4, team=leader,
            ).performance_index,
            D('90.00'),
            'the standings must publish the carried index, not a rewritten one')

    def test_every_active_firm_outranks_every_inactive_firm(self):
        """Interleaved indexes: the partition must be total, not per-pair."""
        teams = [
            self._team('inactive-top', '95.00'),
            self._team('active-second', '80.00'),
            self._team('inactive-third', '70.00'),
            self._team('active-fourth', '65.00'),
            self._team('inactive-fifth', '50.00'),
            self._team('active-last', '10.00'),
        ]
        inactive = [teams[0], teams[2], teams[4]]

        ranks = self._rank(teams, inactive=inactive)

        worst_active = max(ranks[t.name] for t in teams if t not in inactive)
        best_inactive = min(ranks[t.name] for t in inactive)
        self.assertLess(
            worst_active, best_inactive,
            'a firm that did not compete finished above one that did')
        self.assertEqual(
            [name for name, _rank in sorted(ranks.items(), key=lambda kv: kv[1])],
            ['active-second', 'active-fourth', 'active-last',
             'inactive-top', 'inactive-third', 'inactive-fifth'])

    def test_an_inactive_firm_does_not_even_share_a_rank(self):
        """Every published criterion equal: it still must not finish level."""
        idle = self._team('idle', '60.00')
        competed = self._team('competed', '60.00')

        ranks = self._rank([idle, competed], inactive=[idle])

        self.assertEqual(ranks['competed'], 1)
        self.assertEqual(ranks['idle'], 2)

    def test_a_field_with_no_active_firm_is_ranked_on_the_published_key(self):
        """Nobody competed: there is no active firm to protect, so rank normally."""
        first = self._team('high', '80.00')
        second = self._team('low', '40.00')

        ranks = self._rank([first, second], inactive=[first, second])

        self.assertEqual(ranks['high'], 1)
        self.assertEqual(ranks['low'], 2)

    def test_a_context_with_no_classification_demotes_nobody(self):
        """Round zero ranks before any round is played, so nothing is inactive.

        `bootstrap_round_zero` reaches the standings without running the
        performance step, and R22 requires every team to open on a shared rank.
        """
        first = self._team('alpha', '55.00')
        second = self._team('beta', '55.00')
        context = _context(
            game=self.game, scenario=self.scenario, round_number=0,
            teams=[first, second], financials={}, log=[])

        update_leaderboard(context)

        self.assertEqual(
            set(LeaderboardEntry.objects.filter(
                game=self.game, round_number=0,
            ).values_list('rank', flat=True)),
            {1})


class StandingsAreInsertionOrderInvariant(StandingsFixture):
    """V2-012. The replacement must not depend on the order teams arrive in."""

    def test_reversing_the_team_order_does_not_change_a_rank(self):
        teams = [
            self._team('inactive-top', '95.00'),
            self._team('active-second', '80.00'),
            self._team('inactive-third', '70.00'),
            self._team('active-fourth', '65.00'),
        ]
        inactive = [teams[0], teams[2]]

        forward = self._rank(teams, inactive=inactive, round_number=4)
        reverse = self._rank(list(reversed(teams)), inactive=inactive,
                             round_number=5)

        self.assertEqual(forward, reverse)

    def test_the_classification_is_consumed_as_an_unordered_membership_test(self):
        """The order the inactive set is built in cannot reach the standings."""
        teams = [
            self._team('inactive-a', '90.00'),
            self._team('inactive-b', '85.00'),
            self._team('active', '20.00'),
        ]
        context_a = _context(
            game=self.game, scenario=self.scenario, round_number=6,
            teams=list(teams), financials={}, log=[],
            commercially_inactive_team_ids=frozenset(
                [teams[0].id, teams[1].id]))
        context_b = _context(
            game=self.game, scenario=self.scenario, round_number=7,
            teams=list(teams), financials={}, log=[],
            commercially_inactive_team_ids=frozenset(
                [teams[1].id, teams[0].id]))

        update_leaderboard(context_a)
        update_leaderboard(context_b)

        def ranks(round_number):
            return {
                entry.team.name: entry.rank
                for entry in LeaderboardEntry.objects.filter(
                    game=self.game, round_number=round_number,
                ).select_related('team')
            }

        self.assertEqual(ranks(6), ranks(7))
        self.assertEqual(ranks(6)['active'], 1)


class SeverityIsBoundedByTheCompositeCap(ScoringFixture):
    """R32's substance: the round-level consequence is the cap, and only the cap."""

    def _score(self, teams, revenues, round_number=1):
        context = _context(
            game=self.game, scenario=self.scenario, round_number=round_number,
            teams=list(teams), log=[], fit_scores={}, adjusted_fit_scores={},
            financials={
                team.id: {
                    'total_revenue': revenue,
                    'net_income': D('0'),
                    'debt_to_equity': D('0'),
                }
                for team, revenue in zip(teams, revenues)
            },
            compliance_freezes=set(), sc_capacity_factor={},
            sc_disruption_costs={},
        )
        calculate_performance_index(context)
        return context

    def _extra_team(self, name, index):
        return Team.objects.create(
            game=self.game, name=name,
            firm_starter_profile=self.team.firm_starter_profile,
            performance_index=D(index), cash_on_hand=D('1000'),
            total_equity=D('1000'))

    def _result(self, team, round_number=1):
        return RoundResultPerformanceIndex.objects.get(
            game=self.game, round_number=round_number, team=team)

    def test_one_event_costs_a_leader_and_a_mid_table_firm_the_same(self):
        """The measured 17.81-versus-5.00 asymmetry, on one identical event.

        Both firms are classified inactive by the same rule in the same round,
        so both take the composite cap and nothing else. Before R32 the leader
        was dropped to `min(active indexes) − 0.01` and the mid-table firm was
        dropped to the same place, so the *cost* of the identical event differed
        by the distance between them.
        """
        leader = self._extra_team('leader', '70.43')
        mid_table = self._extra_team('mid-table', '57.62')
        active = self._extra_team('active', '52.63')

        self._score([leader, mid_table, active],
                    [D('0'), D('0'), D('5000000')])

        leader_change = self._result(leader).index_change
        mid_change = self._result(mid_table).index_change
        self.assertEqual(leader_change, D('-5.00'))
        self.assertEqual(mid_change, D('-5.00'))
        self.assertEqual(
            leader_change, mid_change,
            'the same event must not cost more because the firm was ahead')

    def test_the_recorded_green_pioneer_event_now_costs_the_capped_five(self):
        """V2-110 Part D recorded 70.43 → 52.62 (−17.81) for this shape."""
        leader = self._extra_team('green-pioneer', '70.43')
        active = self._extra_team('active', '52.63')

        self._score([leader, active], [D('0'), D('5000000')])

        result = self._result(leader)
        self.assertEqual(result.index_value, D('65.43'))
        self.assertEqual(result.index_change, D('-5.00'))
        leader.refresh_from_db()
        self.assertEqual(leader.performance_index, D('65.43'))

    def test_the_carried_index_is_never_replaced_by_the_weakest_active_rival(self):
        """The specific mechanism R32 removed, asserted as absent."""
        idle = self._extra_team('idle', '88.00')
        active = self._extra_team('active', '31.00')

        self._score([idle, active], [D('0'), D('9000000')])

        active_index = self._result(active).index_value
        idle_index = self._result(idle).index_value
        self.assertNotEqual(idle_index, active_index - D('0.01'))
        self.assertGreater(
            idle_index, active_index,
            'the carried index is no longer pulled below the active field; '
            'the anti-free-rider property is enforced on rank instead')

    def test_the_composite_cap_still_applies_its_bounded_five_points(self):
        """R32 changes the second control only. The cap is as authored."""
        idle = self._extra_team('idle', '100.00')
        active = self._extra_team('active', '100.00')

        self._score([idle, active], [D('0'), D('7500000')])

        result = self._result(idle)
        self.assertEqual(result.satisfaction_score,
                         COMMERCIAL_INACTIVITY_COMPOSITE_CAP)
        self.assertEqual(result.index_change, D('-5.00'))
        self.assertEqual(result.index_value, D('95.00'))

    def test_the_cap_is_the_whole_round_level_consequence(self):
        """No second deduction may stack on top of the cap for the same event."""
        for carried in ('20.00', '55.00', '70.43', '120.00'):
            with self.subTest(carried=carried):
                idle = self._extra_team(f'idle-{carried}', carried)
                active = self._extra_team(f'active-{carried}', '45.00')
                round_number = 1

                self._score([idle, active], [D('0'), D('6000000')],
                            round_number=round_number)

                self.assertEqual(
                    self._result(idle, round_number).index_change, D('-5.00'),
                    'the cost of not competing must not depend on the index '
                    'the firm was carrying')

    def test_the_scored_index_and_the_standings_agree_on_who_competed(self):
        """One classification, published once, consumed by both controls."""
        idle = self._extra_team('idle', '90.00')
        active = self._extra_team('active', '40.00')

        context = self._score([idle, active], [D('0'), D('8000000')])

        self.assertEqual(context.commercially_inactive_team_ids,
                         frozenset([idle.id]))

        update_leaderboard(context)
        ranks = {
            entry.team.name: entry.rank
            for entry in LeaderboardEntry.objects.filter(
                game=self.game, round_number=1).select_related('team')
        }
        self.assertEqual(ranks['active'], 1)
        self.assertEqual(ranks['idle'], 2)
        idle.refresh_from_db()
        self.assertEqual(idle.performance_index, D('85.00'),
                         'capped by the composite cap, not rewritten by rank')
