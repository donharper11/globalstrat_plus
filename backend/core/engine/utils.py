"""
Shared utilities for the engine pipeline.
"""
import logging
import math
from decimal import Decimal

from core.models.scenario import ScenarioConfig

_logger = logging.getLogger(__name__)


_config_cache = {}  # scenario_id -> {key: value}

REFERENCE_PRICE_CONFIG_KEY = 'reference_price'


class InvalidScenarioConfiguration(ValueError):
    """A scenario value scoring depends on is missing or unusable.

    Raised rather than defaulted. A silent fallback would change what the
    competition rewards without anyone deciding to, which is the failure mode
    V2-021 was, and the failure mode V2-023 punished: price competitiveness
    fell back to the team's own price and stopped measuring anything.

    Defined here rather than beside either scorer because both the performance
    index and the preference engine need it, and utils is the module they
    already share.
    """


HIGH_PRICE_ELASTICITY_CONFIG_KEY = 'high_price_elasticity'


def scenario_high_price_elasticity(scenario):
    """Demand elasticity applied to prices above the reference.

    Must be strictly greater than 1. The bounded preference feature reaches its
    floor at 1.5x the reference and clamps there, so above that point price no
    longer reduces demand through fit at all while revenue keeps multiplying by
    price. An exponent of exactly 1 would leave revenue flat above the
    reference rather than falling; anything below 1 leaves it growing. Strictly
    greater than 1 is what makes the high-price tail bounded.
    """
    raw = get_config(scenario, HIGH_PRICE_ELASTICITY_CONFIG_KEY, default=None)
    if raw is None:
        raise InvalidScenarioConfiguration(
            f'scenario {getattr(scenario, "id", scenario)} has no '
            f'{HIGH_PRICE_ELASTICITY_CONFIG_KEY!r} configured; demand above '
            f'the reference price would be unbounded in revenue without it')
    elasticity = float(raw)
    if not math.isfinite(elasticity):
        raise InvalidScenarioConfiguration(
            f'scenario {getattr(scenario, "id", scenario)} sets '
            f'{HIGH_PRICE_ELASTICITY_CONFIG_KEY}={raw!r}, which is not a '
            f'finite number')
    if elasticity <= 1:
        raise InvalidScenarioConfiguration(
            f'scenario {getattr(scenario, "id", scenario)} sets '
            f'{HIGH_PRICE_ELASTICITY_CONFIG_KEY}={elasticity}; it must be '
            f'strictly greater than 1, or revenue does not fall as price rises '
            f'above the reference')
    return elasticity


def high_price_demand_multiplier(retail_price, reference_price, elasticity):
    """`(price / reference) ** -elasticity` above the reference, else 1.0.

    Absolute, not a share adjustment. A penalty applied to competitive share
    would cancel out when every team raised price together, leaving collective
    inflation free; this reduces the team's own adopters whatever anyone else
    does. Continuous at the reference, where the multiplier is exactly 1.0.
    """
    price = float(retail_price)
    if price <= reference_price:
        return 1.0
    return (price / reference_price) ** (-elasticity)


def scenario_reference_price(scenario):
    """The scenario-authored price all retail prices are scored against.

    Deliberately independent of any team decision and of roster composition:
    the V2-023 exploit existed because the comparison price was derived from
    the very decision being scored, so a team alone in its positioning was
    always exactly average and price stopped affecting demand.

    Refuses rather than falling back. A fallback to a team or cohort price is
    the defect, not a recovery from it.
    """
    raw = get_config(scenario, REFERENCE_PRICE_CONFIG_KEY, default=None)
    if raw is None:
        raise InvalidScenarioConfiguration(
            f'scenario {getattr(scenario, "id", scenario)} has no '
            f'{REFERENCE_PRICE_CONFIG_KEY!r} configured; retail price cannot '
            f'be scored without a reference independent of team decisions')
    price = float(raw)
    if price <= 0:
        raise InvalidScenarioConfiguration(
            f'scenario {getattr(scenario, "id", scenario)} sets '
            f'{REFERENCE_PRICE_CONFIG_KEY}={price}; it must be greater than '
            f'zero, because it is the denominator of the price ratio')
    return price


def get_config(scenario, key, default=None, cast_type=float):
    """Load a scenario configuration value, with in-memory cache."""
    scenario_id = scenario.id if hasattr(scenario, 'id') else scenario

    if scenario_id not in _config_cache:
        _config_cache[scenario_id] = dict(
            ScenarioConfig.objects.filter(scenario_id=scenario_id)
            .values_list('config_key', 'config_value')
        )

    raw = _config_cache[scenario_id].get(key)
    if raw is None:
        return default

    if cast_type is bool:
        return raw.lower() in ('true', '1', 'yes')
    return cast_type(raw)


def invalidate_config_cache(scenario_id=None):
    """Clear config cache. Call after scenario config changes."""
    if scenario_id:
        _config_cache.pop(scenario_id, None)
    else:
        _config_cache.clear()


def clamp(value, min_val, max_val):
    """Clamp a value between min and max."""
    return max(min_val, min(value, max_val))


def gaussian_fit(actual, ideal, tolerance):
    """
    Calculate feature fit using Gaussian decay.
    Returns 1.0 when actual == ideal, decays toward 0.0.
    tolerance controls the width of the bell curve.
    """
    if tolerance <= 0:
        return 1.0 if actual == ideal else 0.0
    distance = float(actual - ideal)
    return math.exp(-(distance ** 2) / (2 * float(tolerance) ** 2))


def calculate_level_gain(investment_amount, current_level, curve_type, cost_base,
                         scenario=None):
    """
    Calculate the level gain from an R&D investment.
    Implements all 4 cost curve types from 03-engine-logic.md Section 3.
    """
    investment_amount = float(investment_amount)
    current_level = float(current_level)
    cost_base = float(cost_base)

    if cost_base <= 0 or investment_amount <= 0:
        return 0.0

    if curve_type == 'linear':
        gain = investment_amount / cost_base

    elif curve_type == 'diminishing':
        diminishing_factor = 0.15
        if scenario:
            diminishing_factor = get_config(scenario, 'r_and_d_diminishing_factor',
                                            default=0.15)
        effective_cost = cost_base * (1 + current_level * diminishing_factor)
        gain = investment_amount / effective_cost

    elif curve_type == 'exponential':
        doubling_interval = 3.0
        effective_cost = cost_base * (2 ** (current_level / doubling_interval))
        gain = investment_amount / effective_cost

    elif curve_type == 'step':
        cost_per_step = cost_base * (1 + current_level * 0.1)
        gain = math.floor(investment_amount / cost_per_step)

    else:
        gain = investment_amount / cost_base

    return max(gain, 0.0)


class MarketEffectiveState:
    """Effective market values for this round after events and conditions."""

    def __init__(self, market_def):
        self.market_def = market_def
        self.effective_growth_rate = float(market_def.base_growth_rate)
        self.effective_exchange_rate = float(market_def.exchange_rate_base)
        self.effective_tariff_rate = float(market_def.tariff_rate)
        self.demand_multiplier = 1.0


class SegmentEffectiveState:
    """Effective segment values for this round."""

    def __init__(self, segment_def):
        self.segment_def = segment_def
        self.effective_population = float(segment_def.population_size)
        self.preference_modifiers = {}  # feature_id → modifier_value


class RoundContext:
    """Carries computed state through the engine pipeline. Not persisted."""

    def __init__(self, game, round_number):
        self.game = game
        self.round_number = round_number
        self.scenario = game.scenario
        self.teams = list(game.teams.filter(
            participation_status='active',
        ).order_by('id'))
        self.markets = {}          # market_id → MarketEffectiveState
        self.segments = {}         # segment_id → SegmentEffectiveState
        self.fit_scores = {}       # (team_id, segment_id, market_id) → float
        self.adjusted_fit_scores = {}  # after campaign multiplier
        self.best_products = {}    # (team_id, segment_id, market_id) → TeamProduct
        self.adoption = {}         # (team_id, segment_id, market_id) → new_adopters
        self.readiness = {}        # (team_id, product_id, market_id) → readiness_pct
        self.events_fired = []     # list of EventInstance
        self.production_remaining = {}  # (team_id, product_id, market_id) → units remaining
        self.org_modifiers = {}    # team_id → dict of org structure modifiers
        self.log = []              # human-readable log entries


# ── Team notifications ────────────────────────────────────────────────────
# SimulationInstance is an unmanaged model, so its table exists only in
# databases provisioned outside Django (production does; a test database
# Django created does not). Probe once per process instead of raising -- and
# logging a traceback -- on every notification.
_SIMULATION_INSTANCE_AVAILABLE = None


def resolve_instance_id(game_id):
    """Return the SimulationInstance id for a game, or None if unavailable."""
    global _SIMULATION_INSTANCE_AVAILABLE
    if _SIMULATION_INSTANCE_AVAILABLE is False:
        return None
    try:
        from core.models.course import SimulationInstance
        instance = SimulationInstance.objects.filter(game_id=game_id).first()
        _SIMULATION_INSTANCE_AVAILABLE = True
        return instance.instance_id if instance else None
    except Exception:
        if _SIMULATION_INSTANCE_AVAILABLE is None:
            _logger.info(
                'simulation_instance table unavailable; team notifications will '
                'be recorded without an instance id'
            )
        _SIMULATION_INSTANCE_AVAILABLE = False
        return None


def notify_team(game_id, team, round_number, message):
    """Best-effort team notification. Never let this abort round processing."""
    try:
        from core.models.messaging import TeamNotification
        TeamNotification.objects.create(
            team_id=team.id,
            round_id=round_number,
            instance_id=resolve_instance_id(game_id),
            notification_text=message,
            is_read=False,
        )
    except Exception:
        _logger.warning(
            'Could not create TeamNotification for %s', getattr(team, 'name', team),
            exc_info=True,
        )
