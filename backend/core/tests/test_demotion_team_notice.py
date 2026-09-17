"""R35 — the demoted team is told on its own results screen.

Owner ruling R35 (2026-09-17), `handoff_readiness_v2/OWNER_RULINGS_2026-09-17.md`:

    The demoted team is told on its own results screen.

The chain this closes. **R32** moved the commercial-inactivity rule onto the
standings: a firm that sold nothing is placed below every firm that competed,
whatever its score, so a team can hold a *higher* performance index than the
team above it and still finish below it. **R34** made that firing visible in
stored data as a `DecisionAuditEvent`, and CRV2-08's instructor drill-down
already surfaces it. **The team itself was not told:** `RoundResultsView`
filtered audit events to the three price-band actions, so a demoted team read
its own standing with no explanation.

What these tests hold:

1. **The demoted team sees it on its own results screen**, beside the
   price-band adjustments that surface already carries.
2. **The sentence is rendered from the stored payload**, exactly as
   `price_band.adjustment_notice` is — so the sentence the team reads and the
   row an instructor produces in a dispute are the same fact, not two
   computations that can drift apart.
3. **It is participant language, in both shipped languages**, naming no column,
   no action code and no internal id.
4. **It is honest about what the guard cost.** R34's payload records
   `outscored_a_firm_ranked_above` as false when the firm would have finished
   last regardless; the sentence must not then claim it lost a place.
5. **A team with no demotion gets the key present and empty**, not missing, so
   the screen renders "nothing happened" rather than crashing on a missing
   field.
6. **The price-band notices are unchanged** — neither filter catches the
   other's rows.
7. **A rival cannot read this team's notice.** The cross-team leakage property
   Stage 5 established as the standard for this endpoint, re-asserted because
   this change widens what the endpoint reads out of the audit table.

The guard has never fired in stored play (the 2026-09-16 measurement: 448 index
rows, worst `index_change` -5.82), so the firing is constructed here rather than
found, the way `handoff_readiness_v2/r34_inactivity_fixture.py` constructs it.

`PriceBandFixture` is reused rather than reimplemented: it already builds a game
whose round 1 can be closed through the real `close_round` path, which is what
lets test 6 put a genuine band adjustment and a genuine demotion in one round.
It carries no tests of its own, so importing it runs nothing twice.
"""
from decimal import Decimal as D

from core.engine.advance_round import close_round
from core.engine.leaderboard import update_leaderboard
from core.models import DecisionAuditEvent, Round
from core.models.core import Team
from core.services import price_band as band_rules
from core.tests.test_price_band import PriceBandFixture

# Written as literals rather than imported, so a run against the unmodified
# tree fails on the assertion rather than on the import. The same reason
# `test_inactivity_demotion_audit` writes its own.
ACTION = 'inactivity_rank_demotion'
RULE = 'inactivity.ranked_below_every_active_firm'
CLASSIFICATION = 'commercially_inactive'
RESPONSE_KEY = 'inactivity_notices'


class DemotionNoticeFixture(PriceBandFixture):
    """One game, two enrolled teams, and a round whose guard can be fired."""

    def setUp(self):
        super().setUp()
        from core.models import User
        from core.models.course import Course, Enrollment, Section

        course = Course.objects.create(
            course_code=f'R35{id(self) % 100000}', course_name='Demotion',
            instructor_id=None, is_active=True)
        section = Section.objects.create(
            course_id=course.course_id, section_code='S', section_name='S',
            max_teams=4, team_size_min=1, team_size_max=4, is_active=True)
        self.student = User.objects.create(
            username=f'r35-student-{id(self)}', role='student',
            password_hash='x')
        self.rival_student = User.objects.create(
            username=f'r35-rival-{id(self)}', role='student',
            password_hash='x')
        Enrollment.objects.create(
            user_id=self.student.user_id, section_id=section.section_id,
            team_id=self.team.id, is_active=True)
        Enrollment.objects.create(
            user_id=self.rival_student.user_id, section_id=section.section_id,
            team_id=self.rival.id, is_active=True)

    # -- building the firing -------------------------------------------------

    def carry(self, team, index):
        team.performance_index = D(str(index))
        team.save(update_fields=['performance_index'])
        return team

    def demote(self, inactive, round_number=1):
        """Rank the round with `inactive` classified as not having competed.

        A stub context carrying only what the ranking step reads, which is how
        R32's and R34's own tests drive it. The `Round` row already exists, so
        the receipt is written.
        """
        teams = list(Team.objects.filter(game=self.game))
        context = type('Ctx', (), {
            'game': self.game, 'scenario': self.scenario,
            'round_number': round_number, 'teams': teams,
            'financials': {}, 'log': [],
            'commercially_inactive_team_ids': frozenset(
                t.id for t in inactive),
        })()
        update_leaderboard(context)

    def receipt(self, team=None, round_number=1):
        return DecisionAuditEvent.objects.filter(
            game=self.game, team=team or self.team, action=ACTION,
            round__round_number=round_number).first()

    # -- reading the team's own screen --------------------------------------

    def client_for(self, user):
        from rest_framework.test import APIClient
        from core.authentication import create_access_token
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {create_access_token(user)}')
        return client

    def url(self, team=None, round_number=1):
        return (f'/api/games/{self.game.id}/teams/{(team or self.team).id}'
                f'/results/round/{round_number}/')

    def results(self, user=None, team=None, round_number=1, language=None):
        headers = ({'HTTP_ACCEPT_LANGUAGE': language} if language else {})
        return self.client_for(user or self.student).get(
            self.url(team, round_number), **headers)

    def notices(self, **kwargs):
        response = self.results(**kwargs)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn(
            RESPONSE_KEY, response.data,
            'the team results screen carries no demotion notice at all')
        return response.data[RESPONSE_KEY]


class TheDemotedTeamIsToldOnItsOwnScreen(DemotionNoticeFixture):
    """R35's substance: the team reads the reason on its own results screen."""

    def demoted_leader(self):
        """The inversion R32 creates: outscores its rival and finishes below."""
        self.carry(self.team, '90.00')
        self.carry(self.rival, '60.00')
        self.demote(inactive=[self.team])

    def test_a_demoted_team_gets_exactly_one_notice(self):
        self.demoted_leader()

        self.assertEqual(len(self.notices()), 1)

    def test_the_notice_states_the_rule_and_what_it_means(self):
        self.demoted_leader()

        message = self.notices()[0]['message']
        self.assertIn('sold nothing in round 1', message)
        self.assertIn('placed below every firm that did', message)
        self.assertIn('ranked 2', message)
        self.assertIn('90.00', message)

    def test_the_notice_says_the_index_itself_was_not_reduced(self):
        """R32's whole point: the standing moved, the carried score did not.
        A team told only "you were placed last" would reasonably read it as a
        scoring penalty, which is the control R32 removed."""
        self.demoted_leader()

        self.assertIn('was not reduced', self.notices()[0]['message'])

    def test_the_notice_says_what_to_do_next(self):
        """CRV2-12's standard: state the rule AND what to do next."""
        self.demoted_leader()

        self.assertIn('at least one market', self.notices()[0]['message'])


class TheSentenceAndTheAuditRowAreTheSameFact(DemotionNoticeFixture):
    """Rendered from the stored payload, not recomputed beside it.

    This is the property that keeps the sentence a team reads and the row an
    instructor produces in a dispute from drifting apart, and it is the reason
    `price_band.adjustment_notice` renders from its payload too.
    """

    def setUp(self):
        super().setUp()
        self.carry(self.team, '90.00')
        self.carry(self.rival, '60.00')
        self.demote(inactive=[self.team])

    def test_the_message_is_the_rendering_of_the_stored_payload(self):
        from core.engine import leaderboard

        payload = self.receipt().payload

        self.assertEqual(
            self.notices()[0]['message'],
            leaderboard.demotion_notice(payload, 'en'))

    def test_the_notice_carries_the_recorded_rank_and_index_unaltered(self):
        payload = self.receipt().payload

        notice = self.notices()[0]

        self.assertEqual(notice['rank'], payload['rank'])
        self.assertEqual(notice['performance_index'],
                         payload['performance_index'])
        self.assertEqual(notice['rule'], RULE)

    def test_the_notice_reads_back_in_chinese(self):
        english = self.notices()[0]['message']
        chinese = self.notices(language='zh-CN')[0]['message']

        self.assertNotEqual(english, chinese)
        self.assertIn('未参与竞争', chinese)
        self.assertIn('排名第 2 位', chinese)
        self.assertIn('90.00', chinese)

    def test_it_names_no_action_code_column_or_internal_id(self):
        """GSP-CRV2-12: a participant learns the rule, never the vocabulary
        the record is stored under."""
        for language in ('en', 'zh-CN'):
            message = self.notices(language=language)[0]['message']
            for token in (ACTION, RULE, CLASSIFICATION, 'performance_index',
                          'team_id', 'lowest_active_performance_index',
                          'DecisionAuditEvent', 'LeaderboardEntry'):
                self.assertNotIn(token, message)


class TheNoticeIsHonestAboutWhatTheGuardCost(DemotionNoticeFixture):
    """R34 records `outscored_a_firm_ranked_above` as false when the firm would
    have finished last anyway. The sentence must not then claim a lost place."""

    def test_an_inversion_says_the_firm_outscored_those_above_it(self):
        self.carry(self.team, '90.00')
        self.carry(self.rival, '60.00')
        self.demote(inactive=[self.team])

        self.assertTrue(self.receipt().payload['outscored_a_firm_ranked_above'])
        self.assertIn('lower than yours', self.notices()[0]['message'])

    def test_a_demotion_that_cost_no_places_claims_none(self):
        self.carry(self.team, '10.00')
        self.carry(self.rival, '80.00')
        self.demote(inactive=[self.team])

        self.assertFalse(
            self.receipt().payload['outscored_a_firm_ranked_above'])
        message = self.notices()[0]['message']
        self.assertNotIn('lower than yours', message)
        # The rule is still stated: the guard fired, and the team is still told.
        self.assertIn('placed below every firm that did', message)


class ATeamThatCompetedSeesNothing(DemotionNoticeFixture):
    """Present and empty, never missing."""

    def test_a_team_that_competed_gets_an_empty_list_not_a_missing_key(self):
        self.carry(self.team, '90.00')
        self.carry(self.rival, '60.00')
        self.demote(inactive=[self.rival])

        response = self.results()

        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn(RESPONSE_KEY, response.data)
        self.assertEqual(response.data[RESPONSE_KEY], [])

    def test_a_round_in_which_nobody_was_demoted_is_empty_too(self):
        self.demote(inactive=[])

        self.assertEqual(self.notices(), [])

    def test_a_round_with_no_round_row_at_all_is_empty_rather_than_an_error(self):
        """Round 2 has no `Round` row here, so there is nothing to key a
        receipt to. The screen must still answer."""
        response = self.results(round_number=2)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data[RESPONSE_KEY], [])


class ThePriceBandNoticesAreUnchanged(DemotionNoticeFixture):
    """One round carrying both kinds of receipt. Neither filter may catch the
    other's rows, and the band wording is not touched by this change."""

    def setUp(self):
        super().setUp()
        self.sold_at(0, 400)
        self.priced(99999)
        close_round(self.game.id, reason='deadline')
        self.carry(self.team, '90.00')
        self.carry(self.rival, '60.00')
        self.demote(inactive=[self.team])

    def test_the_round_really_carries_both_receipts(self):
        self.assertEqual(len(self.adjustments()), 1)
        self.assertIsNotNone(self.receipt())

    def test_the_price_band_notice_still_renders_as_stage_five_left_it(self):
        response = self.results()

        adjustments = response.data['price_adjustments']
        self.assertEqual(len(adjustments), 1)
        self.assertEqual(adjustments[0]['rule'], band_rules.RULE_OUT_OF_BAND)
        self.assertEqual(
            adjustments[0]['message'],
            band_rules.adjustment_notice(self.adjustments()[0].payload, 'en'))

    def test_the_demotion_does_not_appear_among_the_price_adjustments(self):
        response = self.results()

        for adjustment in response.data['price_adjustments']:
            self.assertNotEqual(adjustment['rule'], RULE)

    def test_a_price_adjustment_does_not_appear_among_the_demotion_notices(self):
        for notice in self.notices():
            self.assertEqual(notice['rule'], RULE)


class DemotionNoticesDoNotLeakAcrossTeams(DemotionNoticeFixture):
    """This change widens what `RoundResultsView` reads out of the audit table,
    so the Stage 5 blast-radius property is re-asserted rather than assumed."""

    def setUp(self):
        super().setUp()
        # Both teams sat the round out, so both have a notice to leak.
        self.carry(self.team, '90.00')
        self.carry(self.rival, '60.00')
        self.demote(inactive=[self.team, self.rival])

    def test_both_teams_were_demoted_so_the_test_can_actually_leak(self):
        self.assertIsNotNone(self.receipt())
        self.assertIsNotNone(self.receipt(team=self.rival))

    def test_a_team_sees_only_its_own_demotion_notice(self):
        response = self.results()

        self.assertEqual(len(response.data[RESPONSE_KEY]), 1)
        self.assertEqual(
            response.data[RESPONSE_KEY][0]['performance_index'],
            self.receipt().payload['performance_index'])
        self.assertNotIn(self.rival.name, str(response.data))

    def test_a_rivals_student_cannot_read_this_teams_demotion_notice(self):
        """`RoundResultsView` declares no permission class of its own, so what
        refuses a rival is `TeamScopeGuardMiddleware`. The status code is
        asserted explicitly: a bare "the rival did not see it" would also pass
        on a 500, which would prove nothing about the guard."""
        response = self.client_for(self.rival_student).get(self.url(self.team))

        self.assertEqual(
            response.status_code, 403,
            f'expected the team-scope guard to refuse, got '
            f'{response.status_code}: {getattr(response, "data", None)!r}')
        self.assertNotIn(RESPONSE_KEY, str(getattr(response, 'data', '')))

    def test_the_owning_teams_student_is_allowed_through_the_same_guard(self):
        """The control for the test above: the 403 is about team scope, not a
        blanket refusal that would make the leakage test vacuous."""
        response = self.results()

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data[RESPONSE_KEY]), 1)


class TheRoundIsNotConfused(DemotionNoticeFixture):
    """A receipt belongs to the round it was written for."""

    def test_a_demotion_in_round_one_does_not_appear_on_round_two(self):
        Round.objects.create(game=self.game, round_number=2, status='open')
        self.carry(self.team, '90.00')
        self.carry(self.rival, '60.00')
        self.demote(inactive=[self.team], round_number=1)

        self.assertEqual(len(self.notices(round_number=1)), 1)
        self.assertEqual(self.notices(round_number=2), [])
