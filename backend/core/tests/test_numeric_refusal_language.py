"""An over-long number is refused in the student's language, by business name.

The 2026-09-21 refusal sweep left one kind of English sentence a student could
plainly meet: Django REST Framework's own numeric refusals. Type a sixteen-digit
amount into an unbounded input and the server said "Ensure that there are no
more than 15 digits in total."; type a huge unit count and it said "Ensure this
value is less than or equal to 2147483647." `DecisionSaveAlert` prints whatever
arrives, so that is what a student working in Chinese read.

The frontend now bounds every student number input
(`src/decisionInputLimits.js`). This module pins the safety net behind it: every
decision-write route rewrites DRF's numeric-range and digit-count refusals into
a catalogue sentence, in the language the route already uses, naming the field
by its business label. The refusals are recognised by DRF's error CODE
(`ErrorDetail.code`), never by their English text.

Every route test here was red before `core/utils/numeric_refusals.py` existed.
"""
import re
from decimal import Decimal

from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from core.models.decisions import DecisionFinancing
from core.tests.test_paid_research import PaidResearchBase
from core.utils.participant_messages import (
    FIELD_LABELS, MESSAGES, field_label, participant_message)

LANGUAGES = ('zh-CN', 'en')

# What DRF says by default. None of it may reach a student on these routes.
DRF_DEFAULTS = re.compile(
    r'Ensure (that|this)|A valid (number|integer) is required|'
    r'String value too large|no more than \d+ (digits|decimal places)|'
    r'\d{6,}', re.IGNORECASE)
# A storage name: two or more lower-case words joined by underscores.
STORAGE_NAME = re.compile(r'\b[a-z]+(_[a-z0-9]+)+\b')

SIXTEEN_DIGITS = 1234567890123456
PAST_INT32 = 99999999999


def has_cjk(text):
    return any('一' <= ch <= '鿿' for ch in str(text))


def leaves(node):
    """Every sentence in a DRF error body, however deeply it is nested."""
    if isinstance(node, dict):
        for value in node.values():
            yield from leaves(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from leaves(value)
    elif node is not None:
        yield str(node)


class NumericRefusalBase(PaidResearchBase):

    def patch(self, decision_type, body, language):
        return self.client.patch(
            f'/api/games/{self.game.id}/teams/{self.team.id}'
            f'/decisions/round/1/{decision_type}/',
            body, format='json', HTTP_ACCEPT_LANGUAGE=language)

    def assert_business_sentence(self, response, field, key, language,
                                 also=()):
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(
            [str(item) for item in response.data[field]],
            [participant_message(
                each, language=language, field=field_label(field, language))
             for each in (key, *also)],
            response.data)
        for sentence in leaves(response.data):
            self.assertIsNone(DRF_DEFAULTS.search(sentence), sentence)
            self.assertIsNone(STORAGE_NAME.search(sentence), sentence)
            self.assertNotIn(field, sentence)
            self.assertEqual(has_cjk(sentence), language == 'zh-CN', sentence)
        self.assertIn(FIELD_LABELS[field][language],
                      str(response.data[field][0]))


class PerTypeRouteTests(NumericRefusalBase):
    """PATCH decisions/round/N/<type>/ -- the route every decision page uses."""

    def both(self, decision_type, body, field, key, also=()):
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assert_business_sentence(
                    self.patch(decision_type, body, language),
                    field, key, language, also=also)

    def test_sixteen_digits_of_new_borrowing(self):
        """The defect verbatim: `max_digits` on a money input with no `max`."""
        self.both('financing', {'new_debt': SIXTEEN_DIGITS}, 'new_debt',
                  'number_too_large')
        self.assertFalse(DecisionFinancing.objects.exists())

    def test_too_many_whole_digits_in_a_dividend(self):
        self.both('financing', {'dividend_per_share': '12345678.5'},
                  'dividend_per_share', 'number_too_large')

    def test_too_many_decimal_places_in_a_dividend(self):
        self.both('financing', {'dividend_per_share': '0.123456'},
                  'dividend_per_share', 'number_too_many_decimals')

    def test_a_headcount_past_the_integer_range(self):
        """`max_value`: 'less than or equal to 2147483647'."""
        self.both('talent', {'rd_headcount': PAST_INT32}, 'rd_headcount',
                  'number_too_large')

    def test_a_headcount_below_the_integer_range(self):
        """`min_value` fires beside this codebase's own non-negative rule, so
        the student reads both -- and both in one language."""
        self.both('talent', {'rd_headcount': -PAST_INT32}, 'rd_headcount',
                  'number_too_small', also=('non_negative',))

    def test_a_fractional_headcount(self):
        self.both('talent', {'rd_headcount': '10.5'}, 'rd_headcount',
                  'whole_number_required')

    def test_text_in_a_money_field(self):
        self.both('esg', {'environmental_investment': 'lots'},
                  'environmental_investment', 'number_required')

    def test_two_bad_fields_are_both_named(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                response = self.patch('financing', {
                    'new_debt': SIXTEEN_DIGITS, 'new_equity': SIXTEEN_DIGITS,
                }, language)
                self.assertEqual(response.status_code, 400)
                for field in ('new_debt', 'new_equity'):
                    self.assertEqual(
                        str(response.data[field][0]),
                        participant_message(
                            'number_too_large', language=language,
                            field=field_label(field, language)))

    def test_this_codebases_own_sentences_are_left_alone(self):
        """They carry DRF's catch-all code `invalid` too, and must not be
        mistaken for DRF's 'A valid number is required.'"""
        for language in LANGUAGES:
            with self.subTest(language=language):
                response = self.patch('financing', {'new_debt': -5}, language)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    str(response.data['new_debt'][0]),
                    participant_message(
                        'non_negative', language=language,
                        field=field_label('new_debt', language)))

    def test_a_legitimate_large_decision_is_still_accepted(self):
        """No rule moved: the largest storable amount still saves."""
        response = self.patch(
            'financing', {'new_debt': '0', 'dividend_per_share': '999999.9999'},
            'en')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(DecisionFinancing.objects.get().dividend_per_share,
                         Decimal('999999.9999'))


class WholeSubmissionRouteTests(NumericRefusalBase):
    """POST decisions/round/N/ -- the autosave. Errors arrive nested."""

    def test_nested_financing_and_a_nested_list_row(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                response = self.client.post(
                    f'/api/games/{self.game.id}/teams/{self.team.id}'
                    '/decisions/round/1/',
                    {'financing': {'new_debt': SIXTEEN_DIGITS},
                     'market_entries': [
                         {'initial_investment': SIXTEEN_DIGITS}]},
                    format='json', HTTP_ACCEPT_LANGUAGE=language)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(
                    str(response.data['financing']['new_debt'][0]),
                    participant_message(
                        'number_too_large', language=language,
                        field=field_label('new_debt', language)))
                self.assertEqual(
                    str(response.data['market_entries'][0]
                        ['initial_investment'][0]),
                    participant_message(
                        'number_too_large', language=language,
                        field=field_label('initial_investment', language)))


class SupplyChainRouteTests(NumericRefusalBase):
    """The supply-chain pages write through their own views and serializers."""

    def test_buffer_days_past_the_integer_range(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                response = self.client.post(
                    f'/api/games/{self.game.id}/teams/{self.team.id}'
                    '/sc/round/1/inventory/',
                    {'inventory': [{'buffer_days': PAST_INT32}]},
                    format='json', HTTP_ACCEPT_LANGUAGE=language)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(
                    [str(item) for item in response.data['buffer_days']],
                    [participant_message(
                        'number_too_large', language=language,
                        field=field_label('buffer_days', language))])


class RewriteUnitTests(PaidResearchBase):
    """The shapes no route above produces."""

    def rewrite(self, detail, language='zh-CN'):
        from core.utils.numeric_refusals import localise_numeric_refusals
        return localise_numeric_refusals(detail, language)

    def test_a_field_with_no_business_label_is_not_named_at_all(self):
        """Better an unnamed sentence than a storage name in a Chinese one."""
        detail = {'some_new_column': [ErrorDetail('x', code='max_digits')]}
        for language in LANGUAGES:
            text = str(self.rewrite(detail, language)['some_new_column'][0])
            self.assertEqual(text, participant_message(
                'number_too_large', language=language,
                field=MESSAGES['this_number'][language]))
            self.assertNotIn('some', text)

    def test_the_code_survives_and_the_shape_is_unchanged(self):
        detail = {'rows': [{}, {'new_debt': [
            ErrorDetail('x', code='max_string_length')]}]}
        out = self.rewrite(detail)
        self.assertEqual(out['rows'][0], {})
        self.assertEqual(out['rows'][1]['new_debt'][0].code,
                         'max_string_length')

    def test_other_codes_are_left_exactly_as_they_were(self):
        detail = {'new_debt': [ErrorDetail('This field is required.',
                                           code='required')]}
        self.assertEqual(self.rewrite(detail), detail)

    def test_an_unsupported_language_falls_back_to_english(self):
        detail = {'new_debt': [ErrorDetail('x', code='max_value')]}
        self.assertEqual(
            str(self.rewrite(detail, 'fr')['new_debt'][0]),
            participant_message('number_too_large', language='en',
                                field=field_label('new_debt', 'en')))


class LabelCoverageTests(PaidResearchBase):
    """A numeric field a student can write must have a business label, or the
    safety net has nothing to call it."""

    def test_every_writable_numeric_decision_field_is_labelled(self):
        from core.serializers import decisions as decision_serializers
        from core.serializers import sc_serializers
        from core.views.decisions import _TYPE_MAP

        classes = {cls for _name, cls, _one in
                   decision_serializers._NESTED_CONFIG}
        classes |= {cls for _name, cls, _one in _TYPE_MAP.values()}
        classes |= {
            value for name, value in vars(sc_serializers).items()
            if name.endswith('WriteSerializer') and isinstance(value, type)}
        numeric = (serializers.IntegerField, serializers.FloatField,
                   serializers.DecimalField)
        unlabelled = sorted({
            f'{cls.__name__}.{name}'
            for cls in classes
            for name, field in cls().get_fields().items()
            if isinstance(field, numeric) and not field.read_only
            and name not in FIELD_LABELS})
        self.maxDiff = None
        self.assertEqual(unlabelled, [])
        self.assertGreaterEqual(len(classes), 20)
