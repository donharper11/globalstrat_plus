"""A Chinese communication is limited like an English one (R48 item 7).

`cc32a_views` counted a communication's words as `len(content.split())`, so a
Chinese memo -- written without spaces -- counted as one word, and the
assignment's `word_limit` never bound for a Chinese team. A limit that binds
one language and not the other is a fairness bug, and the integrator's decision
under R48 is: count CJK letters at 1.5 letters per word, added to the
space-split count of the rest.

The rule lives in one place on each side (`services/communication_words.py`,
`src/communicationWords.js`) and the cases below are repeated verbatim in
`communicationWords.test.js`, so the count a student watches on screen is the
count the server refuses on.
"""
from unittest import mock

from django.test import SimpleTestCase

from core.tests.test_student_refusal_language import StudentRefusalBase

# One row per case: (text, words). The same table is in the Jest test.
CASES = [
    ('', 0),
    ('   ', 0),
    ('one two three', 3),
    ('  spaced\tout\nwords  ', 3),
    # Three Han letters are two words; six are four.
    ('中文字', 2),
    ('中文字中文字', 4),
    # A single letter is still a word, never zero.
    ('中', 1),
    # 600 Han letters against a 300-word limit: 400 words, over the 10% grace.
    ('市' * 600, 400),
    # CJK punctuation separates and is not counted; the letters around it are.
    ('我们。他们', 3),
    ('市场，产品；价格。', 4),
    # Full-width digits and Latin letters are words, as their ASCII forms are.
    ('第１季度', 3),
    # Mixed text counts both parts.
    ('Q3 memo 我们将进入欧洲市场 end', 3 + 6),
    # Hiragana, Katakana and Hangul are letters in the same sense.
    ('ひらがな', 3),
    ('カタカナ', 3),
    ('한국어', 2),
    # Supplementary-plane Han (CJK Extension B) is counted too.
    ('\U00020000\U00020001\U00020002', 2),
]


class CountWordsTests(SimpleTestCase):

    def test_the_table(self):
        from core.services.communication_words import count_words
        for text, expected in CASES:
            with self.subTest(text=text):
                self.assertEqual(count_words(text), expected)

    def test_none_is_empty(self):
        from core.services.communication_words import count_words
        self.assertEqual(count_words(None), 0)

    def test_english_is_what_split_always_gave(self):
        from core.services.communication_words import count_words
        memo = 'word ' * 300
        self.assertEqual(count_words(memo), len(memo.split()))


class CommunicationWordLimitRouteTests(StudentRefusalBase):

    def assignment(self, word_limit=300):
        from decimal import Decimal
        from core.models import CommunicationAssignment
        return CommunicationAssignment.objects.create(
            scenario=self.scenario, code='memo', name='Memo',
            trigger_type='ROUND_MILESTONE', audience='BOARD',
            prompt_text='Write a memo.', word_limit=word_limit,
            trigger_condition={'round': 1}, evaluation_criteria=[],
            coherence_weight=Decimal('0.05'))

    def submit_url(self, assignment):
        return self.team_url(f'communications/{assignment.id}/submit/')

    def test_a_600_letter_chinese_memo_is_refused_against_a_300_word_limit(self):
        url = self.submit_url(self.assignment(300))
        self.both(lambda language: self.call(
            'post', url, {'content': '市' * 600}, language),
            400, 'communication_over_word_limit', field='detail',
            limit=300, count=400)

    def test_a_300_word_english_memo_is_accepted(self):
        url = self.submit_url(self.assignment(300))
        evaluation = {'overall_score': 0.7, 'criteria_scores': {},
                      'strengths': [], 'gaps': [], 'consistency_flags': [],
                      'framework_references': []}
        with mock.patch('core.rag.communication_eval.evaluate_communication',
                        return_value=evaluation) as evaluate:
            response = self.call('post', url, {'content': 'word ' * 300}, 'en')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['word_count'], 300)
        self.assertEqual(response.data['status'], 'evaluated')
        evaluate.assert_called_once()

    def test_a_300_word_chinese_memo_is_accepted_too(self):
        # 450 letters are 300 words: the limit binds at the same point.
        url = self.submit_url(self.assignment(300))
        with mock.patch('core.rag.communication_eval.evaluate_communication',
                        return_value={'overall_score': 0.7}):
            response = self.call('post', url, {'content': '市' * 450}, 'zh-CN')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['word_count'], 300)

    def test_mixed_text_counts_both_parts(self):
        # 20 English words and 30 Han letters (20 words) against a limit of 30:
        # 40 words, over the grace; neither half alone would be.
        url = self.submit_url(self.assignment(30))
        content = ('word ' * 20) + ('市' * 30)
        self.both(lambda language: self.call(
            'post', url, {'content': content}, language),
            400, 'communication_over_word_limit', field='detail',
            limit=30, count=40)

    def test_a_draft_is_counted_by_the_same_rule(self):
        assignment = self.assignment(300)
        url = self.team_url(f'communications/{assignment.id}/draft/')
        response = self.call('post', url, {'content': '市' * 600}, 'zh-CN')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['word_count'], 400)
        listed = self.call('get', self.team_url('communications/assignments/'),
                           None, 'zh-CN')
        self.assertEqual(listed.status_code, 200, listed.data)
        row = next(a for a in listed.data['assignments']
                   if a['id'] == assignment.id)
        self.assertEqual(row['draft_word_count'], 400)

    def test_a_submit_that_carries_no_content_keeps_the_drafts_count(self):
        # The draft was saved at 400 words; submitting without a body is
        # refused on that count, not on a recount of nothing.
        assignment = self.assignment(300)
        self.call('post', self.team_url(f'communications/{assignment.id}/draft/'),
                  {'content': '市' * 600}, 'zh-CN')
        self.both(lambda language: self.call(
            'post', self.submit_url(assignment), {}, language),
            400, 'communication_over_word_limit', field='detail',
            limit=300, count=400)
