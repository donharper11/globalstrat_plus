"""A government's actions read in the language of whoever is reading them.

V2-148. `GovernmentAgent._generate_action_narrative` composes an English
sentence at **resolution** and stores it on `GovernmentAction.narrative`; the
student's Government Relations panel prints what is stored. By the time a reader
sees it the words are data, so switching language cannot touch them — and the
ten-round browser pass on candidate `a0631e5d` caught exactly that on a
Simplified-Chinese screen, on a tab no previous walkthrough had opened:

> Government tightening standards due to poor foreign firm compliance

The sentence is now rebuilt at read time from the facts the row already
carries. **Nothing stored changes**, which is what keeps this out of the
determinism boundary: `GovernmentAction` is a manifest section and its
`narrative` is declared a narrative field, so rewriting what the engine *writes*
would move a digest. Re-rendering what a view *serves* moves nothing, and it is
the same thing `narratives` already does for briefings.

The rule these tests pin, in both directions: every shape the agent can write
is rebuilt in the reader's language, and **any shape this is not taught falls
back to the stored sentence** rather than disappearing.
"""
from django.test import SimpleTestCase

from core.utils.participant_messages import (GOVERNMENT_INCENTIVE_LABELS,
                                             GOVERNMENT_OBJECTIVE_LABELS,
                                             government_action_narrative,
                                             government_objective_label,
                                             participant_message)

STORED = 'Government tightening standards due to poor foreign firm compliance'


def has_cjk(text):
    return any('一' <= ch <= '鿿' for ch in str(text))


class GovernmentNarrativeLanguageTests(SimpleTestCase):

    def narrate(self, action_type, parameters, language, **kw):
        return government_action_narrative(
            action_type, parameters, language, stored=STORED, **kw)

    # ---- the shape the walkthrough caught -----------------------------
    def test_the_sentence_found_on_a_chinese_screen_is_now_chinese(self):
        served = self.narrate('regulatory_tightening',
                              {'type': 'compliance_requirement_increase'},
                              'zh-CN')
        self.assertTrue(has_cjk(served), served)
        self.assertNotEqual(served, STORED)

    def test_the_same_sentence_still_reads_in_english(self):
        served = self.narrate('regulatory_tightening',
                              {'type': 'compliance_requirement_increase'}, 'en')
        self.assertFalse(has_cjk(served), served)
        self.assertIn('tightened', served)

    # ---- every other shape the agent can write ------------------------
    def test_an_incentive_names_which_incentive(self):
        for incentive_type in GOVERNMENT_INCENTIVE_LABELS:
            served = self.narrate('grant_incentive', {'type': incentive_type},
                                  'zh-CN')
            with self.subTest(incentive_type):
                self.assertTrue(has_cjk(served), served)
                self.assertNotEqual(served, STORED)

    def test_a_procurement_award_keeps_its_figure(self):
        served = self.narrate('procurement_award',
                              {'contract_value': 2500000}, 'zh-CN')
        self.assertIn('$2,500,000', served)
        self.assertTrue(has_cjk(served), served)

    def test_a_warning_names_the_policy_area_in_chinese(self):
        served = self.narrate('warning_issued',
                              {'reason': 'local_employment'}, 'zh-CN')
        self.assertIn('本地就业', served)

    def test_a_restriction_keeps_its_percentage(self):
        served = self.narrate('access_restriction', {'magnitude': 0.3}, 'zh-CN')
        self.assertIn('30', served)
        self.assertTrue(has_cjk(served), served)

    def test_restoration_reads_in_both_languages(self):
        self.assertTrue(has_cjk(self.narrate('access_restored', {}, 'zh-CN')))
        self.assertFalse(has_cjk(self.narrate('access_restored', {}, 'en')))

    def test_a_relaxation_reads_as_a_reward(self):
        served = self.narrate('regulatory_relaxation',
                              {'type': 'tariff_reduction'}, 'zh-CN')
        self.assertTrue(has_cjk(served), served)

    def test_a_bilateral_improvement_names_both_sides(self):
        served = self.narrate('bilateral_shift',
                              {'type': 'trade_facilitation',
                               'origin_market': 'APAC'}, 'zh-CN',
                              market_name='北美', origin_name='亚太')
        self.assertIn('北美', served)
        self.assertIn('亚太', served)

    def test_increased_screening_names_the_origin(self):
        served = self.narrate('bilateral_shift',
                              {'type': 'increased_screening',
                               'origin_market': 'LATAM'}, 'zh-CN',
                              origin_name='拉美')
        self.assertIn('拉美', served)

    def test_the_origin_code_is_used_when_no_name_was_resolved(self):
        """A market-wide action carries no origin FK; the code is what is left."""
        served = self.narrate('bilateral_shift',
                              {'type': 'increased_screening',
                               'origin_market': 'LATAM'}, 'en')
        self.assertIn('LATAM', served)

    # ---- the fallback, which is the point ----------------------------
    def test_an_untaught_action_type_keeps_the_stored_sentence(self):
        self.assertEqual(
            self.narrate('some_future_action', {'type': 'whatever'}, 'zh-CN'),
            STORED)

    def test_an_untaught_subtype_keeps_the_stored_sentence(self):
        self.assertEqual(
            self.narrate('regulatory_tightening', {'type': 'something_new'},
                         'zh-CN'),
            STORED)

    def test_an_untaught_incentive_keeps_the_stored_sentence(self):
        self.assertEqual(
            self.narrate('grant_incentive', {'type': 'moon_grant'}, 'zh-CN'),
            STORED)

    def test_a_procurement_with_no_figure_keeps_the_stored_sentence(self):
        self.assertEqual(self.narrate('procurement_award', {}, 'zh-CN'), STORED)

    def test_junk_parameters_do_not_raise(self):
        for params in (None, [], 'not a dict', {}):
            with self.subTest(params=params):
                self.assertIsInstance(
                    self.narrate('access_restored', params, 'zh-CN'), str)

    # ---- the label tables -------------------------------------------
    def test_every_objective_label_carries_both_languages(self):
        for key, labels in GOVERNMENT_OBJECTIVE_LABELS.items():
            with self.subTest(key):
                self.assertTrue(labels.get('en'))
                self.assertTrue(labels.get('zh-CN'))
                self.assertTrue(has_cjk(labels['zh-CN']))

    def test_every_incentive_label_carries_both_languages(self):
        for key, labels in GOVERNMENT_INCENTIVE_LABELS.items():
            with self.subTest(key):
                self.assertTrue(labels.get('en'))
                self.assertTrue(labels.get('zh-CN'))
                self.assertTrue(has_cjk(labels['zh-CN']))

    def test_an_objective_the_table_has_not_been_taught_is_prettified(self):
        self.assertEqual(
            government_objective_label('supply_chain_depth', 'zh-CN'),
            'supply chain depth')

    def test_the_sentences_interpolate_the_same_values_in_both_languages(self):
        """A translated sentence that drops a figure is worse than an English one."""
        for key, values in (
            ('govt_narrative_procurement', {'amount': '$1,000'}),
            ('govt_narrative_access_restriction', {'percent': 30}),
            ('govt_narrative_bilateral_improving',
             {'market': 'M', 'origin': 'O'}),
            ('govt_narrative_bilateral_screening', {'origin': 'O'}),
            ('govt_narrative_warning', {'objective': 'X'}),
            ('govt_narrative_incentive', {'incentive': 'Y'}),
        ):
            for value in values.values():
                for language in ('en', 'zh-CN'):
                    with self.subTest(key=key, language=language, value=value):
                        self.assertIn(
                            str(value),
                            participant_message(key, language=language,
                                                **values))


class SoftenedWarningTests(SimpleTestCase):
    """The shape that only a real row revealed.

    `_resolve_cross_agent_conflicts` softens a warning when a team is already
    bleeding capital: it sets `softened` and APPENDS " (moderated to prevent
    capital flight)" to the reason. The first version of this repair treated the
    whole reason as an objective key, so a real row produced
    *"正式警告：请改善local employment (moderated to prevent capital flight)。"* —
    an English clause inside a Chinese sentence. The flag is read instead of the
    English, and the key is taken off the front.

    The row these tests are written from is one of 41 `WARNING_ISSUED` rows the
    ten-round pass wrote.
    """

    REAL = 'local_employment (moderated to prevent capital flight)'

    def test_a_softened_warning_is_entirely_chinese(self):
        served = government_action_narrative(
            'WARNING_ISSUED', {'reason': self.REAL, 'softened': True}, 'zh-CN',
            stored='Warning: improve ' + self.REAL)
        self.assertIn('本地就业', served)
        self.assertFalse(
            [w for w in served.split() if w.isascii() and w.isalpha()],
            'English words left in the Chinese sentence: %r' % served)

    def test_a_softened_warning_says_it_was_moderated(self):
        for language, needle in (('zh-CN', '从轻'), ('en', 'moderated')):
            served = government_action_narrative(
                'WARNING_ISSUED', {'reason': self.REAL, 'softened': True},
                language, stored='x')
            with self.subTest(language):
                self.assertIn(needle, served)

    def test_an_unsoftened_warning_does_not_claim_moderation(self):
        served = government_action_narrative(
            'WARNING_ISSUED', {'reason': 'local_employment'}, 'zh-CN',
            stored='x')
        self.assertNotIn('从轻', served)

    def test_the_uppercase_action_type_the_model_stores_is_handled(self):
        """The agent writes `warning_issued`; the row stores `WARNING_ISSUED`."""
        for action_type in ('warning_issued', 'WARNING_ISSUED'):
            with self.subTest(action_type):
                served = government_action_narrative(
                    action_type, {'reason': 'local_employment'}, 'zh-CN',
                    stored='x')
                self.assertIn('本地就业', served)
