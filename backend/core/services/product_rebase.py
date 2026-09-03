"""Re-basing a product onto another of the team's ready platforms.

The switch itself is cheap; what it costs is the stock already built on the
platform being left. A scenario-configured percentage of unit cost times the
units on hand at the moment of the switch is charged as its own line, on the
stated rationale that this is a new model launching and the old one
discontinuing.

Three things this service refuses to do, each because a predecessor did it and
it cost someone a round:

* **Resolve the platform anywhere but as of the round.** The association is
  round-versioned and the prior association is seeded on the first switch, so
  rounds resolved before it keep resolving to the platform they were scored
  against. BECSR's guarantee that "past rounds stay frozen" was false for every
  seeded portfolio because one round id was read as a round number.
* **Charge more than once.** The write-off is recorded on the history row that
  caused it, and a second switch in the same round updates that row rather than
  adding a charge beside it.
* **Half-apply.** Validation, write-off and association move together in one
  transaction: a switch that charged but did not move, or moved but did not
  charge, is worse than a refusal.
"""
from decimal import Decimal

from django.db import transaction

ZERO = Decimal('0')
DEFAULT_WRITE_OFF_PCT = Decimal('0.15')


class RebaseRefused(Exception):
    """The switch was refused. `status_code` is the HTTP status to return."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# Governing rule decisions for this module -- the write-off's cash treatment,
# its percentage basis and the round it takes effect in -- are recorded in
# `handoff_readiness_v2/GSP-CRV2-10_RULE_DECISIONS.md` (R1, R2, R3, R7). They
# are choices the specification does not uniquely determine, so reversing one
# is a rules decision rather than a bug fix.
def write_off_pct(scenario):
    """The authored markdown on stock left behind, as a fraction."""
    from core.engine.utils import get_config
    try:
        value = get_config(scenario, 'platform_switch_write_off_pct',
                           float(DEFAULT_WRITE_OFF_PCT))
        return Decimal(str(value))
    except (TypeError, ValueError):
        return DEFAULT_WRITE_OFF_PCT


def unsold_on_platform(product, round_number):
    """Units on hand for this product, and their unit cost, at the switch.

    The latest closing snapshot, not a sum across rounds: each round's row is a
    closing position, and summing them would write off stock that was sold
    rounds ago. BECSR records the same reasoning for the same reason.
    """
    from core.models.results_financials import RoundResultProductMarket

    rows = (RoundResultProductMarket.objects
            .filter(team_product=product, round_number__lte=round_number)
            .order_by('-round_number', 'market_id'))
    latest_round = rows[0].round_number if rows else None
    if latest_round is None:
        return 0, ZERO
    units = ZERO
    weighted_cost = ZERO
    for row in rows:
        if row.round_number != latest_round:
            break
        unsold = Decimal(str(row.units_unsold or 0))
        units += unsold
        weighted_cost += unsold * Decimal(str(row.unit_cost or 0))
    # Decimal throughout: `units_unsold` is decimal, and coercing it to int
    # silently discarded part of a real balance -- 100.50 units wrote off $750
    # instead of $753.75 (V2-049).
    return units, (weighted_cost / units if units else ZERO)


def validate(product, target_platform, team, round_number):
    """Why this switch may not happen, or None.

    Fail-closed and in a fixed order, so a refusal names the first thing wrong
    rather than the last thing checked.
    """
    if product is None:
        return 'No such product.'
    if product.team_id != getattr(team, 'id', team):
        return 'That product belongs to another team.'
    if product.status != 'active':
        return f'{product.name} is {product.status}; only an active product can be re-based.'
    if target_platform is None:
        return 'No such platform.'
    if target_platform.team_id != getattr(team, 'id', team):
        return (f'Platform "{target_platform.name}" belongs to another team. '
                f'A product can only be re-based onto your own platforms.')
    if target_platform.status != 'active':
        return (f'Platform "{target_platform.name}" is {target_platform.status}; '
                f'a product can only be re-based onto a ready platform.')

    from core.services.product_platform import platform_as_of_round
    current = platform_as_of_round(product, round_number)
    if current is not None and current.id == target_platform.id:
        return (f'{product.name} is already based on '
                f'"{target_platform.name}".')
    return None


@transaction.atomic
def rebase(product, target_platform, team, round_number):
    """Move a product onto another ready platform, and charge the write-off.

    One transaction: validation, the inventory write-off and the association
    move together or not at all.
    """
    problem = validate(product, target_platform, team, round_number)
    if problem:
        raise RebaseRefused(problem)

    from core.services.product_platform import (record_association,
                                                seed_prior_association)

    # Captured before anything moves: the platform being left behind.
    previous_id = product.team_platform_id
    # Record the association that held before this switch, so earlier rounds
    # keep resolving to the platform they were scored against.
    seed_prior_association(product, round_number)

    units, unit_cost = unsold_on_platform(product, round_number)
    pct = write_off_pct(product.team.game.scenario)
    write_off = (Decimal(units) * unit_cost * pct).quantize(Decimal('0.01'))

    row = record_association(product, target_platform, round_number)
    # Recorded on the association that caused it, so a second switch in the
    # same round updates this row rather than charging twice.
    row.inventory_written_off_units = units
    row.inventory_write_off = write_off
    row.save(update_fields=['inventory_written_off_units',
                            'inventory_write_off'])

    product.team_platform = target_platform
    product.save(update_fields=['team_platform'])

    return {
        'product': product.id,
        'from_platform': previous_id,
        'to_platform': target_platform.id,
        'effective_from_round': round_number,
        'units_written_off': str(units),
        'unit_cost': str(unit_cost),
        'write_off_pct': str(pct),
        'write_off': str(write_off),
    }


def write_offs_for_round(team, round_number):
    """The switch write-off this team owes for this round, charged once.

    Read from the history rows rather than recomputed, so the charge and the
    association that caused it cannot disagree, and a round with no switch
    costs nothing.
    """
    from core.models.team_state import TeamProductPlatformHistory

    total = (TeamProductPlatformHistory.objects
             .filter(team_product__team=team, effective_from_round=round_number)
             .order_by('team_product_id')
             .values_list('inventory_write_off', flat=True))
    return sum((Decimal(str(value or 0)) for value in total), ZERO)
