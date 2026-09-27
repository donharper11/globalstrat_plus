"""
Reasoning Dimension 1: Extended Coherence Analysis (deterministic).

Five cross-domain consistency sub-dimensions:
  1. Positioning-Investment: R&D/platform spend matches positioning tier
  2. Market Entry-Support: New entries backed by marketing + production
  3. Financial Strategy: Financing supports strategic direction
  4. ESG-Strategy: ESG investments align with governance commitments
  5. Supply Chain-Market: Sourcing/plant decisions reflect market presence

Pure function — no I/O, no database access.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProductInfo:
    name: str
    positioning: str  # budget/mainstream/premium/ultra_premium
    platform_name: str = ''


@dataclass
class MarketPresenceInfo:
    market_name: str
    market_code: str
    entry_mode: str = ''
    status: str = 'active'


@dataclass
class BudgetInfo:
    rd_budget: float = 0.0
    marketing_budget: float = 0.0
    strategy_budget: float = 0.0


@dataclass
class MarketingInfo:
    product_name: str
    market_name: str
    promotion_budget: float = 0.0
    production_volume: int = 0


@dataclass
class MarketEntryInfo:
    market_name: str
    action: str  # enter/exit
    initial_investment: float = 0.0


@dataclass
class FinancingInfo:
    new_debt: float = 0.0
    debt_repayment: float = 0.0
    dividend_per_share: float = 0.0
    equity_issued: float = 0.0


@dataclass
class PlantInfo:
    market_name: str
    capacity: int = 0
    status: str = 'active'


@dataclass
class ESGInfo:
    environmental_spend: float = 0.0
    social_spend: float = 0.0
    governance_spend: float = 0.0


@dataclass
class GovernanceCommitment:
    commitment_type: str
    is_active: bool = True


@dataclass
class PlatformDevInfo:
    platform_name: str
    investment: float = 0.0


@dataclass
class CoherenceExtInput:
    products: List[ProductInfo] = field(default_factory=list)
    market_presences: List[MarketPresenceInfo] = field(default_factory=list)
    budget: Optional[BudgetInfo] = None
    marketing_decisions: List[MarketingInfo] = field(default_factory=list)
    market_entries: List[MarketEntryInfo] = field(default_factory=list)
    financing: Optional[FinancingInfo] = None
    plants: List[PlantInfo] = field(default_factory=list)
    esg: Optional[ESGInfo] = None
    governance_commitments: List[GovernanceCommitment] = field(default_factory=list)
    platform_devs: List[PlatformDevInfo] = field(default_factory=list)
    total_revenue: float = 0.0
    total_debt: float = 0.0
    total_equity: float = 0.0


@dataclass
class CoherenceExtResult:
    score: float  # 0-100
    sub_scores: Dict[str, float] = field(default_factory=dict)
    signals: List[str] = field(default_factory=list)
    feedback: Dict[str, str] = field(default_factory=dict)


# ── Tier thresholds ──

POSITIONING_RD_THRESHOLDS = {
    'ultra_premium': 0.08,
    'premium': 0.05,
    'mainstream': 0.02,
    'budget': 0.0,
}


def _score_positioning_investment(inp: CoherenceExtInput) -> tuple:
    """Sub-dim 1: R&D/platform spend matches product positioning tier."""
    if not inp.products:
        return 50.0, [], 'No products to evaluate.'

    scores = []
    signals = []
    total_rd = (inp.budget.rd_budget if inp.budget else 0.0)
    total_rd += sum(pd.investment for pd in inp.platform_devs)
    revenue = max(inp.total_revenue, 1.0)
    rd_ratio = total_rd / revenue

    premium_count = sum(
        1 for p in inp.products
        if p.positioning in ('premium', 'ultra_premium')
    )
    budget_count = sum(
        1 for p in inp.products if p.positioning == 'budget'
    )

    if premium_count > 0:
        threshold = POSITIONING_RD_THRESHOLDS.get('premium', 0.05)
        if rd_ratio >= threshold:
            scores.append(100.0)
        elif rd_ratio >= threshold * 0.5:
            scores.append(50.0)
            signals.append(
                f'R&D spend ({rd_ratio:.1%} of revenue) is below premium threshold ({threshold:.1%})'
            )
        else:
            scores.append(20.0)
            signals.append(
                f'Premium products lack R&D investment ({rd_ratio:.1%} vs {threshold:.1%} needed)'
            )
    if budget_count > 0 and rd_ratio > 0.10:
        scores.append(60.0)
        signals.append(
            'High R&D spend may be misaligned with budget positioning'
        )
    elif budget_count > 0:
        scores.append(90.0)

    if not scores:
        scores.append(70.0)

    avg = sum(scores) / len(scores)
    feedback = 'R&D investment aligns with positioning.' if avg >= 70 else (
        'R&D investment may not match product positioning tier.'
    )
    return avg, signals, feedback


def _score_market_entry_support(inp: CoherenceExtInput) -> tuple:
    """Sub-dim 2: New market entries backed by marketing + production."""
    new_entries = [e for e in inp.market_entries if e.action == 'enter']
    if not new_entries:
        return 70.0, [], 'No new market entries this round.'

    scores = []
    signals = []
    marketing_markets = {m.market_name for m in inp.marketing_decisions}
    plant_markets = {p.market_name for p in inp.plants if p.status == 'active'}

    for entry in new_entries:
        has_marketing = entry.market_name in marketing_markets
        has_production = entry.market_name in plant_markets

        mktg_for_market = [
            m for m in inp.marketing_decisions
            if m.market_name == entry.market_name
        ]
        has_budget = any(m.promotion_budget > 0 for m in mktg_for_market)

        if has_marketing and has_budget:
            scores.append(100.0)
        elif has_marketing:
            scores.append(70.0)
            signals.append(
                f'{entry.market_name}: market entry has marketing decisions but no promotion budget'
            )
        else:
            scores.append(30.0)
            signals.append(
                f'{entry.market_name}: market entry without marketing support'
            )

    avg = sum(scores) / len(scores) if scores else 50.0
    feedback = 'Market entries well-supported.' if avg >= 70 else (
        'Some market entries lack adequate marketing or production support.'
    )
    return avg, signals, feedback


def _score_financial_strategy(inp: CoherenceExtInput) -> tuple:
    """Sub-dim 3: Financing decisions support strategic direction."""
    signals = []
    score_components = []

    new_entries = [e for e in inp.market_entries if e.action == 'enter']
    is_expanding = len(new_entries) > 0
    financing = inp.financing

    if not financing:
        return 60.0, [], 'No financing decisions to evaluate.'

    # Dividends during aggressive expansion
    if is_expanding and financing.dividend_per_share > 0:
        score_components.append(30.0)
        signals.append(
            'Paying dividends during market expansion may strain capital'
        )
    elif not is_expanding and financing.dividend_per_share > 0:
        score_components.append(90.0)

    # Debt levels
    d2e = (inp.total_debt / max(inp.total_equity, 1.0))
    if is_expanding and financing.new_debt > 0 and d2e < 2.0:
        score_components.append(85.0)  # Sensible leverage for growth
    elif financing.new_debt > 0 and d2e >= 2.0:
        score_components.append(40.0)
        signals.append(
            f'Taking on more debt at high leverage (D/E={d2e:.1f})'
        )
    elif not is_expanding and financing.debt_repayment > 0:
        score_components.append(90.0)  # Paying down debt in stable phase

    if not score_components:
        score_components.append(70.0)

    avg = sum(score_components) / len(score_components)
    feedback = 'Financial strategy supports operational direction.' if avg >= 60 else (
        'Financial decisions may conflict with strategic priorities.'
    )
    return avg, signals, feedback


def _score_esg_strategy(inp: CoherenceExtInput) -> tuple:
    """Sub-dim 4: ESG investments align with governance commitments."""
    if not inp.governance_commitments:
        return 70.0, [], 'No governance commitments to evaluate.'

    esg = inp.esg or ESGInfo()
    total_esg = esg.environmental_spend + esg.social_spend + esg.governance_spend
    active_commitments = [g for g in inp.governance_commitments if g.is_active]

    if not active_commitments:
        return 70.0, [], 'No active governance commitments.'

    signals = []

    # Check if ESG spend exists when commitments are active
    if total_esg <= 0 and active_commitments:
        signals.append(
            'Active governance commitments but no ESG spending'
        )
        return 25.0, signals, 'ESG spending does not support governance commitments.'

    # Check specific alignment
    env_types = {'sustainability', 'environmental', 'carbon_neutral'}
    social_types = {'diversity', 'labor_rights', 'community'}

    has_env_commitment = any(
        g.commitment_type in env_types for g in active_commitments
    )
    has_social_commitment = any(
        g.commitment_type in social_types for g in active_commitments
    )

    score = 80.0
    if has_env_commitment and esg.environmental_spend <= 0:
        score -= 25.0
        signals.append('Environmental commitment without environmental spending')
    if has_social_commitment and esg.social_spend <= 0:
        score -= 25.0
        signals.append('Social commitment without social spending')

    feedback = 'ESG investments align with commitments.' if score >= 60 else (
        'ESG spending does not adequately support governance commitments.'
    )
    return max(score, 0.0), signals, feedback


def _score_supply_chain_market(inp: CoherenceExtInput) -> tuple:
    """Sub-dim 5: Sourcing/plant decisions reflect market presence."""
    active_markets = {
        mp.market_name for mp in inp.market_presences if mp.status == 'active'
    }
    if not active_markets:
        return 50.0, [], 'No active market presence.'

    plant_markets = {p.market_name for p in inp.plants if p.status == 'active'}
    signals = []

    # Check plant coverage of active markets
    covered = active_markets & plant_markets
    coverage_ratio = len(covered) / max(len(active_markets), 1)

    if coverage_ratio >= 0.5:
        score = 80.0 + coverage_ratio * 20.0
    elif coverage_ratio > 0:
        score = 50.0 + coverage_ratio * 30.0
    else:
        score = 40.0
        if len(active_markets) > 1:
            signals.append(
                'No local production capacity in any active market'
            )

    # Penalty for plants in markets without presence
    orphan_plants = plant_markets - active_markets
    if orphan_plants:
        score -= 10.0 * len(orphan_plants)
        signals.append(
            f'Plant capacity in markets without active presence: {", ".join(orphan_plants)}'
        )

    score = max(min(score, 100.0), 0.0)
    feedback = 'Supply chain aligns with market presence.' if score >= 60 else (
        'Production capacity may not match market footprint.'
    )
    return score, signals, feedback


def calculate_coherence_ext(inp: CoherenceExtInput) -> CoherenceExtResult:
    """
    Calculate extended coherence score across 5 sub-dimensions.

    Returns CoherenceExtResult with score (0-100), sub_scores, signals, and feedback.
    """
    sub_results = {
        'positioning_investment': _score_positioning_investment(inp),
        'market_entry_support': _score_market_entry_support(inp),
        'financial_strategy': _score_financial_strategy(inp),
        'esg_strategy': _score_esg_strategy(inp),
        'supply_chain_market': _score_supply_chain_market(inp),
    }

    sub_scores = {}
    all_signals = []
    all_feedback = {}

    for key, (score, signals, feedback) in sub_results.items():
        sub_scores[key] = round(score, 2)
        all_signals.extend(signals)
        all_feedback[key] = feedback

    # Equal weight across 5 sub-dimensions
    overall = sum(sub_scores.values()) / max(len(sub_scores), 1)

    return CoherenceExtResult(
        score=round(overall, 2),
        sub_scores=sub_scores,
        signals=all_signals,
        feedback=all_feedback,
    )
