"""What a team is actually allowed to submit, discovered rather than assumed.

The handoff requires the search space to come from the serializers and scenario
configuration, not from a convenient subset someone typed out. So the dimension
list is built by walking the DRF serializer registry that the write endpoints
use, and every bound is established by *probing the real serializer* rather than
by reading its source: a field is "non-negative" here because `-1` was offered
and refused, not because a `validate_` method appeared to say so.

That distinction matters for this handoff specifically. A constraint that exists
in one code path and not another reads identically in the source of the path
that has it.
"""
import decimal
import json

from rest_framework import serializers as drf

# The write paths a team can reach. `partial` is the per-type PATCH endpoint,
# `full` is the whole-submission PUT/POST. Both are taken from
# `core.views.decisions`, so a new decision type appears here by being routed,
# not by being remembered.
def api_surface():
    from core.views.decisions import _TYPE_MAP
    from core.serializers.decisions import DecisionSubmissionSerializer

    nested = {}
    for name, field in DecisionSubmissionSerializer().get_fields().items():
        target = field
        many = isinstance(field, drf.ListSerializer)
        if many:
            target = field.child
        if isinstance(target, drf.Serializer):
            nested[name] = {'serializer': type(target), 'many': many}

    partial = {}
    for decision_type, (related_name, serializer_cls, one_to_one) in _TYPE_MAP.items():
        partial[related_name] = {
            'decision_type': decision_type,
            'serializer': serializer_cls,
            'one_to_one': one_to_one,
        }
    return nested, partial


# Values every numeric dimension is probed with. Chosen to cover the boundary
# classes the handoff names: zero, negative, absurd magnitude, and the
# fractional case that rounding rules can disagree about.
NUMERIC_PROBES = [
    ('negative_one', -1),
    ('negative_large', -10 ** 9),
    ('zero', 0),
    ('one', 1),
    ('fraction', decimal.Decimal('0.005')),
    ('large', 10 ** 9),
    ('overflow_int32', 2 ** 31),
    ('huge', 10 ** 15),
]

TEXT_PROBES = [
    ('empty', ''),
    ('long', 'x' * 5000),
]


def field_kind(field):
    if isinstance(field, (drf.IntegerField, drf.FloatField, drf.DecimalField)):
        return 'numeric'
    if isinstance(field, drf.ChoiceField):
        return 'choice'
    if isinstance(field, drf.JSONField):
        return 'json'
    if isinstance(field, (drf.CharField,)):
        return 'text'
    if isinstance(field, drf.PrimaryKeyRelatedField):
        return 'reference'
    if isinstance(field, drf.BooleanField):
        return 'boolean'
    return type(field).__name__


def declared_bounds(field):
    """What the field says about itself, before anything is probed."""
    out = {}
    for attr in ('min_value', 'max_value', 'max_digits', 'decimal_places',
                 'max_length'):
        value = getattr(field, attr, None)
        if value is not None:
            out[attr] = value
    if isinstance(field, drf.ChoiceField):
        out['choices'] = list(field.choices)
    return out


def probe_field(serializer_cls, field_name, base_payload, value):
    """Offer one value for one field and report whether it was accepted."""
    payload = dict(base_payload)
    payload[field_name] = value
    serializer = serializer_cls(data=payload)
    if serializer.is_valid():
        return {'accepted': True, 'errors': None}
    errors = serializer.errors
    # Only this field's verdict is interesting; other fields may be missing
    # because the base payload is deliberately minimal.
    field_errors = errors.get(field_name)
    if field_errors is None:
        return {'accepted': True, 'errors': None, 'other_field_errors':
                json.loads(json.dumps(errors, default=str))}
    return {'accepted': False,
            'errors': [str(e) for e in field_errors]}
