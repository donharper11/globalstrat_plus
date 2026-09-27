"""
Reasoning Dimension 3: Strategic Trajectory (deterministic, requires 2+ rounds).

Tracks decision patterns across rounds:
- Budget allocation trend stability (coefficient of variation)
- Market presence evolution (expansion rate, consistency)
- Product portfolio velocity (create/retire frequency)
- Pricing stability across rounds
- Financial leverage trend

Classifies pattern: Consistent Executor | Reactive Adjuster | Aggressive Expander
                   | Conservative Optimizer | Erratic

Score rewards consistency of execution, penalizes unjustified reversals.

Pure function — no I/O, no database access.
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RoundSnapshot:
    """Snapshot of key decision metrics for one round."""
    round_number: int
    rd_budget_pct: float = 0.0  # R&D as % of total budget
    marketing_budget_pct: float = 0.0
    strategy_budget_pct: float = 0.0
    num_active_markets: int = 0
    num_products: int = 0
    num_new_entries: int = 0
    num_exits: int = 0
    num_new_products: int = 0
    num_retired_products: int = 0
    avg_price: float = 0.0
    total_debt: float = 0.0
    total_equity: float = 0.0
    total_revenue: float = 0.0


@dataclass
class TrajectoryInput:
    round_snapshots: List[RoundSnapshot] = field(default_factory=list)


@dataclass
class TrendInfo:
    values: List[float] = field(default_factory=list)
    cv: float = 0.0  # Coefficient of variation
    direction: str = 'stable'  # increasing/decreasing/stable


@dataclass
class TrajectoryResult:
    score: float  # 0-100
    pattern: str  # consistent/reactive/aggressive/conservative/erratic
    trends: Dict[str, TrendInfo] = field(default_factory=dict)
    stability_score: float = 0.0  # 0-100
    feedback: str = ''


def _coefficient_of_variation(values: List[float]) -> float:
    """Calculate CV = std/mean. Lower = more stable."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if abs(mean) < 0.001:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance)
    return std / abs(mean)


def _trend_direction(values: List[float]) -> str:
    """Simple linear trend via sign of average change."""
    if len(values) < 2:
        return 'stable'
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    avg_change = sum(changes) / len(changes)
    if avg_change > 0.02:
        return 'increasing'
    elif avg_change < -0.02:
        return 'decreasing'
    return 'stable'


def _compute_trend(values: List[float]) -> TrendInfo:
    return TrendInfo(
        values=values,
        cv=round(_coefficient_of_variation(values), 4),
        direction=_trend_direction(values),
    )


def _classify_pattern(
    budget_cv: float,
    market_trend: str,
    market_expansion_rate: float,
    product_velocity: float,
    leverage_trend: str,
    reversal_count: int,
) -> str:
    """Classify the strategic pattern based on aggregated metrics."""
    # Erratic: high variation + frequent reversals
    if budget_cv > 0.4 and reversal_count >= 2:
        return 'erratic'

    # Aggressive Expander: consistently adding markets, high product velocity
    if market_expansion_rate > 0.3 and market_trend == 'increasing':
        return 'aggressive'

    # Conservative Optimizer: stable markets, low leverage, decreasing debt
    if (market_trend in ('stable', 'decreasing')
            and leverage_trend in ('stable', 'decreasing')
            and budget_cv < 0.2):
        return 'conservative'

    # Reactive Adjuster: moderate variation, responding to changes
    if budget_cv > 0.25 or reversal_count >= 1:
        return 'reactive'

    # Consistent Executor: low variation across all dimensions
    return 'consistent'


def _count_reversals(snapshots: List[RoundSnapshot]) -> int:
    """Count strategy reversals (direction changes in market count)."""
    if len(snapshots) < 3:
        return 0
    market_counts = [s.num_active_markets for s in snapshots]
    changes = [market_counts[i] - market_counts[i - 1] for i in range(1, len(market_counts))]
    reversals = 0
    for i in range(1, len(changes)):
        if (changes[i] > 0 and changes[i - 1] < 0) or (changes[i] < 0 and changes[i - 1] > 0):
            reversals += 1
    return reversals


def _score_from_pattern(pattern: str, stability: float) -> float:
    """
    Score rewards consistency of execution.
    Consistent and conservative get highest scores.
    Erratic gets lowest.
    """
    pattern_base = {
        'consistent': 80.0,
        'conservative': 75.0,
        'aggressive': 65.0,
        'reactive': 55.0,
        'erratic': 30.0,
    }
    base = pattern_base.get(pattern, 50.0)
    # Blend with stability (0-100)
    return base * 0.6 + stability * 0.4


def calculate_trajectory(inp: TrajectoryInput) -> TrajectoryResult:
    """
    Analyze strategic trajectory across rounds.

    Requires 2+ round snapshots. With <2 rounds, returns neutral score.
    """
    if len(inp.round_snapshots) < 2:
        return TrajectoryResult(
            score=50.0,
            pattern='consistent',
            stability_score=50.0,
            feedback='Insufficient rounds for trajectory analysis (need 2+).',
        )

    snapshots = sorted(inp.round_snapshots, key=lambda s: s.round_number)

    # Compute trends
    rd_pcts = [s.rd_budget_pct for s in snapshots]
    mktg_pcts = [s.marketing_budget_pct for s in snapshots]
    market_counts = [float(s.num_active_markets) for s in snapshots]
    product_counts = [float(s.num_products) for s in snapshots]
    prices = [s.avg_price for s in snapshots if s.avg_price > 0]
    leverage = [
        s.total_debt / max(s.total_equity, 1.0)
        for s in snapshots
    ]

    trends = {
        'rd_allocation': _compute_trend(rd_pcts),
        'marketing_allocation': _compute_trend(mktg_pcts),
        'market_presence': _compute_trend(market_counts),
        'product_portfolio': _compute_trend(product_counts),
        'pricing': _compute_trend(prices) if prices else TrendInfo(),
        'leverage': _compute_trend(leverage),
    }

    # Aggregate CV for stability
    cvs = [t.cv for t in trends.values() if t.values]
    avg_cv = sum(cvs) / max(len(cvs), 1)
    stability = max(0.0, 100.0 - avg_cv * 200)  # CV of 0.5 -> stability 0

    # Market expansion rate
    if len(market_counts) >= 2:
        first_markets = max(market_counts[0], 1)
        expansion_rate = (market_counts[-1] - market_counts[0]) / first_markets
    else:
        expansion_rate = 0.0

    # Product velocity
    total_creates = sum(s.num_new_products for s in snapshots)
    total_retires = sum(s.num_retired_products for s in snapshots)
    product_velocity = (total_creates + total_retires) / max(len(snapshots), 1)

    reversal_count = _count_reversals(snapshots)

    pattern = _classify_pattern(
        budget_cv=avg_cv,
        market_trend=trends['market_presence'].direction,
        market_expansion_rate=expansion_rate,
        product_velocity=product_velocity,
        leverage_trend=trends['leverage'].direction,
        reversal_count=reversal_count,
    )

    score = _score_from_pattern(pattern, stability)
    score = round(min(max(score, 0.0), 100.0), 2)

    pattern_labels = {
        'consistent': 'Consistent Executor — stable strategy with disciplined execution.',
        'reactive': 'Reactive Adjuster — frequent course corrections in response to events.',
        'aggressive': 'Aggressive Expander — rapid market and product expansion.',
        'conservative': 'Conservative Optimizer — focus on efficiency within existing footprint.',
        'erratic': 'Erratic — frequent direction changes without clear strategic rationale.',
    }
    feedback = pattern_labels.get(pattern, '')

    return TrajectoryResult(
        score=score,
        pattern=pattern,
        trends=trends,
        stability_score=round(stability, 2),
        feedback=feedback,
    )
