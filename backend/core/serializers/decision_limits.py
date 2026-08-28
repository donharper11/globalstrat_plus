"""One table of what a decision field may not be, shared by every write path.

GSP-CRV2-06 found thirteen investment and headcount fields that accepted a
negative value, and `core/engine/costs.py` adds several of them straight into
`strategy_expense`. A negative investment was therefore income: a team entering
`environmental_investment = -5,000,000` turned a $1.13M loss into a $3.99M
profit with no revenue, and a negative headcount — multiplied by a salary band
— was worth fifty billion.

Seven more fields accepted a negative value but happened to be masked in the
first probe because another field in the payload failed first. A guard that
depends on a neighbouring field failing is not a guard, so they are listed here
too, along with one supply-chain field.

The rule lives here rather than as another `validate_<field>` method beside the
eight that already existed, because the eight that already existed are the
reason this looked covered. A field is protected by being in this table, and
`test_decision_limits` fails if a numeric decision field is in neither this
table nor `NEGATIVE_ALLOWED`.
"""
from django.core.exceptions import FieldError
from rest_framework import serializers

# Serializer class name → fields that must be >= 0.
#
# Keyed by name rather than by class to avoid an import cycle: the serializer
# modules import this one.
NON_NEGATIVE_FIELDS = {
    'DecisionESGSerializer': (
        'environmental_investment', 'social_investment',
    ),
    'DecisionMarketEntrySerializer': (
        'initial_investment',
    ),
    'DecisionPartnershipSerializer': (
        'annual_investment',
    ),
    'DecisionPlantSerializer': (
        'capacity_units', 'contract_mfg_volume',
    ),
    'DecisionPlatformDevelopmentSerializer': (
        'committed_cost',
    ),
    'DecisionTalentSerializer': (
        'rd_headcount', 'commercial_headcount', 'operations_headcount',
        'rd_training_budget', 'commercial_training_budget',
        'operations_training_budget',
    ),
    # Accepted a negative value; the first probe missed them because another
    # field in the same payload failed first.
    'DecisionMarketingSerializer': (
        'channel_digital_pct', 'channel_traditional_pct', 'channel_trade_pct',
        'distribution_investment', 'sales_team_count',
    ),
    'DecisionRDInvestmentSerializer': (
        'calculated_cost', 'target_level',
    ),
    'SourcingAllocationWriteSerializer': (
        'volume_commitment_units',
    ),
}

# Numeric decision fields that may legitimately be negative, with the reason.
# Empty today: no decision a team submits is a negative quantity of anything.
# The list exists so that adding one is a deliberate, reviewable act.
NEGATIVE_ALLOWED = {}


def non_negative_message(field_name):
    return f'{field_name} must be >= 0.'


class NonNegativeFieldsMixin:
    """Attach a `>= 0` rule to the fields this serializer declares in the table.

    Applied at the field level rather than in `validate()` so each field reports
    its own refusal, and so a payload with two bad fields names both. `validate()`
    only runs once every field has passed, which is exactly how the duplicate
    R&D rule came to be silent on the per-type path.
    """

    def get_fields(self):
        fields = super().get_fields()
        for name in NON_NEGATIVE_FIELDS.get(type(self).__name__, ()):
            field = fields.get(name)
            if field is None:
                # The table names a field this serializer no longer has. Fail
                # loudly: a stale entry is a guard nobody is getting.
                raise ImproperlyConfiguredDecisionLimit(
                    f'{type(self).__name__} has no field {name!r}, but '
                    'decision_limits.NON_NEGATIVE_FIELDS says it does.')
            field.validators = list(field.validators) + [
                _NonNegative(name),
            ]
        return fields


class ImproperlyConfiguredDecisionLimit(Exception):
    pass


class _NonNegative:
    """A validator with a stable identity, so tests can find it on a field."""

    requires_context = False

    def __init__(self, field_name):
        self.field_name = field_name

    def __call__(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(non_negative_message(self.field_name))

    def __eq__(self, other):
        return (isinstance(other, _NonNegative)
                and other.field_name == self.field_name)

    def __repr__(self):
        return f'<NonNegative {self.field_name}>'


# ---------------------------------------------------------------------------
# The same policy, asked of persisted rows
# ---------------------------------------------------------------------------
# The serializer guards above stop a negative value entering through either
# supported API. They say nothing about a row that is already in the database:
# a data migration, an import, `manage.py shell`, the admin, or a restore can
# put one there, and the engine reads rows rather than payloads. So scoring
# asks the same question of what it is about to score.
#
# The answer is to refuse, not to clamp. A clamped value silently changes a
# team's submitted decision into a different one and scores that instead, which
# is a worse failure than not scoring: it is wrong and it is invisible. The
# engine stops and names the row.

# How each protected model reaches a game and round. Everything a team submits
# through the decision endpoints hangs off `DecisionSubmission`; the supply
# chain rows carry their own team and round.
_SCOPE_FILTERS = {
    'submission': lambda game, rnd: {
        'submission__team__game': game, 'submission__round': rnd},
    'team_round': lambda game, rnd: {'team__game': game, 'round': rnd},
}

_SCOPE_BY_MODEL = {
    'SourcingAllocation': 'team_round',
}


def protected_model_fields():
    """`{model: (field, ...)}` derived from the serializer table.

    Derived rather than declared a second time: two tables would be two places
    to forget, and the point of this module is that there is one.
    """
    import importlib

    mapping = {}
    for module_name in ('core.serializers.decisions',
                        'core.serializers.sc_serializers'):
        module = importlib.import_module(module_name)
        for serializer_name, fields in NON_NEGATIVE_FIELDS.items():
            serializer_cls = getattr(module, serializer_name, None)
            if serializer_cls is None:
                continue
            model = serializer_cls.Meta.model
            mapping.setdefault(model, ())
            mapping[model] = tuple(dict.fromkeys(mapping[model] + tuple(fields)))
    return mapping


def persisted_violations(game, round_obj):
    """Every persisted decision row holding a negative protected value.

    Returns a list of dicts naming the model, row, field and value, so the
    refusal can say which row to correct rather than that something is wrong.
    """
    violations = []
    for model, fields in sorted(protected_model_fields().items(),
                                key=lambda item: item[0].__name__):
        scope = _SCOPE_BY_MODEL.get(model.__name__, 'submission')
        try:
            queryset = model.objects.filter(
                **_SCOPE_FILTERS[scope](game, round_obj))
        except FieldError as error:
            # A model whose scope filter no longer matches its fields is
            # reported rather than skipped: an unscannable table is an
            # unchecked table, and silence here would read as "no violations".
            violations.append({
                'model': model.__name__, 'row': None, 'field': None,
                'value': None,
                'detail': (f'{model.__name__} could not be scoped to this '
                           f'round: {error}'),
            })
            continue
        for row in queryset.order_by('pk'):
            for field in fields:
                value = getattr(row, field, None)
                if value is not None and value < 0:
                    violations.append({
                        'model': model.__name__,
                        'row': row.pk,
                        'submission': getattr(row, 'submission_id', None),
                        'team': getattr(row, 'team_id', None),
                        'field': field,
                        'value': str(value),
                    })
    return violations


def describe_violations(violations, limit=10):
    parts = []
    for item in violations[:limit]:
        if item.get('detail'):
            parts.append(item['detail'])
            continue
        where = (f"submission {item['submission']}"
                 if item.get('submission') is not None
                 else f"team {item.get('team')}")
        parts.append(
            f"{item['model']} row {item['row']} ({where}): "
            f"{item['field']} = {item['value']}")
    if len(violations) > limit:
        parts.append(f'... and {len(violations) - limit} more')
    return '; '.join(parts)
