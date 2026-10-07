"""What language a team's memo feedback and audience label reach a reader in.

Both were found by the ten-round browser pass on candidate `a0631e5d`, on a
Simplified-Chinese student's own screen:

* the memo evaluation read *"Automated evaluation unavailable. Score based on
  submission completeness."* — English, although `_FALLBACK_TEXT` carries a
  complete Chinese block. Nothing was missing from the catalogue:
  `_fallback_evaluation` asks for the TEAM's language, a team's language is its
  first-enrolled member's, and that member states English.
* the audience was *"Board of Directors"*, which is the English half of
  `AUDIENCE_CHOICES` served straight through `get_audience_display()`.

The audience is simply a label and is now translated. The evaluation is the
more careful case, and the rule these tests pin is the line between the two
halves of it: **a fallback evaluation is template text and is re-rendered for
the reader; a model-generated one is prose and is served exactly as stored.**

What this does NOT decide is what language a team-wide artefact should be
written in when a team's members differ. That question is open and belongs to
the owner; this takes only the case where the reader can be served their own
language without changing anything that was stored.
"""
from django.test import SimpleTestCase

from core.rag.communication_eval import (_FALLBACK_TEXT,
                                         localized_fallback_evaluation)
from core.utils.participant_messages import communication_audience_label


def fallback_like(language='en'):
    """The shape `_fallback_evaluation` returns, in one language."""
    text = _FALLBACK_TEXT[language]
    return {
        'overall_score': 0.55,
        'criteria_scores': {
            'strategic_consistency': {'score': 0.55,
                                      'feedback': text['criterion']},
        },
        'strengths': [text['strength']],
        'gaps': [text['gap']],
        'consistency_flags': [],
        'framework_references': [],
        'overall_feedback': text['overall'],
        'fallback': True,
    }


class FallbackEvaluationLanguageTests(SimpleTestCase):

    def test_a_chinese_reader_gets_the_chinese_fallback(self):
        served = localized_fallback_evaluation(fallback_like('en'), 'zh-CN')
        zh = _FALLBACK_TEXT['zh-CN']
        self.assertEqual(served['overall_feedback'], zh['overall'])
        self.assertEqual(served['strengths'], [zh['strength']])
        self.assertEqual(served['gaps'], [zh['gap']])
        self.assertEqual(
            served['criteria_scores']['strategic_consistency']['feedback'],
            zh['criterion'])

    def test_the_score_is_not_touched(self):
        """Only wording is re-rendered. The grade is what was stored."""
        stored = fallback_like('en')
        served = localized_fallback_evaluation(stored, 'zh-CN')
        self.assertEqual(served['overall_score'], stored['overall_score'])
        self.assertEqual(
            served['criteria_scores']['strategic_consistency']['score'],
            stored['criteria_scores']['strategic_consistency']['score'])

    def test_what_was_stored_is_not_modified(self):
        stored = fallback_like('en')
        before = dict(stored)
        localized_fallback_evaluation(stored, 'zh-CN')
        self.assertEqual(stored['overall_feedback'], before['overall_feedback'])
        self.assertEqual(stored['strengths'], before['strengths'])

    def test_a_model_generated_evaluation_is_served_as_stored(self):
        """The line this function must not cross.

        Model prose cannot be re-rendered in another language, and pretending
        otherwise would silently replace a team's actual feedback with a
        template. An evaluation with no `fallback` marker is returned
        untouched, whatever the reader's language.
        """
        real = {'overall_score': 0.81,
                'overall_feedback': 'The memo ties the Africa entry to the '
                                    'talent plan convincingly.',
                'strengths': ['Specific about the ESG spend'],
                'gaps': ['No mention of currency risk'],
                'criteria_scores': {}}
        self.assertIs(localized_fallback_evaluation(real, 'zh-CN'), real)

    def test_an_empty_strength_list_stays_empty(self):
        """An over-limit memo earns no strength; it must not gain one."""
        stored = fallback_like('en')
        stored['strengths'] = []
        served = localized_fallback_evaluation(stored, 'zh-CN')
        self.assertEqual(served['strengths'], [])

    def test_an_unknown_reader_language_changes_nothing(self):
        stored = fallback_like('en')
        self.assertIs(localized_fallback_evaluation(stored, 'fr'), stored)

    def test_none_and_junk_are_handled(self):
        self.assertIsNone(localized_fallback_evaluation(None, 'zh-CN'))
        self.assertEqual(localized_fallback_evaluation({}, 'zh-CN'), {})


class AudienceLabelTests(SimpleTestCase):

    def test_every_audience_reads_in_chinese(self):
        for code, expected in (('BOARD', '董事会'),
                               ('EMPLOYEES', '全体员工'),
                               ('INVESTORS', '投资者群体'),
                               ('REGULATORS', '监管机构'),
                               ('PUBLIC', '媒体／公开声明'),
                               ('PARTNER', '联盟／合资伙伴')):
            self.assertEqual(
                communication_audience_label(code, 'ignored', 'zh-CN'),
                expected)

    def test_english_is_the_wording_the_model_already_used(self):
        self.assertEqual(
            communication_audience_label('BOARD', 'Board of Directors', 'en'),
            'Board of Directors')

    def test_an_audience_the_table_has_not_been_taught_keeps_its_display(self):
        """A new choice must render a name, not a token."""
        self.assertEqual(
            communication_audience_label('SUPPLIERS', 'Key Suppliers', 'zh-CN'),
            'Key Suppliers')

    def test_with_no_display_to_fall_back_on_the_token_is_prettified(self):
        self.assertEqual(
            communication_audience_label('KEY_SUPPLIERS', '', 'zh-CN'),
            'Key Suppliers')
