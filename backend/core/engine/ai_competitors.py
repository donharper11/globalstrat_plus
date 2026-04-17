"""
Engine: Dynamic AI Competitor Fit Score Calculation (CC-20).

Replaces static AICompetitorFitByRound with rule-based adjustments
that make AI competitors reactive to market conditions.
"""
from core.models.scenario import (
    AICompetitorFitByRound, AICompetitorBehavior,
)


def calculate_ai_competitor_fit(ai_competitor, segment, market, round_number, context):
    """
    Calculate AI competitor's fit score dynamically based on:
    1. Base fit from static table (starting point)
    2. Innovation gain over time for primary segments
    3. Competitive response to human team dominance
    4. Defensive reaction to declining position
    5. Market growth attraction for aggressive competitors
    """
    behavior = AICompetitorBehavior.objects.filter(
        ai_competitor=ai_competitor,
    ).first()

    # Start with static base fit
    base = AICompetitorFitByRound.objects.filter(
        ai_competitor=ai_competitor,
        segment=segment,
        round_number=round_number,
    ).first()
    base_fit = float(base.fit_score) if base else 0.4

    if not behavior:
        return base_fit  # No behavior model — use static

    adjustments = 0.0

    # 1. Innovation: AI improves over time for primary segments
    seg_code = getattr(segment, 'code', '') or segment.name.lower().replace(' ', '_')
    if any(ps in seg_code for ps in behavior.primary_segments):
        innovation_gain = float(behavior.innovation_rate) * 0.03 * round_number
        adjustments += innovation_gain

    # 2. Aggressive response: If human teams dominate a segment
    if behavior.strategy_type == 'aggressive':
        human_leader_share = _get_max_human_share(segment, market, round_number - 1, context)
        if human_leader_share > 0.30:
            adjustments += 0.05

    # 3. Defensive: Fight back against declining position
    if behavior.strategy_type == 'defensive':
        prev_base = AICompetitorFitByRound.objects.filter(
            ai_competitor=ai_competitor,
            segment=segment,
            round_number=max(round_number - 1, 0),
        ).first()
        if prev_base and base_fit < float(prev_base.fit_score):
            adjustments += 0.03

    # 4. Aggressive: Attracted to high-growth markets
    if behavior.strategy_type == 'aggressive':
        market_growth = float(getattr(market, 'growth_rate_base', 0) or 0)
        if market_growth > 0.05:
            adjustments += 0.02

    # 5. Price response: Price-sensitive AI responds to low human pricing
    if float(behavior.price_sensitivity) > 0.5:
        avg_price = _get_avg_human_price(market, round_number, context)
        if avg_price and avg_price < 300:
            adjustments += 0.03 * float(behavior.price_sensitivity)

    # Cap total fit
    final_fit = min(max(base_fit + adjustments, 0.05), 0.95)
    return final_fit


def _get_max_human_share(segment, market, round_number, context):
    """Get the maximum market share any human team has in this segment."""
    if round_number < 1:
        return 0.0

    from core.models.results import RoundResultAdoption
    adoptions = RoundResultAdoption.objects.filter(
        game=context.game,
        segment=segment,
        market=market,
        round_number=round_number,
    )
    max_share = 0.0
    for a in adoptions:
        share = float(a.team_share_pct) if a.team_share_pct else 0.0
        if share > max_share:
            max_share = share
    return max_share


def _get_avg_human_price(market, round_number, context):
    """Get average retail price of human teams in this market."""
    from core.models.results_financials import RoundResultProductMarket
    results = RoundResultProductMarket.objects.filter(
        game=context.game,
        market=market,
        round_number=max(round_number - 1, 0),
    )
    prices = [float(r.retail_price) for r in results if r.retail_price]
    if not prices:
        return None
    return sum(prices) / len(prices)
