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

# --- R34: the recorded vocabulary of a demotion -----------------------------
# Stable strings: they are what a dispute is answered with months later, so
# they are part of the record's meaning and are not reworded casually. The
# same standard `price_band` sets for its own rule identifiers.
ACTION_INACTIVITY_DEMOTION = 'inactivity_rank_demotion'
RULE_INACTIVE_RANKED_BELOW_ACTIVE = 'inactivity.ranked_below_every_active_firm'
CLASSIFICATION_INACTIVE = 'commercially_inactive'
# Names the engine step that decided it, the way the price-band receipts name
# `engine:close_round`. `user=None` is what CRV2-08's instructor drill-down
# renders as actor `system`.
AUDIT_ENDPOINT = 'engine:update_leaderboard'


def _s(value):
    """Null stays null. `str(None)` would store the string 'None', which reads
    as a value in a dispute rather than as the absence of one."""
    return None if value is None else str(value)


def demotion_audit_payload(*, team, rank, round_number, lowest_active,
                           active_count, inactive_count):
    """The record a demotion leaves behind.

    Carries what a disputing team actually asks — *why am I below a team I
    outscored?* — and carries it in a form that can be checked rather than
    merely asserted: the firm's own carried index, the lowest index among the
    firms that competed and which firm held it, the rank received, the round,
    and the classification that caused it. Names as well as ids, because a
    human reads this in a dispute.

    ``lowest_active`` is ``(index, team_name, rank)`` or ``None`` when no firm
    competed at all — a field in which nobody competed has no comparison to
    make, and inventing one would be the dishonest half of this record.
    """
    index = D(str(team.performance_index))
    lowest_index = lowest_active[0] if lowest_active else None
    return {
        'rule': RULE_INACTIVE_RANKED_BELOW_ACTIVE,
        'classification': CLASSIFICATION_INACTIVE,
        'round_number': round_number,
        'team_id': team.id,
        'team_name': team.name,
        'rank': rank,
        'performance_index': _s(index),
        'lowest_active_performance_index': _s(lowest_index),
        'lowest_active_team_name': lowest_active[1] if lowest_active else None,
        'lowest_active_rank': lowest_active[2] if lowest_active else None,
        'active_firm_count': active_count,
        'inactive_firm_count': inactive_count,
        # The inversion itself, stated rather than left to be inferred. False
        # when the firm would have finished last regardless: the guard still
        # fired, and the record says so without claiming it cost a place.
        'outscored_a_firm_ranked_above': bool(
            lowest_index is not None and index > lowest_index),
    }


def _record_demotions(game, round_number, ranked_pairs, inactive_team_ids):
    """R34. Write one audit event per demoted team per round.

    Why an audit event and not a field on the stored row: `performance` and
    `leaderboard` are hashed output sections, so a new field on either would
    take the manifest envelope from v6 to v7 and make every hash comparison
    across that point differ while no outcome had changed. The audit trail is
    deliberately outside the hashed output (`decision_audit_event` is
    `in_output=False`), which is why the explanation goes there.

    IDEMPOTENT BY SKIPPING, not by overwriting. `DecisionAuditEvent.save`
    refuses to rewrite an existing row and `0070_audit_guards` installs
    database triggers that refuse `UPDATE` and `DELETE` on the table, so
    "recompute and replace" is not available and must not be attempted. A
    round recomputed after a correction or a reopen therefore leaves the
    receipt it already has. That is the honest property for an append-only
    evidence table: the first recorded explanation of a firing stands.

    A round with no `Round` row records nothing and still ranks. An audit event
    is keyed to a round, so there is nothing to key to -- this is the
    round-zero bootstrap, which ranks before any round is played.
    """
    from core.models import DecisionAuditEvent
    from core.models.core import Round

    demoted_pairs = [(rank, team) for rank, team in ranked_pairs
                     if team.id in inactive_team_ids]
    if not demoted_pairs:
        return 0

    round_obj = Round.objects.filter(
        game=game, round_number=round_number).first()
    if round_obj is None:
        return 0

    # The weakest firm that actually competed: the comparison that makes the
    # inversion legible. Taken from `ranked_pairs`, which is already in the
    # published order, so ties resolve to the worst-ranked such firm and the
    # choice cannot depend on the order teams arrived in (V2-012).
    lowest_active = None
    active_count = 0
    for rank, team in ranked_pairs:
        if team.id in inactive_team_ids:
            continue
        active_count += 1
        index = D(str(team.performance_index))
        if lowest_active is None or index <= lowest_active[0]:
            lowest_active = (index, team.name, rank)

    already_recorded = set(DecisionAuditEvent.objects.filter(
        game=game, round=round_obj, action=ACTION_INACTIVITY_DEMOTION,
    ).values_list('team_id', flat=True))

    written = 0
    for rank, team in demoted_pairs:
        if team.id in already_recorded:
            continue
        DecisionAuditEvent.objects.create(
            game=game, team=team, round=round_obj, user=None,
            action=ACTION_INACTIVITY_DEMOTION, endpoint=AUDIT_ENDPOINT,
            payload=demotion_audit_payload(
                team=team, rank=rank, round_number=round_number,
                lowest_active=lowest_active, active_count=active_count,
                inactive_count=len(demoted_pairs)))
        written += 1
    return written


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

    # R34. The firing must be visible in stored data, not only in this log.
    # Recorded here, where the demotion is decided, and as an audit event
    # rather than a field on the hashed `performance` or `leaderboard` rows --
    # which is what keeps the manifest envelope at v6.
    _record_demotions(game, current_round, ranked_pairs, inactive_team_ids)
