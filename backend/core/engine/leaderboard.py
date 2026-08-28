"""
Engine Step 15: Leaderboard Update.
From 03-engine-logic.md Section 14.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from core.models.scenario import MarketDefinition
from core.models.results_financials import (
    LeaderboardEntry, RoundResultFinancials, RoundResultMarketRevenue)
from core.models.sc_state import ResilienceScoreHistory

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

    # Published competition tie-break: cumulative operating cash flow,
    # cumulative revenue, then current/final-round resilience. Team id is only
    # a stable display ordering if every published criterion remains equal;
    # competition rules treat that final condition as a shared prize tie.
    financials_by_team = getattr(context, 'financials', {}) or {}
    cumulative = {
        row['team_id']: row
        for row in RoundResultFinancials.objects.filter(
            game=game, round_number__lte=current_round,
        ).values('team_id').annotate(
            operating_cash_flow=Sum('operating_cash_flow'),
            total_revenue=Sum('total_revenue'),
        )
    }
    for team in context.teams:
        if team.id not in cumulative:
            current = financials_by_team.get(team.id, {})
            cumulative[team.id] = {
                'operating_cash_flow': current.get('operating_cash_flow', 0),
                'total_revenue': current.get('total_revenue', 0),
            }
    resilience = dict(ResilienceScoreHistory.objects.filter(
        team__game=game, round__round_number=current_round,
    ).values_list('team_id', 'score'))
    def published_key(team):
        return (
            D(str(team.performance_index)),
            D(str(cumulative.get(team.id, {}).get('operating_cash_flow', 0) or 0)),
            D(str(cumulative.get(team.id, {}).get('total_revenue', 0) or 0)),
            D(str(resilience.get(team.id, 0) or 0)),
        )

    teams_ranked = sorted(
        context.teams,
        key=lambda t: published_key(t) + (
            -t.id,
        ),
        reverse=True,
    )

    markets = (MarketDefinition.objects.filter(scenario=scenario)).order_by('code')

    previous_key = None
    shared_rank = 0
    ranked_pairs = []
    for position, team in enumerate(teams_ranked, 1):
        team_key = published_key(team)
        if team_key != previous_key:
            shared_rank = position
        previous_key = team_key
        ranked_pairs.append((shared_rank, team))
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
                'rank': shared_rank,
                'performance_index': team.performance_index,
                'shareholder_return': financials.get('shareholder_return', D('0')),
                'total_revenue': financials.get('total_revenue', D('0')),
                'net_income': financials.get('net_income', D('0')),
                'market_share_summary': market_share_summary,
            },
        )

    context.log.append(
        'Leaderboard: ' + ', '.join(
            f'#{rank} {team.name} ({team.performance_index})'
            for rank, team in ranked_pairs
        )
    )
