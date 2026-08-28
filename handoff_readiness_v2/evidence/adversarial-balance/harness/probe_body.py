"""Runs inside `manage.py shell` against the disposable database."""
import decimal
import json
import sys

from rest_framework import serializers as drf

from core.models import Game, Round, Team
from core.serializers.decisions import DecisionSubmissionSerializer
from core.views.decisions import _TYPE_MAP

game = Game.objects.order_by('-id').first()
team = Team.objects.filter(game=game).order_by('id').first()
rnd = Round.objects.filter(game=game).order_by('round_number').first()

NUMERIC_PROBES = [
    ('negative_one', -1),
    ('negative_large', -(10 ** 9)),
    ('zero', 0),
    ('one', 1),
    ('fraction', '0.005'),
    ('large', 10 ** 9),
    ('overflow_int32', 2 ** 31),
    ('huge', 10 ** 15),
]


def kind(field):
    if isinstance(field, (drf.IntegerField, drf.FloatField, drf.DecimalField)):
        return 'numeric'
    if isinstance(field, drf.ChoiceField):
        return 'choice'
    if isinstance(field, drf.JSONField):
        return 'json'
    if isinstance(field, drf.CharField):
        return 'text'
    if isinstance(field, drf.PrimaryKeyRelatedField):
        return 'reference'
    if isinstance(field, drf.BooleanField):
        return 'boolean'
    return type(field).__name__


def declared(field):
    out = {}
    for attr in ('min_value', 'max_value', 'max_digits', 'decimal_places',
                 'max_length'):
        v = getattr(field, attr, None)
        if v is not None:
            out[attr] = v
    if isinstance(field, drf.ChoiceField):
        out['choices'] = [c for c in field.choices]
    return out


def plausible(field):
    """A value the field should accept, so other fields do not mask a verdict."""
    if isinstance(field, drf.DecimalField):
        return '1.00'
    if isinstance(field, drf.IntegerField):
        return 1
    if isinstance(field, drf.BooleanField):
        return True
    if isinstance(field, drf.ChoiceField):
        choices = [c for c in field.choices]
        return choices[0] if choices else None
    if isinstance(field, drf.PrimaryKeyRelatedField):
        qs = field.get_queryset()
        obj = qs.first() if qs is not None else None
        return obj.pk if obj is not None else None
    if isinstance(field, drf.JSONField):
        return []
    if isinstance(field, drf.CharField):
        return 'x'
    return None


def base_payload(serializer_cls):
    payload = {}
    for name, field in serializer_cls().get_fields().items():
        if field.read_only or not field.required:
            continue
        value = plausible(field)
        if value is not None:
            payload[name] = value
    return payload


def verdict(serializer_cls, base, field_name, value):
    data = dict(base)
    data[field_name] = value
    ser = serializer_cls(data=data)
    ok = ser.is_valid()
    if ok:
        return {'accepted': True}
    errs = ser.errors.get(field_name)
    if errs is None:
        # Refused, but not because of this field.
        return {'accepted': True, 'blocked_elsewhere': True}
    return {'accepted': False, 'error': str(errs[0])}


inventory = {'decision_types': {}, 'path_uniformity': {}, 'totals': {}}
dimension_count = 0

for decision_type, (related, serializer_cls, one_to_one) in sorted(_TYPE_MAP.items()):
    base = base_payload(serializer_cls)
    fields = {}
    for name, field in serializer_cls().get_fields().items():
        if field.read_only:
            continue
        entry = {
            'kind': kind(field),
            'required': field.required,
            'declared': declared(field),
        }
        if entry['kind'] == 'numeric':
            probes = {}
            for label, value in NUMERIC_PROBES:
                if isinstance(field, drf.IntegerField) and label == 'fraction':
                    continue
                probes[label] = verdict(serializer_cls, base, name, value)
            entry['probes'] = probes
            accepted_negative = any(
                probes[l]['accepted'] for l in ('negative_one', 'negative_large')
                if l in probes)
            entry['accepts_negative'] = accepted_negative
            entry['accepts_unbounded_magnitude'] = probes.get(
                'huge', {}).get('accepted', False)
        fields[name] = entry
        dimension_count += 1
    inventory['decision_types'][decision_type] = {
        'related_name': related,
        'serializer': serializer_cls.__name__,
        'one_to_one': one_to_one,
        'fields': fields,
    }

# --- path uniformity -------------------------------------------------------
# The whole-submission serializer runs cross-field rules that the per-type
# PATCH path never reaches, because PATCH validates one nested serializer at a
# time. Offer the same payload to both and compare the verdicts.
divergences = []
checks = []

rd_serializer = _TYPE_MAP['rd'][1]


def valid_rd_item():
    """An R&D row this team is actually allowed to submit.

    The first attempt at this check picked the first platform and feature it
    found, and both API paths refused it because that feature was not available
    on the team's platform generation. Two refusals for an unrelated reason look
    exactly like agreement, so the check reported uniformity without ever
    reaching the rule it was written to test.
    """
    fields = rd_serializer().get_fields()
    platforms = list(fields['team_platform'].get_queryset()[:12])
    features = list(fields['feature'].get_queryset()[:40])
    for platform in platforms:
        for feature in features:
            candidate = {'team_platform': platform.pk, 'feature': feature.pk,
                         'method': 'in_house', 'amount': '1000.00',
                         'target_level': 1}
            ser = rd_serializer(data=candidate)
            if ser.is_valid():
                return candidate
    return None


rd_item = valid_rd_item()
checks = []
divergences = []

if rd_item is None:
    checks.append({
        'payload': 'two R&D investments naming the same platform and feature',
        'inconclusive': True,
        'why': 'no platform/feature pair in this scenario validated on its own, '
               'so the duplicate rule could not be reached',
    })
else:
    # `team` and `round` are required fields of the submission serializer, and
    # DRF only calls `validate()` once every field has validated. Omitting them
    # meant the cross-row rule was never reached and the check reported
    # agreement — twice, for two different wrong reasons.
    def full_verdict(rows):
        ser = DecisionSubmissionSerializer(data={
            'team': team.pk, 'round': rnd.pk, 'rd_investments': rows})
        ser.is_valid()
        return ser.errors

    second = dict(rd_item)
    # A different feature on the same platform, so the control differs from the
    # duplicate only in being unambiguous.
    fields = rd_serializer().get_fields()
    for feature in fields['feature'].get_queryset()[:40]:
        if feature.pk != rd_item['feature']:
            candidate = dict(rd_item, feature=feature.pk)
            if rd_serializer(data=candidate).is_valid():
                second = candidate
                break

    control_errors = full_verdict([dict(rd_item), second])
    duplicate_errors = full_verdict([dict(rd_item), dict(rd_item)])

    full_rejects_rd = 'rd_investments' in duplicate_errors
    control_accepted = 'rd_investments' not in control_errors

    partial_rejects = False
    partial_errors = []
    for item in [dict(rd_item), dict(rd_item)]:
        ser = rd_serializer(data=item)
        if not ser.is_valid():
            partial_rejects = True
            partial_errors.append(str(ser.errors))

    check = {
        'payload': 'two R&D investments naming the same platform and feature',
        'item': rd_item,
        'control_item': second,
        'why_it_matters': (
            'The whole-submission serializer rejects this because the outcome '
            'would otherwise depend on row order — the defect class V2-012 was '
            'raised for. The per-type PATCH path validates each row on its own '
            'and never runs the cross-row rule.'),
        'control_distinct_pair_accepted_by_full_api': control_accepted,
        'full_api_rejects': full_rejects_rd,
        'partial_api_rejects': partial_rejects,
        'full_api_error': str(duplicate_errors.get('rd_investments')) if full_rejects_rd else None,
        'partial_api_error': partial_errors or None,
        'conclusive': bool(control_accepted and full_rejects_rd),
    }
    checks.append(check)
    if not check['conclusive']:
        check['note'] = (
            'Inconclusive: the control pair must be accepted and the duplicate '
            'pair rejected by the full API, or this check is not measuring the '
            'rule it names.')
    elif check['full_api_rejects'] != check['partial_api_rejects']:
        divergences.append(check)

inventory['path_uniformity'] = {'checks': checks, 'divergences': divergences}
inventory['totals'] = {
    'decision_types': len(inventory['decision_types']),
    'dimensions': dimension_count,
    'unprobed_types': sum(
        1 for t in inventory['decision_types'].values() if not t['fields']),
    'numeric_dimensions_accepting_negative': sum(
        1 for t in inventory['decision_types'].values()
        for f in t['fields'].values() if f.get('accepts_negative')),
    'path_divergences': len(divergences),
}

print('game', game.id, 'team', team.id, 'round', rnd.round_number)
print('decision types', inventory['totals']['decision_types'],
      '| dimensions', inventory['totals']['dimensions'])
print('numeric dimensions accepting a negative value:',
      inventory['totals']['numeric_dimensions_accepting_negative'])
print('full-vs-partial divergences:', len(divergences))
print('---INVENTORY-JSON---')
print(json.dumps(inventory, default=str))
