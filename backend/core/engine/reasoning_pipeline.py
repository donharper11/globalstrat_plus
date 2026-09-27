"""
Reasoning Pipeline: bridges database I/O with pure engine functions.

Called from advance_round.py Step 18 (Phase 1: deterministic dimensions 1-3).
Phase 2 (justification + student feedback) runs via narrative_jobs.

This module does the I/O: reads from decision/state tables,
builds immutable dataclass inputs, calls pure analysis functions,
and persists results to RoundResultReasoningAnalysis.
"""
import logging
from collections import Counter
from decimal import Decimal

from core.models.core import Game, Team
from core.models.decisions import (
    DecisionSubmission, DecisionBudgetAllocation, DecisionMarketing,
    DecisionMarketEntry, DecisionFinancing, DecisionPlant,
    DecisionESG, DecisionEventResponse, DecisionPlatformDevelopment,
    DecisionProductCreate, DecisionProductRetire,
)
from core.models.team_state import TeamMarketPresence, TeamProduct, TeamPlant
from core.models.results import EventInstance, ActiveModifier
from core.models.results_financials import RoundResultFinancials
from core.models.cc_reasoning import (
    RoundResultReasoningAnalysis, CompetitionReasoningAggregate,
)

from core.engine.reasoning_coherence import (
    CoherenceExtInput, ProductInfo, MarketPresenceInfo, BudgetInfo,
    MarketingInfo, MarketEntryInfo, FinancingInfo, PlantInfo,
    ESGInfo, GovernanceCommitment, PlatformDevInfo,
    calculate_coherence_ext,
)
from core.engine.reasoning_responsiveness import (
    ResponsivenessInput, EventSignal, DecisionChange,
    calculate_responsiveness,
)
from core.engine.reasoning_trajectory import (
    TrajectoryInput, RoundSnapshot, calculate_trajectory,
)
from core.engine.reasoning_aggregator import compose_scores

logger = logging.getLogger('engine')

D = Decimal


def run_reasoning_analysis(game, current_round, teams, context):
    """
    Run deterministic reasoning analysis (dims 1-3) for all teams.
    Called from advance_round.py Step 18.

    Returns count of teams evaluated.
    """
    count = 0
    for team in teams:
        try:
            _analyze_team(game, current_round, team, context)
            count += 1
        except Exception as e:
            logger.warning(
                'Reasoning analysis failed for team %s: %s',
                team.name, e, exc_info=True,
            )
    return count


def _analyze_team(game, current_round, team, context):
    """Run reasoning analysis for a single team."""
    submission = DecisionSubmission.objects.filter(
        team=team, round__round_number=current_round, round__game=game,
    ).first()

    # Dim 1: Extended Coherence
    coherence_input = _build_coherence_input(game, team, submission, context)
    coherence_result = calculate_coherence_ext(coherence_input)

    # Dim 2: Signal Responsiveness
    responsiveness_input = _build_responsiveness_input(game, team, submission, current_round)
    responsiveness_result = calculate_responsiveness(responsiveness_input)

    # Dim 3: Strategic Trajectory
    trajectory_input = _build_trajectory_input(game, team, current_round)
    trajectory_result = calculate_trajectory(trajectory_input)

    # Compose scores
    aggregated = compose_scores(
        coherence=coherence_result,
        responsiveness=responsiveness_result,
        trajectory=trajectory_result,
        justification=None,  # Phase 2
    )

    # Persist
    RoundResultReasoningAnalysis.objects.update_or_create(
        game=game, team=team, round_number=current_round,
        defaults={
            'reasoning_score_deterministic': D(str(aggregated.reasoning_score_deterministic)),
            'coherence_ext_score': D(str(coherence_result.score)),
            'responsiveness_score': D(str(responsiveness_result.score)),
            'trajectory_score': D(str(trajectory_result.score)),
            'coherence_ext_breakdown': {
                'sub_scores': coherence_result.sub_scores,
                'signals': coherence_result.signals,
            },
            'responsiveness_breakdown': {
                'events_relevant': responsiveness_result.events_relevant,
                'events_addressed': responsiveness_result.events_addressed,
                'details': [
                    {
                        'event': d.event_name,
                        'addressed': d.addressed,
                        'score': d.score,
                    }
                    for d in responsiveness_result.details
                ],
            },
            'trajectory_breakdown': {
                'pattern': trajectory_result.pattern,
                'stability': trajectory_result.stability_score,
                'feedback': trajectory_result.feedback,
            },
            'trajectory_pattern': trajectory_result.pattern,
            'overall_band': aggregated.overall_band,
            'feedback_student': aggregated.feedback_student,
            'feedback_judge': aggregated.feedback_judge,
            'engine_version': '1.0',
        },
    )

    # Update aggregate
    _update_aggregate(game, team)


def _build_coherence_input(game, team, submission, context):
    """Build CoherenceExtInput from database state."""
    # Products
    products = [
        ProductInfo(
            name=tp.name,
            positioning=tp.positioning or 'mainstream',
            platform_name=tp.platform.name if tp.platform else '',
        )
        for tp in TeamProduct.objects.filter(
            team=team, is_active=True,
        ).select_related('platform')
    ]

    # Market presences
    presences = [
        MarketPresenceInfo(
            market_name=mp.market.name,
            market_code=mp.market.code if hasattr(mp.market, 'code') else '',
            entry_mode=mp.entry_mode.name if mp.entry_mode else '',
            status=mp.status,
        )
        for mp in TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).select_related('market', 'entry_mode')
    ]

    # Budget
    budget = None
    if submission:
        try:
            ba = submission.budget_allocation
            budget = BudgetInfo(
                rd_budget=float(ba.rd_budget),
                marketing_budget=float(ba.marketing_budget),
                strategy_budget=float(ba.strategy_budget),
            )
        except DecisionBudgetAllocation.DoesNotExist:
            pass

    # Marketing decisions
    marketing_decisions = []
    if submission:
        for md in submission.marketing_decisions.all().select_related('team_product', 'market'):
            marketing_decisions.append(MarketingInfo(
                product_name=md.team_product.name,
                market_name=md.market.name,
                promotion_budget=float(md.promotion_budget),
                production_volume=md.production_volume,
            ))

    # Market entries
    entries = []
    if submission:
        for me in submission.market_entries.all().select_related('market'):
            entries.append(MarketEntryInfo(
                market_name=me.market.name,
                action=me.action,
                initial_investment=float(me.initial_investment),
            ))

    # Financing
    financing = None
    if submission:
        fin = DecisionFinancing.objects.filter(submission=submission).first()
        if fin:
            financing = FinancingInfo(
                new_debt=float(fin.new_debt or 0),
                debt_repayment=float(fin.debt_repayment or 0),
                dividend_per_share=float(fin.dividend_per_share or 0),
                equity_issued=float(fin.new_equity or 0),
            )

    # Plants
    plants = [
        PlantInfo(
            market_name=p.market.name if p.market else '',
            capacity=p.capacity_units or 0,
            status=p.status or 'operational',
        )
        for p in TeamPlant.objects.filter(
            team=team, status='operational',
        ).select_related('market')
    ]

    # ESG
    esg = None
    if submission:
        try:
            esg_dec = submission.esg
            esg = ESGInfo(
                environmental_spend=float(esg_dec.environmental_investment or 0),
                social_spend=float(esg_dec.social_investment or 0),
            )
        except DecisionESG.DoesNotExist:
            pass

    # Governance commitments
    from core.models.cc31_models import TeamGovernanceCommitment
    gov_commitments = [
        GovernanceCommitment(
            commitment_type=gc.commitment_type.code if gc.commitment_type else '',
            is_active=gc.is_active,
        )
        for gc in TeamGovernanceCommitment.objects.filter(
            game=game, team=team, is_active=True,
        ).select_related('commitment_type')
    ]

    # Platform devs
    platform_devs = []
    if submission:
        for pd in submission.platform_developments.all().select_related('team_platform'):
            platform_devs.append(PlatformDevInfo(
                platform_name=pd.team_platform.name if pd.team_platform else '',
                investment=float(pd.calculated_cost or 0),
            ))

    # Financial state — query from round results
    from core.models.results_financials import RoundResultFinancials as _RRF
    _fin = _RRF.objects.filter(
        game=game, team=team, round_number=context._round_number if hasattr(context, "_round_number") else game.current_round,
    ).first()
    total_revenue = float(_fin.total_revenue) if _fin else 0.0
    total_debt = float(_fin.total_debt) if _fin else 0.0
    total_equity = float(_fin.total_equity) if _fin else 1.0

    return CoherenceExtInput(
        products=products,
        market_presences=presences,
        budget=budget,
        marketing_decisions=marketing_decisions,
        market_entries=entries,
        financing=financing,
        plants=plants,
        esg=esg,
        governance_commitments=gov_commitments,
        platform_devs=platform_devs,
        total_revenue=max(total_revenue, 1.0),
        total_debt=total_debt,
        total_equity=max(total_equity, 1.0),
    )


def _build_responsiveness_input(game, team, submission, current_round):
    """Build ResponsivenessInput from events and decision changes."""
    # Active events this round
    events = []
    for ei in EventInstance.objects.filter(
        game=game, round_number=current_round,
    ).select_related('event_template'):
        template = ei.event_template
        affected = [ei.target_market.name] if ei.target_market else []
        events.append(EventSignal(
            event_name=template.name if template else 'Unknown',
            category=template.category if template else 'MARKET',
            affected_markets=affected,
            severity=0.5,  # severity is a char choice, use default
        ))

    # Active modifiers
    for am in ActiveModifier.objects.filter(
        game=game, started_round__lte=current_round,
    ).exclude(expires_round__lt=current_round):
        market_name = am.target_market.name if am.target_market else ''
        events.append(EventSignal(
            event_name=am.modifier_type or 'Modifier',
            category='MARKET',
            affected_markets=[market_name] if market_name else [],
            severity=0.3,
        ))

    # Check for event response
    has_response = False
    if submission:
        has_response = DecisionEventResponse.objects.filter(
            submission=submission,
        ).exists()

    # Decision changes from previous round
    changes = _detect_decision_changes(game, team, current_round)

    active_markets = list(
        TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).values_list('market__name', flat=True)
    )

    return ResponsivenessInput(
        events=events,
        has_event_response=has_response,
        decision_changes=changes,
        active_market_names=active_markets,
    )


def _detect_decision_changes(game, team, current_round):
    """Detect changes in decisions between current and previous round."""
    if current_round < 2:
        return []

    prev_round = current_round - 1
    changes = []

    # Compare budget allocations
    curr_sub = DecisionSubmission.objects.filter(
        team=team, round__round_number=current_round, round__game=game,
    ).first()
    prev_sub = DecisionSubmission.objects.filter(
        team=team, round__round_number=prev_round, round__game=game,
    ).first()

    if curr_sub and prev_sub:
        try:
            curr_ba = curr_sub.budget_allocation
            prev_ba = prev_sub.budget_allocation
            rd_change = abs(float(curr_ba.rd_budget) - float(prev_ba.rd_budget))
            total = float(curr_ba.rd_budget + curr_ba.marketing_budget + curr_ba.strategy_budget)
            if total > 0 and rd_change / total > 0.1:
                changes.append(DecisionChange(
                    domain='rd',
                    description=f'R&D budget changed by {rd_change:,.0f}',
                    magnitude=min(rd_change / total, 1.0),
                ))
            mktg_change = abs(float(curr_ba.marketing_budget) - float(prev_ba.marketing_budget))
            if total > 0 and mktg_change / total > 0.1:
                changes.append(DecisionChange(
                    domain='marketing',
                    description=f'Marketing budget changed by {mktg_change:,.0f}',
                    magnitude=min(mktg_change / total, 1.0),
                ))
        except DecisionBudgetAllocation.DoesNotExist:
            pass

        # Compare pricing
        curr_prices = {
            (md.team_product_id, md.market_id): float(md.retail_price)
            for md in curr_sub.marketing_decisions.all()
        }
        prev_prices = {
            (md.team_product_id, md.market_id): float(md.retail_price)
            for md in prev_sub.marketing_decisions.all()
        }
        for key, curr_price in curr_prices.items():
            prev_price = prev_prices.get(key)
            if prev_price and abs(curr_price - prev_price) / max(prev_price, 1) > 0.05:
                changes.append(DecisionChange(
                    domain='pricing',
                    description=f'Price changed from {prev_price:.0f} to {curr_price:.0f}',
                    magnitude=min(abs(curr_price - prev_price) / max(prev_price, 1), 1.0),
                ))

        # Check for new sourcing changes
        curr_entries = set(
            me.market_id
            for me in curr_sub.market_entries.filter(action='enter')
        )
        if curr_entries:
            changes.append(DecisionChange(
                domain='market_entry',
                description=f'{len(curr_entries)} new market entries',
                magnitude=min(len(curr_entries) * 0.3, 1.0),
            ))

    return changes


def _build_trajectory_input(game, team, current_round):
    """Build TrajectoryInput from historical round data."""
    snapshots = []

    for rn in range(1, current_round + 1):
        sub = DecisionSubmission.objects.filter(
            team=team, round__round_number=rn, round__game=game,
        ).first()

        rd_pct = mktg_pct = strat_pct = 0.0
        if sub:
            try:
                ba = sub.budget_allocation
                total = float(ba.rd_budget + ba.marketing_budget + ba.strategy_budget)
                if total > 0:
                    rd_pct = float(ba.rd_budget) / total
                    mktg_pct = float(ba.marketing_budget) / total
                    strat_pct = float(ba.strategy_budget) / total
            except DecisionBudgetAllocation.DoesNotExist:
                pass

        num_markets = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).count()  # Current state — simplified for now

        num_products = TeamProduct.objects.filter(
            team=team, is_active=True,
        ).count()

        new_entries = 0
        exits = 0
        new_products = 0
        retired_products = 0
        if sub:
            new_entries = sub.market_entries.filter(action='enter').count()
            exits = sub.market_entries.filter(action='exit').count()
            new_products = DecisionProductCreate.objects.filter(submission=sub).count()
            retired_products = DecisionProductRetire.objects.filter(submission=sub).count()

        avg_price = 0.0
        if sub:
            prices = list(
                sub.marketing_decisions.values_list('retail_price', flat=True)
            )
            if prices:
                avg_price = sum(float(p) for p in prices) / len(prices)

        fin = RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=rn,
        ).first()
        total_debt = float(fin.total_debt) if fin else 0.0
        total_equity = float(fin.total_equity) if fin else 1.0
        total_revenue = float(fin.total_revenue) if fin else 0.0

        snapshots.append(RoundSnapshot(
            round_number=rn,
            rd_budget_pct=rd_pct,
            marketing_budget_pct=mktg_pct,
            strategy_budget_pct=strat_pct,
            num_active_markets=num_markets,
            num_products=num_products,
            num_new_entries=new_entries,
            num_exits=exits,
            num_new_products=new_products,
            num_retired_products=retired_products,
            avg_price=avg_price,
            total_debt=total_debt,
            total_equity=total_equity,
            total_revenue=total_revenue,
        ))

    return TrajectoryInput(round_snapshots=snapshots)


def _update_aggregate(game, team):
    """Update CompetitionReasoningAggregate from all RoundResultReasoningAnalysis records."""
    analyses = RoundResultReasoningAnalysis.objects.filter(
        game=game, team=team,
    ).order_by('round_number')

    if not analyses.exists():
        return

    scores = [float(a.reasoning_score_deterministic) for a in analyses]
    coherence_scores = [float(a.coherence_ext_score) for a in analyses]
    resp_scores = [float(a.responsiveness_score) for a in analyses]
    traj_scores = [float(a.trajectory_score) for a in analyses]
    patterns = [a.trajectory_pattern for a in analyses]

    avg_score = sum(scores) / len(scores)

    # Dominant pattern
    pattern_counts = Counter(patterns)
    dominant = pattern_counts.most_common(1)[0]
    dominant_pattern = dominant[0]
    pattern_consistency = dominant[1] / len(patterns)

    # Score trend
    if len(scores) >= 3:
        first_half = scores[:len(scores) // 2]
        second_half = scores[len(scores) // 2:]
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        if second_avg > first_avg + 3:
            trend = 'improving'
        elif second_avg < first_avg - 3:
            trend = 'declining'
        else:
            trend = 'stable'
    else:
        trend = 'stable'

    # Round-by-round detail
    round_detail = {
        str(a.round_number): {
            'score': float(a.reasoning_score_deterministic),
            'band': a.overall_band,
            'pattern': a.trajectory_pattern,
            'coherence': float(a.coherence_ext_score),
            'responsiveness': float(a.responsiveness_score),
            'trajectory': float(a.trajectory_score),
        }
        for a in analyses
    }

    CompetitionReasoningAggregate.objects.update_or_create(
        game=game, team=team,
        defaults={
            'aggregate_reasoning_score': D(str(round(avg_score, 2))),
            'rounds_evaluated': len(scores),
            'avg_coherence_ext': D(str(round(sum(coherence_scores) / len(coherence_scores), 2))),
            'avg_responsiveness': D(str(round(sum(resp_scores) / len(resp_scores), 2))),
            'avg_trajectory': D(str(round(sum(traj_scores) / len(traj_scores), 2))),
            'dominant_pattern': dominant_pattern,
            'pattern_consistency': D(str(round(pattern_consistency, 2))),
            'score_trend': trend,
            'round_by_round': round_detail,
        },
    )
