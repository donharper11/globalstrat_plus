"""CC-26: Investor Relations API endpoint."""
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team
from core.models.cc26_models import (
    AIInvestorFund, AIInvestorHolding, SharePriceHistory,
)
from core.models.results_financials import RoundResultFinancials
from core.utils.localization import get_localized_field, get_user_language


# ── Quick-win suggestions keyed by feature_code ──
QUICK_WIN_MAP = {
    'dividend_consistency': {'action': 'Set a dividend policy', 'page': 'finance'},
    'governance_quality': {'action': 'Add governance commitments', 'page': 'corporate-strategy'},
    'financial_leverage_inv': {'action': 'Repay debt or issue equity', 'page': 'finance'},
    'sustainability_level': {'action': 'Increase ESG investment', 'page': 'corporate-strategy'},
    'esg_composite': {'action': 'Increase ESG investment', 'page': 'corporate-strategy'},
    'rd_intensity': {'action': 'Increase R&D budget', 'page': 'rd-investment'},
    'revenue_growth_rate': {'action': 'Expand marketing or enter new markets', 'page': 'marketing-mix'},
    'market_expansion': {'action': 'Enter a new market', 'page': 'market-strategy'},
    'market_diversity': {'action': 'Enter a new market', 'page': 'market-strategy'},
    'platform_generation': {'action': 'Upgrade platform features', 'page': 'rd-investment'},
    'net_margin_score': {'action': 'Reduce costs or increase prices', 'page': 'marketing-mix'},
    'talent_operations_quality': {'action': 'Invest in operations talent', 'page': 'corporate-strategy'},
    'talent_rd_quality': {'action': 'Invest in R&D talent', 'page': 'corporate-strategy'},
    'talent_commercial_quality': {'action': 'Invest in commercial talent', 'page': 'corporate-strategy'},
    'tech_independence': {'action': 'Develop features in-house', 'page': 'rd-investment'},
    'cash_runway_score': {'action': 'Improve cash management', 'page': 'finance'},
    'revenue_scale': {'action': 'Grow revenue through marketing', 'page': 'marketing-mix'},
}


def _calculate_fund_alignment(fund, features):
    """
    Calculate how well a team's current feature state matches a fund's preferences.
    Uses the same features already computed for investor preference matching.
    Returns alignment dict with 0.0-1.0 score, per-feature breakdown, gap, and quick win.
    """
    prefs = list(fund.preferences.all())
    if not prefs:
        return {'score': 0.0, 'feature_scores': {}, 'biggest_gap': None, 'quick_win': None}

    feature_scores = {}
    for p in prefs:
        actual = features.get(p.feature_code, 3.0)
        ideal = float(p.ideal_value)
        tolerance = float(p.tolerance)
        # Score 0-1: how close actual is to ideal within tolerance band
        distance = abs(actual - ideal)
        score = max(0.0, 1.0 - distance / (tolerance * 2))
        feature_scores[p.feature_code] = round(score, 2)

    # Weighted average alignment
    total_weight = sum(float(p.weight) for p in prefs)
    weighted_sum = sum(
        feature_scores.get(p.feature_code, 0) * float(p.weight) for p in prefs
    )
    alignment_score = weighted_sum / total_weight if total_weight > 0 else 0

    # Find biggest gap (lowest score * weight product)
    gaps = []
    for p in prefs:
        score = feature_scores.get(p.feature_code, 0)
        gaps.append({
            'feature': p.feature_code,
            'label': p.feature_label,
            'score': score,
            'weight': round(float(p.weight), 2),
        })
    gaps.sort(key=lambda g: g['score'] * g['weight'])
    biggest_gap = gaps[0] if gaps else None

    # Generate quick win
    quick_win = None
    if biggest_gap:
        suggestion = QUICK_WIN_MAP.get(
            biggest_gap['feature'],
            {'action': 'Review strategy', 'page': 'dashboard'},
        )
        potential_improvement = biggest_gap['weight'] * (0.7 - biggest_gap['score'])
        quick_win = {
            'action': suggestion['action'],
            'page': suggestion['page'],
            'impact': f"+{max(1, int(potential_improvement * 100))}% alignment",
        }

    return {
        'score': round(alignment_score, 2),
        'feature_scores': feature_scores,
        'biggest_gap': biggest_gap,
        'quick_win': quick_win,
    }


class InvestorRelationsView(APIView):
    """GET — Investor relations data for financial reports."""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, pk=game_id)
        team = get_object_or_404(Team, pk=team_id)
        latest_round = max(game.current_round - 1, 0)

        requested_round = request.query_params.get('round')
        if requested_round is not None:
            latest_round = max(min(int(requested_round), game.current_round - 1), 0)

        # Share price data
        price_history = SharePriceHistory.objects.filter(
            game=game, team=team,
        ).order_by('round_number')

        current_price = price_history.filter(round_number=latest_round).first()
        prev_price = price_history.filter(round_number=latest_round - 1).first() if latest_round > 0 else None

        price_change = 0
        price_change_pct = 0
        if current_price and prev_price and prev_price.share_price > 0:
            price_change = float(current_price.share_price - prev_price.share_price)
            price_change_pct = price_change / float(prev_price.share_price)

        # Fund holdings
        holdings = AIInvestorHolding.objects.filter(
            game=game, team=team, round_number=latest_round,
        ).select_related('fund')

        prev_holdings = {
            h.fund_id: h for h in AIInvestorHolding.objects.filter(
                game=game, team=team, round_number=latest_round - 1,
            )
        } if latest_round > 0 else {}

        shareholders = []
        total_fund_pct = 0
        for h in holdings:
            prev = prev_holdings.get(h.fund_id)
            prev_shares = prev.shares_held if prev else h.shares_held
            share_change = h.shares_held - prev_shares

            shareholders.append({
                'fund_name': get_localized_field(h.fund, 'name', language),
                'fund_code': h.fund.code,
                'philosophy': h.fund.investment_philosophy,
                'shares_held': h.shares_held,
                'holding_pct': round(float(h.holding_pct) * 100, 1),
                'share_change': share_change,
                'action': h.action,
                'satisfaction': round(float(h.satisfaction_score), 3),
                'trade_reason': h.trade_reason,
                'rating': 'OVERWEIGHT' if h.action == 'buy' else ('UNDERWEIGHT' if h.action == 'sell' else 'NEUTRAL'),
            })
            total_fund_pct += float(h.holding_pct)

        # Market (passive) remainder
        market_pct = max(1.0 - total_fund_pct, 0)
        market_shares = int(market_pct * team.shares_outstanding)

        # Price history for chart
        price_trend = [{
            'round': ph.round_number,
            'price': float(ph.share_price),
            'book_value': float(ph.book_value_per_share),
            'sentiment': float(ph.sentiment_multiplier),
        } for ph in price_history]

        # Holding trend for chart
        funds = AIInvestorFund.objects.filter(scenario=game.scenario)
        holding_trend = []
        for r in range(0, latest_round + 1):
            entry = {'round': r}
            for fund in funds:
                h = AIInvestorHolding.objects.filter(
                    game=game, fund=fund, team=team, round_number=r,
                ).first()
                entry[fund.code] = round(float(h.holding_pct) * 100, 1) if h else 0
            entry['market'] = round(100 - sum(v for k, v in entry.items() if k != 'round'), 1)
            holding_trend.append(entry)

        # What investors want (preferences + gaps + alignment)
        from core.engine.investor_features import calculate_investor_features
        features = calculate_investor_features(team, game, latest_round)

        fund_profiles = []
        for fund in funds:
            prefs = []
            best_gap = None
            worst_gap_val = 0
            for p in fund.preferences.all():
                actual = features.get(p.feature_code, 3.0)
                ideal = float(p.ideal_value)
                gap = ideal - actual
                prefs.append({
                    'feature': p.feature_label,
                    'feature_code': p.feature_code,
                    'weight': round(float(p.weight), 2),
                    'ideal': ideal,
                    'actual': round(actual, 1),
                    'gap': round(gap, 1),
                })
                if abs(gap) * float(p.weight) > worst_gap_val:
                    worst_gap_val = abs(gap) * float(p.weight)
                    best_gap = p.feature_label

            h = holdings.filter(fund=fund).first()

            # CC-31G: Alignment scoring
            alignment = _calculate_fund_alignment(fund, features)

            # CC-31G: Fund profile data
            profile = fund.profile or {}

            fund_profiles.append({
                'name': get_localized_field(fund, 'name', language),
                'code': fund.code,
                'philosophy': fund.investment_philosophy,
                'description': get_localized_field(fund, 'description', language),
                'satisfaction': round(float(h.satisfaction_score), 3) if h else 0.5,
                'key_gap': best_gap,
                'preferences': prefs,
                # CC-31G: New fields for popover
                'fund_type': profile.get('fund_type', fund.investment_philosophy.title() + ' Fund'),
                'strategy_summary': profile.get('strategy_summary', fund.description),
                'dislikes': profile.get('dislikes', []),
                'alignment': alignment,
                'shares_held': h.shares_held if h else 0,
                'holding_pct': round(float(h.holding_pct) * 100, 1) if h else 0,
                'action': h.action if h else 'hold',
                'rating': ('OVERWEIGHT' if h.action == 'buy' else ('UNDERWEIGHT' if h.action == 'sell' else 'NEUTRAL')) if h else 'NEUTRAL',
                'trade_reason': h.trade_reason if h else '',
            })

        # Aggregate sentiment
        avg_satisfaction = sum(s['satisfaction'] for s in shareholders) / max(len(shareholders), 1)
        if avg_satisfaction >= 0.6:
            sentiment_label = 'Positive'
            sentiment_direction = 'buying'
        elif avg_satisfaction >= 0.45:
            sentiment_label = 'Neutral'
            sentiment_direction = 'holding'
        else:
            sentiment_label = 'Negative'
            sentiment_direction = 'selling'

        return Response({
            'round_number': latest_round,
            'share_price': float(current_price.share_price) if current_price else 0,
            'price_change': round(price_change, 2),
            'price_change_pct': round(price_change_pct * 100, 1),
            'book_value': float(current_price.book_value_per_share) if current_price else 0,
            'sentiment_multiplier': float(current_price.sentiment_multiplier) if current_price else 1,
            'market_cap': float(current_price.market_cap) if current_price else 0,
            'shares_outstanding': team.shares_outstanding,
            'shareholders': shareholders,
            'market_passive': {
                'shares': market_shares,
                'holding_pct': round(market_pct * 100, 1),
            },
            'price_trend': price_trend,
            'holding_trend': holding_trend,
            'fund_profiles': fund_profiles,
            'aggregate_sentiment': round(avg_satisfaction, 3),
            'sentiment_label': sentiment_label,
            'sentiment_direction': sentiment_direction,
        })
