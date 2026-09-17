"""R34 — a guard firing is recorded as an audit event, not as a hashed field.

Owner ruling R34 (2026-09-17), `handoff_readiness_v2/OWNER_RULINGS_2026-09-17.md`:

    It must be visible in stored data — recorded as an audit event, not by
    adding a field to the hashed performance or leaderboard rows.

Under R32 the standings place a commercially inactive firm below every firm
that competed, whatever its score, so a team can hold a **higher** performance
index than the team above it and still finish below them. Before R34 that
firing existed only in `context.log`: the stored rows read "index 90.00, rank 2"
beside "index 60.00, rank 1" and said nothing about why.

What these tests hold:

1. **The firing is in stored data.** One `DecisionAuditEvent` per demoted team
   per round, actor `system` (`user=None`), endpoint naming the engine step.
2. **The payload answers the question a disputing team actually asks** — why am
   I below a team I outscored? It carries the team's own index, the lowest
   index among firms that competed and whose it was, the rank received, the
   round, and the classification that caused it. Names, not bare ids.
3. **Recomputation does not duplicate.** The rows are append-only and immutable
   (`0070_audit_guards` protects the table), so the property has to be
   skip-if-already-recorded rather than overwrite.
4. **Ranking behaviour is untouched.** R34 adds the explanation, not an effect.
5. **A context with no `Round` row records nothing** — which is what keeps the
   round-zero bootstrap and R32's own stub fixtures working unchanged.
"""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.authentication import create_access_token
from core.engine.leaderboard import update_leaderboard
from core.models.competition_audit import DecisionAuditEvent
from core.models.core import Game, Round, Team, User
from core.models.decisions import DecisionSubmission
from core.models.results_financials import LeaderboardEntry
from core.models.scenario import FirmStarterProfile, MarketDefinition, Scenario

# Written as literals rather than imported, so that a run against the
# unmodified engine fails on the assertion rather than on the import.
ACTION = 'inactivity_rank_demotion'
ENDPOINT = 'engine:update_leaderboard'
RULE = 'inactivity.ranked_below_every_active_firm'


def _context(**attributes):
    """A resolution context stub carrying only what the step under test reads."""
    return type('Ctx', (), attributes)()


class DemotionFixture(TestCase):
    """A minimal game whose ranking inputs are all explicit.

    Unlike R32's `StandingsFixture` this one creates the `Round` row, because
    an audit event is keyed to a round. The absence of that row is itself a
    case under test — see `NoRoundRowRecordsNothing`.
    """

    def setUp(self):
        user = get_user_model().objects.create_user(f'r34-{id(self)}')
        self.scenario = Scenario.objects.create(
            name=f'R34 standings {id(self)}', industry_label='T',
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
            scenario=self.scenario, name='R34 game', created_by=user,
            status='active', current_round=4)
        self.round = Round.objects.create(
            game=self.game, round_number=4, status='closed')

    def _team(self, name, index):
        return Team.objects.create(
            game=self.game, name=name, firm_starter_profile=self.profile,
            performance_index=D(index), cash_on_hand=D('1000'),
            total_equity=D('1000'))

    def _rank(self, teams, inactive, round_number=4):
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

    def _events(self, round_obj=None):
        return list(DecisionAuditEvent.objects.filter(
            game=self.game, round=round_obj or self.round, action=ACTION,
        ).order_by('id'))


class TheFiringIsRecordedInStoredData(DemotionFixture):
    """R34's substance: the inversion is explained somewhere a dispute can read."""

    def test_a_demoted_firm_leaves_exactly_one_audit_event(self):
        leader = self._team('inactive-leader', '90.00')
        self._team('active-rival', '60.00')

        self._rank(Team.objects.filter(game=self.game), inactive=[leader])

        events = self._events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].team_id, leader.id)

    def test_the_actor_is_system_and_the_endpoint_names_the_engine_step(self):
        """The price-band precedent: `user=None` renders as actor `system`."""
        leader = self._team('inactive-leader', '90.00')
        self._team('active-rival', '60.00')

        self._rank(Team.objects.filter(game=self.game), inactive=[leader])

        event = self._events()[0]
        self.assertIsNone(event.user_id)
        self.assertEqual(event.endpoint, ENDPOINT)
        self.assertEqual(event.action, ACTION)

    def test_a_firm_that_competed_leaves_no_event(self):
        self._team('active-one', '90.00')
        self._team('active-two', '60.00')

        self._rank(Team.objects.filter(game=self.game), inactive=[])

        self.assertEqual(self._events(), [])

    def test_one_event_per_demoted_team(self):
        teams = [
            self._team('inactive-top', '95.00'),
            self._team('active-second', '80.00'),
            self._team('inactive-third', '70.00'),
            self._team('active-fourth', '65.00'),
            self._team('inactive-fifth', '50.00'),
        ]
        inactive = [teams[0], teams[2], teams[4]]

        self._rank(teams, inactive=inactive)

        self.assertEqual(
            sorted(e.team.name for e in self._events()),
            ['inactive-fifth', 'inactive-third', 'inactive-top'])


class ThePayloadAnswersTheDispute(DemotionFixture):
    """"Why am I below a team I outscored?" — answerable from the row."""

    def _payload(self):
        leader = self._team('inactive-leader', '90.00')
        self._team('active-rival', '60.00')
        self._rank(Team.objects.filter(game=self.game), inactive=[leader])
        return self._events()[0].payload, leader

    def test_it_carries_the_firms_own_index_and_the_rank_it_received(self):
        payload, _leader = self._payload()

        self.assertEqual(payload['performance_index'], '90.00')
        self.assertEqual(payload['rank'], 2)
        self.assertEqual(payload['round_number'], 4)

    def test_it_carries_the_lowest_index_among_firms_that_competed(self):
        """The number that makes the inversion legible: the team was placed
        below a firm carrying 60.00 while itself carrying 90.00."""
        payload, _leader = self._payload()

        self.assertEqual(payload['lowest_active_performance_index'], '60.00')
        self.assertEqual(payload['lowest_active_team_name'], 'active-rival')
        self.assertTrue(payload['outscored_a_firm_ranked_above'])

    def test_it_names_the_classification_that_caused_the_demotion(self):
        payload, _leader = self._payload()

        self.assertEqual(payload['rule'], RULE)
        self.assertEqual(payload['classification'], 'commercially_inactive')

    def test_it_names_the_firm_rather_than_only_its_id(self):
        """Names, not bare ids, where a human will read it — the price-band
        payload was built to the same standard."""
        payload, leader = self._payload()

        self.assertEqual(payload['team_name'], 'inactive-leader')
        self.assertEqual(payload['team_id'], leader.id)

    def test_a_demotion_that_cost_no_places_is_recorded_honestly(self):
        """The guard still fires when the firm was last anyway. The event says
        so rather than claiming an inversion that did not happen."""
        idle = self._team('idle-and-last', '10.00')
        self._team('active-rival', '80.00')

        self._rank(Team.objects.filter(game=self.game), inactive=[idle])

        payload = self._events()[0].payload
        self.assertFalse(payload['outscored_a_firm_ranked_above'])
        self.assertEqual(payload['performance_index'], '10.00')

    def test_a_field_with_no_active_firm_records_no_comparison_it_cannot_make(self):
        """Nobody competed, so there is no lowest active index to name."""
        first = self._team('high', '80.00')
        second = self._team('low', '40.00')

        self._rank([first, second], inactive=[first, second])

        for event in self._events():
            self.assertIsNone(event.payload['lowest_active_performance_index'])
            self.assertIsNone(event.payload['lowest_active_team_name'])
            self.assertFalse(event.payload['outscored_a_firm_ranked_above'])


class RecomputingTheRoundDoesNotDuplicate(DemotionFixture):
    """The rows are immutable and the table is append-only, so the only
    available property is skip-if-already-recorded."""

    def test_ranking_the_same_round_twice_leaves_one_event(self):
        leader = self._team('inactive-leader', '90.00')
        self._team('active-rival', '60.00')
        teams = list(Team.objects.filter(game=self.game))

        self._rank(teams, inactive=[leader])
        self._rank(teams, inactive=[leader])

        self.assertEqual(len(self._events()), 1)

    def test_a_correction_that_changes_the_field_still_leaves_one_event(self):
        """A re-process after a correction must not stack a second receipt on
        the same team and round."""
        leader = self._team('inactive-leader', '90.00')
        rival = self._team('active-rival', '60.00')

        self._rank([leader, rival], inactive=[leader])
        third = self._team('late-arrival', '70.00')
        self._rank([leader, rival, third], inactive=[leader])

        self.assertEqual(len(self._events()), 1)

    def test_a_team_demoted_in_two_different_rounds_leaves_one_event_each(self):
        """Idempotency is per round, not per team: a firm that sits out twice
        is recorded twice."""
        leader = self._team('inactive-leader', '90.00')
        self._team('active-rival', '60.00')
        teams = list(Team.objects.filter(game=self.game))
        round_five = Round.objects.create(
            game=self.game, round_number=5, status='closed')

        self._rank(teams, inactive=[leader], round_number=4)
        self._rank(teams, inactive=[leader], round_number=5)

        self.assertEqual(len(self._events()), 1)
        self.assertEqual(len(self._events(round_obj=round_five)), 1)


class RankingBehaviourIsUnchanged(DemotionFixture):
    """R32's enforcement stands exactly as merged; R34 adds no effect."""

    def test_the_standings_are_what_r32_merged(self):
        leader = self._team('inactive-leader', '90.00')
        self._team('active-rival', '60.00')

        ranks = self._rank(Team.objects.filter(game=self.game),
                           inactive=[leader])

        self.assertEqual(ranks['active-rival'], 1)
        self.assertEqual(ranks['inactive-leader'], 2)

    def test_the_published_index_is_still_the_carried_one(self):
        """The receipt explains the rank; it does not rewrite a score."""
        leader = self._team('inactive-leader', '90.00')
        self._team('active-rival', '60.00')

        self._rank(Team.objects.filter(game=self.game), inactive=[leader])

        leader.refresh_from_db()
        self.assertEqual(leader.performance_index, D('90.00'))
        self.assertEqual(
            LeaderboardEntry.objects.get(
                game=self.game, round_number=4, team=leader,
            ).performance_index,
            D('90.00'))


class NoRoundRowRecordsNothing(DemotionFixture):
    """An audit event is keyed to a round. Where there is no round row there is
    nothing to key to, and the standings must still rank.

    This is the property that keeps R32's own fixtures — which create no
    `Round` — and the round-zero bootstrap working unchanged.
    """

    def test_ranking_a_round_with_no_round_row_still_ranks_and_records_nothing(self):
        leader = self._team('inactive-leader', '90.00')
        self._team('active-rival', '60.00')

        ranks = self._rank(Team.objects.filter(game=self.game),
                           inactive=[leader], round_number=9)

        self.assertEqual(ranks['active-rival'], 1)
        self.assertEqual(ranks['inactive-leader'], 2)
        self.assertEqual(
            DecisionAuditEvent.objects.filter(
                game=self.game, action=ACTION).count(),
            0)


class TheDisputeToolingSurfacesItUnchanged(DemotionFixture):
    """CRV2-08's instructor drill-down already reads every audit event for a
    team and round and renders `user=None` as actor `system`. R34 needs no
    change there, and this is the proof rather than the assumption."""

    def test_the_instructor_drilldown_shows_the_demotion_as_actor_system(self):
        leader = self._team('inactive-leader', '90.00')
        self._team('active-rival', '60.00')
        DecisionSubmission.objects.create(
            team=leader, round=self.round, status='locked')
        self._rank(Team.objects.filter(game=self.game), inactive=[leader])

        instructor = User.objects.create(
            username=f'r34-inst-{id(self)}', role='instructor',
            password_hash='x')
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(instructor)}')
        response = client.get(
            f'/api/games/{self.game.id}/instructor/teams/{leader.id}'
            f'/decisions/', {'round': 4})

        self.assertEqual(response.status_code, 200)
        demotions = [event for event in response.data['audit_events']
                     if event['action'] == ACTION]
        self.assertEqual(len(demotions), 1)
        self.assertEqual(demotions[0]['actor'], 'system')
        self.assertEqual(demotions[0]['endpoint'], ENDPOINT)
        self.assertEqual(
            demotions[0]['payload']['lowest_active_performance_index'],
            '60.00')


class TheModuleExposesItsRecordedVocabulary(TestCase):
    """The action and rule strings are what a dispute is answered with months
    later, so they are named constants rather than literals at the call site —
    the standard `price_band` set for the same reason."""

    def test_the_constants_are_the_strings_that_are_stored(self):
        from core.engine import leaderboard

        self.assertEqual(leaderboard.ACTION_INACTIVITY_DEMOTION, ACTION)
        self.assertEqual(leaderboard.RULE_INACTIVE_RANKED_BELOW_ACTIVE, RULE)
        self.assertEqual(leaderboard.AUDIT_ENDPOINT, ENDPOINT)
