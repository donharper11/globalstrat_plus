"""Django REST Framework's numeric refusals, re-said for a participant.

A number DRF will not store is refused by DRF itself, before any rule of this
codebase runs, in DRF's words: "Ensure that there are no more than 15 digits in
total.", "Ensure this value is less than or equal to 2147483647.". Those
sentences are English whatever the student reads, name no field, and quote a
storage limit nobody can act on. The decision-write boundary
(`core.views.decisions.CompetitionDecisionWriteMixin.handle_exception`) passes
every validation refusal through here on its way out.

A refusal is recognised by its **code** (`ErrorDetail.code`), which is DRF's
contract, and never by its English text, which is DRF's copy and changes with
the active locale. The field is named by `FIELD_LABELS`; a field with no label
is called "this number" rather than by its storage name.

`invalid` needs one more step, because it is also the code DRF gives every
`ValidationError` raised without one -- which is every business sentence this
codebase raises from a serializer. Rewriting on the code alone would replace
"new borrowing cannot be negative" with "new borrowing must be a number". An
`invalid` refusal is therefore rewritten only when it *is* one of DRF's own
numeric `invalid` messages: compared against the message objects on DRF's field
classes, evaluated in the same thread and so the same locale as the refusal,
not against a copy of their English wording kept here.

The response keeps its shape, its keys, its status and each refusal's code.
Only the sentence changes, so a client that reads codes or keys sees no
difference.
"""
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from core.utils.participant_messages import (
    FIELD_LABELS, SUPPORTED_LANGUAGES, field_label, participant_message)

# DRF error code -> catalogue sentence. `max_string_length` is DRF refusing a
# numeric *string* over 1,000 characters: too large, said the long way round.
SENTENCE_FOR_CODE = {
    'max_digits': 'number_too_large',
    'max_whole_digits': 'number_too_large',
    'max_value': 'number_too_large',
    'max_string_length': 'number_too_large',
    'max_decimal_places': 'number_too_many_decimals',
    'min_value': 'number_too_small',
}

# DRF field class -> the sentence for that class's own `invalid` refusal.
_INVALID_SENTENCES = (
    (serializers.IntegerField, 'whole_number_required'),
    (serializers.FloatField, 'number_required'),
    (serializers.DecimalField, 'number_required'),
)


def _sentence_key(detail):
    code = getattr(detail, 'code', None)
    if code in SENTENCE_FOR_CODE:
        return SENTENCE_FOR_CODE[code]
    if code == 'invalid':
        said = str(detail)
        for field_class, key in _INVALID_SENTENCES:
            if said == str(field_class.default_error_messages['invalid']):
                return key
    return None


def _label(field_name, language):
    if field_name in FIELD_LABELS:
        return field_label(field_name, language)
    return participant_message('this_number', language=language)


def localise_numeric_refusals(detail, language, field_name=None):
    """A copy of a `ValidationError.detail` with DRF's numeric refusals re-said.

    `field_name` is the nearest enclosing dictionary key, which is how DRF says
    which field a refusal belongs to at any depth: `{'financing': {'new_debt':
    [...]}}` and `{'market_entries': [{}, {'initial_investment': [...]}]}` both
    end in the field's own name. List positions are not names and are skipped.
    """
    if language not in SUPPORTED_LANGUAGES:
        language = 'en'
    if isinstance(detail, dict):
        return {
            key: localise_numeric_refusals(
                value, language,
                key if isinstance(key, str) and not key.isdigit()
                else field_name)
            for key, value in detail.items()}
    if isinstance(detail, (list, tuple)):
        return [localise_numeric_refusals(item, language, field_name)
                for item in detail]
    key = _sentence_key(detail)
    if key is None:
        return detail
    return ErrorDetail(
        participant_message(key, language=language,
                            field=_label(field_name, language)),
        code=detail.code)
