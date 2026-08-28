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
