"""
Engine Step 15: Leaderboard Update.
From 03-engine-logic.md Section 14.
"""
from decimal import Decimal, ROUND_HALF_UP

from core.models.scenario import MarketDefinition
from core.models.results_financials import LeaderboardEntry, RoundResultMarketRevenue

D = Decimal


def update_leaderboard(context):
    """
    Rank all teams by performance_index (descending).
    Create LeaderboardEntry for each team with financial summary
    and market share per market.
    """
    game = context.game
    current_round = context.round_number
    scenario = context.scenario

    # Sort by PI first. At the nonnegative PI floor, the performance guard
    # cannot put a zero-revenue team numerically below a selling team at 0.00,
    # so positive revenue is the explicit tie-break. Revenue, net income, and
    # team id make all remaining ties deterministic and financially legible.
    financials_by_team = getattr(context, 'financials', {}) or {}
    teams_ranked = sorted(
        context.teams,
        key=lambda t: (
            D(str(t.performance_index)),
            D(str(financials_by_team.get(t.id, {}).get('total_revenue', 0) or 0)) > 0,
            D(str(financials_by_team.get(t.id, {}).get('total_revenue', 0) or 0)),
            D(str(financials_by_team.get(t.id, {}).get('net_income', 0) or 0)),
            -t.id,
        ),
        reverse=True,
    )

    markets = MarketDefinition.objects.filter(scenario=scenario)

    for rank, team in enumerate(teams_ranked, 1):
        financials = getattr(context, 'financials', {}).get(team.id, {})

        # Build market share summary
        market_share_summary = {}
        for market in markets:
            try:
                mr = RoundResultMarketRevenue.objects.get(
                    game=game, round_number=current_round,
                    team=team, market=market,
                )
                market_share_summary[market.code] = float(mr.market_share_pct)
            except RoundResultMarketRevenue.DoesNotExist:
                market_share_summary[market.code] = 0.0

        LeaderboardEntry.objects.update_or_create(
            game=game, round_number=current_round, team=team,
            defaults={
                'rank': rank,
                'performance_index': team.performance_index,
                'shareholder_return': financials.get('shareholder_return', D('0')),
                'total_revenue': financials.get('total_revenue', D('0')),
                'net_income': financials.get('net_income', D('0')),
                'market_share_summary': market_share_summary,
            },
        )

    context.log.append(
        'Leaderboard: ' + ', '.join(
            f'#{i+1} {t.name} ({t.performance_index})'
            for i, t in enumerate(teams_ranked)
        )
    )
