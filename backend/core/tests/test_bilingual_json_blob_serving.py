"""Authored content inside a JSONField reaches a Chinese reader in Chinese.

`get_localized_field` reads `<field>` and `<field>_zh` off a model. It cannot
reach inside a JSONField, and three views served authored blobs straight
through while localising every model field beside them. The ten-round browser
pass on candidate `a0631e5d` caught the first of these on a Chinese student's
own screen:

* `cc32d_views` served `'preferences': p.preferences` — the questions an
  alliance partner judges the team on — raw, two lines below
  `get_localized_field(p, 'description', language)`. The partner was in
  Chinese and the questions beside it in English.
* `cc32a_views` localised each criterion's NAME (W-CE3-17) and served the
  sentence under it — what the team is told its writing is judged on — as
  stored, plus `audience_display`, which is the English half of
  `AUDIENCE_CHOICES`.
* `cc31j_views` served `amplifier`, whose `description`
  `CorporateStrategyPage` prints to the player.

The scenario content is checked by `test_scenario_bilingual_coverage`. These
tests are the other half: that the serving path picks the translation up, and
that an English reader is unaffected. They build their own rows rather than
loading a scenario, so a serving regression fails here even if the content
changes.
"""
from decimal import Decimal

from core.models.cc31_models import GovernanceCommitmentType
from core.models.cc32_models import CommunicationAssignment
from core.models.cc32d_models import AlliancePartnerProfile, TeamAllianceState
from core.models.course import Enrollment
from core.tests.test_paid_research import PaidResearchBase

CHINESE_PREFERENCE = '你们在本地招聘吗？'
CHINESE_CRITERION = '备忘录是否与团队实际的决策相符？'
CHINESE_AMPLIFIER = '在公开披露的前提下，满意度提升 30%'


def has_cjk(text):
    return any('一' <= ch <= '鿿' for ch in str(text))


class BilingualBlobServingBase(PaidResearchBase):
    """The student of `PaidResearchBase`, reading in a stated language."""

    def read_as(self, url, language):
        Enrollment.objects.filter(user_id=self.user.user_id).update(
            language=language)
        return self.client.get(url, HTTP_ACCEPT_LANGUAGE=language)

    def alliance_url(self):
        return f'/api/games/{self.game.id}/teams/{self.team.id}/alliances/'

    def governance_url(self):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/context/governance/')

    def communications_url(self):
        return (f'/api/games/{self.game.id}/teams/{self.team.id}'
                f'/communications/assignments/')


class AlliancePreferenceLanguageTests(BilingualBlobServingBase):

    def setUp(self):
        super().setUp()
        self.profile = AlliancePartnerProfile.objects.create(
            scenario=self.scenario, partnership_code='JV_TEST',
            market=self.market, name='Partner', name_zh='伙伴',
            partner_type='DISTRIBUTOR', description='Who they are',
            description_zh='他们是谁',
            preferences=[{'feature': 'localization_commitment', 'weight': 0.5,
                          'description': 'Are you hiring locally?',
                          'description_zh': CHINESE_PREFERENCE},
                         {'feature': 'volume_growth', 'weight': 0.5,
                          'description': 'Is volume growing?'}])
        TeamAllianceState.objects.create(
            game=self.game, team=self.team, partner_profile=self.profile,
            market=self.market, satisfaction=Decimal('0.70'),
            status='HEALTHY', established_round=1)

    def _preferences(self, language):
        response = self.read_as(self.alliance_url(), language)
        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()
        alliances = rows if isinstance(rows, list) else rows.get('alliances', rows)
        self.assertTrue(alliances, rows)
        first = alliances[0] if isinstance(alliances, list) else alliances
        return [p.get('description') for p in first['preferences']]

    def test_a_chinese_reader_gets_the_chinese_question(self):
        self.assertIn(CHINESE_PREFERENCE, self._preferences('zh-CN'))

    def test_an_english_reader_is_unaffected(self):
        served = self._preferences('en')
        self.assertIn('Are you hiring locally?', served)
        self.assertFalse([s for s in served if has_cjk(s)], served)

    def test_a_preference_with_no_translation_keeps_its_english(self):
        """Falling back is what the engine reads, so it must still be there."""
        self.assertIn('Is volume growing?', self._preferences('zh-CN'))

    def test_the_weight_the_engine_reads_survives_the_rewrite(self):
        """The view rebuilds each dict; the engine's fields must come through."""
        response = self.read_as(self.alliance_url(), 'zh-CN')
        rows = response.json()
        alliances = rows if isinstance(rows, list) else rows.get('alliances', rows)
        first = alliances[0] if isinstance(alliances, list) else alliances
        for served in first['preferences']:
            self.assertIn('feature', served)
            self.assertIn('weight', served)


class CommunicationAssignmentLanguageTests(BilingualBlobServingBase):

    def setUp(self):
        super().setUp()
        CommunicationAssignment.objects.create(
            scenario=self.scenario, code='BOARD_MEMO',
            name='Board memo', name_zh='董事会备忘录',
            audience='BOARD', prompt_text='Write to the board.',
            prompt_text_zh='请向董事会汇报。', word_limit=300,
            # Fires on the round the base class opens, so the view returns it.
            trigger_type='ROUND_MILESTONE', trigger_condition={'round': 1},
            is_mandatory=True,
            coherence_weight=Decimal('0.05'),
            evaluation_criteria=[
                {'criterion': 'strategic_consistency', 'weight': 0.4,
                 'description': 'Does the memo match the decisions?',
                 'description_zh': CHINESE_CRITERION},
            ])

    def _assignment(self, language):
        response = self.read_as(self.communications_url(), language)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        rows = body if isinstance(body, list) else body.get('assignments', [])
        self.assertTrue(rows, body)
        return rows[0]

    def test_a_chinese_reader_gets_the_chinese_criterion(self):
        served = self._assignment('zh-CN')
        self.assertEqual(served['evaluation_criteria'][0]['description'],
                         CHINESE_CRITERION)

    def test_the_criterion_name_is_still_localised(self):
        """W-CE3-17's repair, which this change sits beside."""
        served = self._assignment('zh-CN')
        self.assertTrue(
            has_cjk(served['evaluation_criteria'][0]['criterion_label']),
            served['evaluation_criteria'][0])

    def test_the_storage_token_is_still_served(self):
        """`evaluation.criteria_scores` is keyed by it."""
        served = self._assignment('zh-CN')
        self.assertEqual(served['evaluation_criteria'][0]['criterion'],
                         'strategic_consistency')

    def test_the_audience_reads_in_chinese(self):
        self.assertEqual(self._assignment('zh-CN')['audience_display'], '董事会')

    def test_the_audience_reads_in_english_for_an_english_reader(self):
        self.assertEqual(self._assignment('en')['audience_display'],
                         'Board of Directors')

    def test_an_english_reader_gets_the_english_criterion(self):
        served = self._assignment('en')
        self.assertEqual(served['evaluation_criteria'][0]['description'],
                         'Does the memo match the decisions?')


class GovernanceAmplifierLanguageTests(BilingualBlobServingBase):
    """`CorporateStrategyPage` prints `amplifier.description` to the player.

    The `interactions` blob beside it is deliberately NOT localised: the page
    renders no field of it, and what a player reads about an interaction is
    built by `_evaluate_all_interactions` from the bilingual catalogue. The
    scenario-coverage test names that exception with the same reason, so the two
    records agree.
    """

    def setUp(self):
        super().setUp()
        GovernanceCommitmentType.objects.create(
            scenario=self.scenario, code='ESG_REPORT',
            name='Public ESG reporting', name_zh='公开 ESG 披露',
            description='Report publicly', description_zh='对外公开披露',
            ongoing_cost_per_round=Decimal('100000'),
            amplifier={'description': 'All ESG investments produce more '
                                      'stakeholder satisfaction',
                       'description_zh': CHINESE_AMPLIFIER,
                       'multiplier': 1.3})

    def _amplifier(self, language):
        response = self.read_as(self.governance_url(), language)
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        defs = body.get('commitment_defs') or body.get('commitment_types') or []
        self.assertTrue(defs, body)
        return defs[0]['amplifier']

    def test_a_chinese_reader_gets_the_chinese_amplifier(self):
        self.assertEqual(self._amplifier('zh-CN')['description'],
                         CHINESE_AMPLIFIER)

    def test_an_english_reader_gets_the_english_amplifier(self):
        served = self._amplifier('en')
        self.assertFalse(has_cjk(served['description']), served)

    def test_the_multiplier_the_engine_reads_survives(self):
        self.assertEqual(self._amplifier('zh-CN')['multiplier'], 1.3)
