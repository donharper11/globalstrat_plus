"""
Trigger condition evaluator for team-specific events.

Evaluates JSON condition definitions against a team's current simulation state.
Conditions are dicts of the form {"attribute": "team.X.Y", "operator": ">", "value": 0.40}
and are combined with AND logic when multiple conditions are provided.
"""

from decimal import Decimal

from django.db.models import Avg


# ---------------------------------------------------------------------------
# Attribute resolution
# ---------------------------------------------------------------------------

def resolve_team_attribute(attribute_path, team, game, market):
    """Resolve a dotted attribute path (e.g. ``team.compliance_level.US``)
    to the current value for *team* within *game* / *market*.

    Lazy-imports Django models inside the function body to avoid circular
    import issues at module load time.

    Returns ``None`` when the attribute is unrecognised or the underlying
    database row does not exist.
    """

    parts = attribute_path.split(".")

    # All supported paths start with "team"
    if not parts or parts[0] != "team":
        return None

    key = parts[1] if len(parts) > 1 else None
    market_code = parts[2] if len(parts) > 2 else (market.code if market else None)

    # -- team.licensed_dependency_pct ----------------------------------------
    if key == "licensed_dependency_pct":
        from core.models.team_state import TeamPlatform

        result = (
            TeamPlatform.objects
            .filter(team=team, status="active")
            .aggregate(avg=Avg("licensed_dependency_pct"))
        )
        return Decimal(str(result["avg"])) if result["avg"] is not None else None

    # -- team.compliance_level.<market_code> ----------------------------------
    if key == "compliance_level":
        from core.models.cc31_models import TeamMarketCompliance

        try:
            obj = TeamMarketCompliance.objects.get(
                game=game, team=team, market__code=market_code,
            )
            return Decimal(str(obj.compliance_level)) if obj.compliance_level is not None else None
        except TeamMarketCompliance.DoesNotExist:
            return None

    # -- team.origin_trust.<market_code> --------------------------------------
    if key == "origin_trust":
        from core.models.cc31_models import TeamMarketCompliance

        try:
            obj = TeamMarketCompliance.objects.get(
                game=game, team=team, market__code=market_code,
            )
            return Decimal(str(obj.current_trust_multiplier)) if obj.current_trust_multiplier is not None else None
        except TeamMarketCompliance.DoesNotExist:
            return None

    # -- team.entry_mode.<market_code> ----------------------------------------
    if key == "entry_mode":
        from core.models.team_state import TeamMarketPresence

        try:
            obj = TeamMarketPresence.objects.get(
                team=team, market__code=market_code,
            )
            return obj.entry_mode.code if obj.entry_mode else None
        except TeamMarketPresence.DoesNotExist:
            return None

    # -- team.rounds_in_market.<market_code> ----------------------------------
    if key == "rounds_in_market":
        from core.models.cc31_models import TeamMarketCompliance

        try:
            obj = TeamMarketCompliance.objects.get(
                game=game, team=team, market__code=market_code,
            )
            return Decimal(str(obj.rounds_present)) if obj.rounds_present is not None else None
        except TeamMarketCompliance.DoesNotExist:
            return None

    # -- team.debt_to_equity (NOT IMPLEMENTED) --------------------------------
    if key == "debt_to_equity":
        return None

    return None


# ---------------------------------------------------------------------------
# Single-condition evaluation
# ---------------------------------------------------------------------------

_OPERATORS = {
    ">":  lambda a, b: a > b,
    "<":  lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def evaluate_trigger_condition(condition, team, game, market):
    """Evaluate a single condition dict against the team's current state.

    *condition* must contain ``attribute``, ``operator``, and ``value`` keys.
    Returns ``True`` if the condition is satisfied, ``False`` otherwise
    (including when the attribute cannot be resolved).
    """

    attribute_path = condition.get("attribute")
    operator = condition.get("operator")
    target_value = condition.get("value")

    if not attribute_path or operator not in _OPERATORS:
        return False

    actual_value = resolve_team_attribute(attribute_path, team, game, market)
    if actual_value is None:
        return False

    # entry_mode is compared as a string; everything else as Decimal.
    if "entry_mode" in attribute_path:
        return _OPERATORS[operator](str(actual_value), str(target_value))

    try:
        return _OPERATORS[operator](Decimal(str(actual_value)), Decimal(str(target_value)))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Multi-condition evaluation (AND logic)
# ---------------------------------------------------------------------------

def evaluate_all_conditions(conditions, team, game, market):
    """Evaluate a list of conditions with AND logic.

    * ``None`` or empty list  -> ``True`` (no conditions means always triggered).
    * A single dict           -> evaluated as one condition.
    * A list of dicts         -> all must pass.
    """

    if conditions is None:
        return True

    if isinstance(conditions, dict):
        conditions = [conditions]

    if not conditions:
        return True

    return all(
        evaluate_trigger_condition(c, team, game, market)
        for c in conditions
    )
