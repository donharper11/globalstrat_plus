"""Third-walkthrough display and language repairs (W-CE3-*).

One file per walkthrough pass, as `test_walk_ce2_language.py` is for the
second. Each class names the defect it holds closed and fails on the
unmodified tree.
"""
from django.test import SimpleTestCase

from core.tests.test_demotion_team_notice import DemotionNoticeFixture


# ---------------------------------------------------------------------------
# W-CE3-15 — the standings contradicted the numbers beside them
# ---------------------------------------------------------------------------

class TheLeaderboardSaysWhyTheTopScoreIsNotFirst(DemotionNoticeFixture):
    """R32 places a commercially inactive firm below every firm that competed.

    The team's own results screen explains it (R35). The leaderboard -- the
    screen a competition is read from -- had no field for it and no mention of
    it, so round 6 showed `4 Meridian Tech 60.34` under three lower scores
    with nothing to explain it.
    """

    def setUp(self):
        super().setUp()
        self.carry(self.team, '90.00')
        self.carry(self.rival, '60.00')
        self.demote(inactive=[self.team])

    def board(self, language=None, user=None, round_number=1):
        headers = ({'HTTP_ACCEPT_LANGUAGE': language} if language else {})
        response = self.client_for(user or self.student).get(
            f'/api/games/{self.game.id}/leaderboard/round/{round_number}/',
            **headers)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def row(self, data, team):
        return next(r for r in data['rankings'] if r['team_id'] == team.id)

    def test_the_demoted_row_is_marked(self):
        data = self.board()

        self.assertTrue(self.row(data, self.team)['commercially_inactive'])
        self.assertTrue(self.row(data, self.team)['rank_marker'])

    def test_a_firm_that_competed_is_not_marked(self):
        data = self.board()

        self.assertFalse(self.row(data, self.rival)['commercially_inactive'])
        self.assertIsNone(self.row(data, self.rival)['rank_marker'])

    def test_the_rule_is_stated_under_the_table(self):
        note = self.board()['rank_rule_note']

        self.assertTrue(note)
        self.assertIn('did not compete', note)
        self.assertIn('not reduced', note)

    def test_the_marker_and_the_rule_read_in_chinese(self):
        data = self.board(language='zh-CN')

        self.assertEqual(self.row(data, self.team)['rank_marker'], '未参与竞争')
        self.assertIn('未参与竞争', data['rank_rule_note'])
        self.assertIn('绩效指数本身并未被扣减', data['rank_rule_note'])

    def test_the_marker_is_read_from_the_stored_receipt(self):
        """Not recomputed beside the record: a screen cannot disagree with the
        audit row about who was demoted."""
        from core.engine import leaderboard as rank_rules

        self.assertEqual(
            rank_rules.demoted_team_ids(self.game, 1), {self.team.id})
        self.assertEqual(self.receipt().payload['team_id'], self.team.id)

    def test_a_round_with_no_demotion_states_no_rule(self):
        self.assertTrue(self.board()['rank_rule_note'])

        # Round 2 was never ranked, so it carries no receipts and no rule.
        self.assertIsNone(self.board(round_number=2)['rank_rule_note'])

    def test_no_rival_score_is_published_by_the_marker(self):
        """R35's standard: the record names the firm that was outscored so a
        dispute can be answered; the marker does not republish it."""
        marker = self.row(self.board(), self.team)['rank_marker']

        self.assertNotIn(self.rival.name, marker)
        self.assertNotIn('60', marker)


class TheLeaderboardSentencesAreInTheCatalogue(SimpleTestCase):
    """Both languages, and no storage name in either (A1/A3's property)."""

    def test_both_sentences_carry_both_languages(self):
        from core.utils.participant_messages import MESSAGES

        for key in ('inactivity_rank_marker', 'inactivity_rank_rule'):
            with self.subTest(key=key):
                self.assertEqual(set(MESSAGES[key]), {'en', 'zh-CN'})
                for text in MESSAGES[key].values():
                    self.assertNotIn('_', text)
