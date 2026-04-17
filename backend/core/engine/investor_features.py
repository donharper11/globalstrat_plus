"""
CC-26: Derived Financial Features for AI Investor Preference Matching.

Calculates features from financial data and team state,
mapping them to a 1-10 scale for Gaussian preference matching.
"""
import math

from core.models.results_financials import RoundResultFinancials
from core.models.team_state import TeamMarketPresence, TeamPlatform, TeamStrategyFeatureLevel
from core.models.scenario import MarketDefinition
from core.models.talent import TeamTalentState


FEATURE_CODES = [
    'revenue_growth_rate', 'rd_intensity', 'market_expansion', 'revenue_scale',
    'financial_leverage_inv', 'dividend_consistency', 'net_margin_score',
    'cash_runway_score', 'platform_generation', 'talent_rd_quality',
    'talent_commercial_quality', 'talent_operations_quality',
    'esg_composite', 'sustainability_level', 'governance_quality', 'market_diversity',
    'tech_independence', 'compliance_efficiency', 'localization_employment',
]


def calculate_investor_features(team, game, round_number):
    """
    Calculate all derived features used by AI investor preference matching.
    Returns dict: {feature_code: level_value} (all values 1-10).
    """
    features = {}
    financials = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number=round_number,
    ).first()
    prev_financials = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number=round_number - 1,
    ).first()

    if not financials:
        return {code: 3.0 for code in FEATURE_CODES}

    # === Revenue Growth Rate ===
    if prev_financials and prev_financials.total_revenue > 0:
        growth = float((financials.total_revenue - prev_financials.total_revenue) / prev_financials.total_revenue)
    else:
        growth = 0
    features['revenue_growth_rate'] = _clamp(3 + growth * 20, 1, 10)

    # === R&D Intensity ===
    if financials.total_revenue > 0:
        rd_pct = float(financials.rd_expense / financials.total_revenue)
    else:
        rd_pct = 0
    features['rd_intensity'] = _clamp(1 + rd_pct * 45, 1, 10)

    # === Market Expansion ===
    market_count = TeamMarketPresence.objects.filter(team=team, status='active').count()
    total_markets = MarketDefinition.objects.filter(scenario=game.scenario).count()
    features['market_expansion'] = _clamp(market_count / max(total_markets, 1) * 10, 1, 10)

    # === Revenue Scale ===
    rev = float(financials.total_revenue)
    features['revenue_scale'] = _clamp(1 + math.log(max(rev, 1) / 1000000 + 1) * 2.5, 1, 10)

    # === Financial Leverage (Inverted — low debt = high score) ===
    d_e = float(financials.debt_to_equity or 0)
    features['financial_leverage_inv'] = _clamp(10 - d_e * 3, 1, 10)

    # === Dividend Consistency ===
    if financials.share_price and financials.share_price > 0:
        div_yield = float(financials.dividends_paid / (financials.share_price * 1000000))
    else:
        div_yield = 0
    features['dividend_consistency'] = _clamp(1 + div_yield * 100, 1, 10)
    consecutive_divs = _count_consecutive_dividend_rounds(team, game, round_number)
    if consecutive_divs >= 3:
        features['dividend_consistency'] = min(features['dividend_consistency'] + 1.5, 10)
    elif consecutive_divs >= 2:
        features['dividend_consistency'] = min(features['dividend_consistency'] + 0.8, 10)

    # === Net Margin Score ===
    margin = float(financials.net_margin_pct or 0)
    features['net_margin_score'] = _clamp(3 + margin * 20, 1, 10)

    # === Cash Runway Score ===
    net_income = float(financials.net_income or 0)
    if net_income >= 0:
        features['cash_runway_score'] = 10.0
    else:
        burn = abs(net_income)
        cash = float(financials.cash_closing or 0)
        runway = cash / max(burn, 1)
        features['cash_runway_score'] = _clamp(runway * 1.2, 1, 10)

    # === Platform Generation ===
    highest_gen = TeamPlatform.objects.filter(
        team=team, status='active',
    ).order_by('-platform_generation__generation_order').first()
    gen_order = highest_gen.platform_generation.generation_order if highest_gen else 1
    features['platform_generation'] = {1: 4, 2: 7, 3: 10}.get(gen_order, 4)

    # === Talent Levels ===
    for pool in ['rd', 'commercial', 'operations']:
        state = TeamTalentState.objects.filter(
            team=team, talent_pool=pool, round_number=round_number,
        ).first()
        level = float(state.talent_level) if state else 3.0
        features[f'talent_{pool}_quality'] = level

    # === ESG Composite ===
    esg_level = _get_strategy_feature_level(team, 'esg_track_record', round_number)
    features['esg_composite'] = esg_level

    # === Sustainability Level ===
    sus_level = _get_strategy_feature_level(team, 'sustainability_commitment', round_number)
    features['sustainability_level'] = sus_level if sus_level > 1 else features['esg_composite']

    # === Governance Quality ===
    features['governance_quality'] = _get_strategy_feature_level(team, 'governance_quality', round_number)

    # === Market Diversity ===
    features['market_diversity'] = features['market_expansion']

    # === CC-31A B10: Technology Independence ===
    active_platforms = TeamPlatform.objects.filter(team=team, status='active')
    if active_platforms.exists():
        avg_dependency = sum(
            float(p.licensed_dependency_pct) for p in active_platforms
        ) / active_platforms.count()
        tech_independence = 1.0 - avg_dependency
    else:
        tech_independence = 1.0
    features['tech_independence'] = _clamp(tech_independence * 10, 1, 10)

    # === CC-31A: Compliance Efficiency ===
    from core.models.cc31_models import TeamMarketCompliance
    compliance_records = TeamMarketCompliance.objects.filter(
        game=game, team=team,
    )
    if compliance_records.exists():
        avg_compliance = sum(
            float(c.compliance_level) for c in compliance_records
        ) / compliance_records.count()
    else:
        avg_compliance = 0.0
    features['compliance_efficiency'] = _clamp(avg_compliance * 10, 1, 10)

    # === CC-31A: Localization Employment ===
    from core.models.cc31_models import TalentAllocation
    from core.models.talent import TeamTalentState as _TTS
    total_headcount = 0
    total_market_staff = 0
    for pool in ['rd', 'commercial', 'operations']:
        ts = _TTS.objects.filter(team=team, talent_pool=pool, round_number=round_number).first()
        if ts:
            total_headcount += ts.headcount
    # Get latest allocation
    from core.models.decisions import DecisionSubmission
    sub = DecisionSubmission.objects.filter(
        team=team, round__round_number=round_number, round__game=game,
    ).first()
    if sub:
        for alloc in TalentAllocation.objects.filter(submission=sub):
            total_market_staff += sum(alloc.market_allocation.values())
    if total_headcount > 0:
        localization_ratio = total_market_staff / total_headcount
    else:
        localization_ratio = 0.0
    features['localization_employment'] = _clamp(localization_ratio * 10, 1, 10)

    return features


def _clamp(value, min_val, max_val):
    return max(min_val, min(max_val, round(value, 2)))


def _count_consecutive_dividend_rounds(team, game, current_round):
    """Count how many consecutive rounds the team has paid dividends."""
    count = 0
    for r in range(current_round, -1, -1):
        f = RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=r,
        ).first()
        if f and f.dividends_paid and f.dividends_paid > 0:
            count += 1
        else:
            break
    return count


def _get_strategy_feature_level(team, feature_code, round_number):
    """Get team's strategy feature level, defaulting to 1.0."""
    tsfl = TeamStrategyFeatureLevel.objects.filter(
        team=team, feature__code=feature_code,
        round_number=round_number, market__isnull=True,
    ).first()
    return float(tsfl.current_level) if tsfl else 1.0
