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
    # R32 / V2-021 / V2-022. A commercially inactive firm must not finish above
    # one that competed. That property is enforced here, on the standings, and
    # no longer by overwriting the firm's carried index in `performance.py`:
    # replacing a carried score made the penalty grow with how far the firm had
    # climbed, so one event cost a leader 17.81 index points where it cost a
    # mid-table firm 5.00 (V2-119). The round-level consequence of not
    # competing stays the composite cap, bounded at 5.00.
    #
    # The classification is computed once, by the performance step, and only
    # read here, so the two controls cannot disagree about who was competing.
    # A context that never ran the performance step carries no classification
    # and demotes nobody -- that is the round-zero bootstrap, which ranks
    # before any round is played and where R22 requires a shared opening rank.
    inactive_team_ids = frozenset(
        getattr(context, 'commercially_inactive_team_ids', ()) or ())

    def published_key(team):
        return (
            # Leads the key, so no index and no tie-break can lift a firm that
            # did not compete above one that did, however far ahead it was
            # carrying. Because the shared-rank test below compares whole keys,
            # an inactive firm cannot even finish level with an active one.
            # Membership only: nothing here iterates, so the standings cannot
            # depend on the order teams or the classification arrive in.
            D('0') if team.id in inactive_team_ids else D('1'),
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

    demoted = [team.name for _rank, team in ranked_pairs
               if team.id in inactive_team_ids]
    if demoted:
        context.log.append(
            'Leaderboard: ranked below every firm that competed this round '
            '(commercially inactive): ' + ', '.join(demoted)
        )
