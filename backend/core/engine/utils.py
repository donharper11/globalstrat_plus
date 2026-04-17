"""
Shared utilities for the engine pipeline.
"""
import math
from decimal import Decimal

from core.models.scenario import ScenarioConfig


_config_cache = {}  # scenario_id -> {key: value}

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
        self.teams = list(game.teams.all())
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
