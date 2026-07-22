"""
Engine Step 13: Performance Index Calculation.
From 03-engine-logic.md Section 12.
"""
from decimal import Decimal, ROUND_HALF_UP

from core.models.scenario import SegmentDefinition
from core.models.team_state import TeamMarketPresence
from core.models.decisions import DecisionSubmission
from core.models.results_financials import RoundResultPerformanceIndex
from core.engine.utils import get_config

D = Decimal


PI_WEIGHTS = {
    'market': D('0.30'),
    'capability': D('0.25'),
    'financial': D('0.15'),
    'stakeholder': D('0.15'),
    'resilience': D('0.15'),
}


def _clamp01(value):
    return max(D('0'), min(D('1'), D(str(value))))


def _ratio(value, denominator):
    value = D(str(value or 0))
    denominator = D(str(denominator or 0))
    if denominator <= 0:
        return D('0')
    return _clamp01(value / denominator)


def _segment_score(context, team, all_segments, active_market_ids, segment_types):
    weighted_score = D('0')
    total_weight = D('0')

    for segment in all_segments:
        if segment.segment_type not in segment_types:
            continue

        weight = D(str(segment.performance_index_weight or 0))
        if weight <= 0:
            continue

        market = segment.market
        if market is None:
            key = (team.id, segment.id, None)
            fit = D(str(context.fit_scores.get(key, 0.5)))
            fit = D(str(context.adjusted_fit_scores.get(key, fit)))
        elif market.id in active_market_ids:
            key = (team.id, segment.id, market.id)
            fit = D(str(context.fit_scores.get(key, 0.5)))
            fit = D(str(context.adjusted_fit_scores.get(key, fit)))
        elif segment.segment_type == 'customer':
            continue
        else:
            fit = D('0.5')

        weighted_score += _clamp01(fit) * weight
        total_weight += weight

    if total_weight <= 0:
        return D('0.5')
    return _clamp01(weighted_score / total_weight)


def _team_financials(context, team):
    return getattr(context, 'financials', {}).get(team.id, {}) or {}


def _financial_component(context, team, max_revenue, max_abs_net_income):
    financials = _team_financials(context, team)
    revenue = D(str(financials.get('total_revenue', 0) or 0))
    net_income = D(str(financials.get('net_income', 0) or 0))
    debt_to_equity = D(str(financials.get('debt_to_equity', 0) or 0))

    revenue_score = _ratio(revenue, max_revenue)
    if max_abs_net_income > 0:
        profit_score = _clamp01(D('0.5') + (net_income / max_abs_net_income) * D('0.5'))
    else:
        profit_score = D('0.5')
    debt_score = D('1') - _clamp01(debt_to_equity / D('2'))

    return _clamp01(revenue_score * D('0.40') + profit_score * D('0.40') + debt_score * D('0.20'))


def _strategic_capability_component(team, current_round):
    submission = (
        DecisionSubmission.objects
        .filter(team=team, round__round_number=current_round)
        .first()
    )
    if submission is None:
        return D('0.35')

    rd_score = D('0')
    if hasattr(submission, 'budget_allocation'):
        rd_budget = D(str(submission.budget_allocation.rd_budget or 0))
        rd_spend = sum(D(str(row.amount or 0)) for row in submission.rd_investments.all())
        rd_score = _ratio(rd_spend, rd_budget) if rd_budget > 0 else D('0')

    has_product_action = (
        submission.product_creates.exists()
        or submission.product_retires.exists()
        or submission.platform_developments.exists()
    )
    has_strategy_action = (
        submission.market_entries.exists()
        or submission.plant_decisions.exists()
        or submission.partnerships.exists()
        or submission.acquisitions.exists()
        or hasattr(submission, 'esg')
    )

    product_score = D('1') if has_product_action else D('0.45')
    strategy_score = D('1') if has_strategy_action else D('0.45')
    return _clamp01(rd_score * D('0.40') + product_score * D('0.30') + strategy_score * D('0.30'))


def _market_component(context, team, customer_score, max_revenue):
    revenue = D(str(_team_financials(context, team).get('total_revenue', 0) or 0))
    revenue_score = _ratio(revenue, max_revenue)
    return _clamp01(customer_score * D('0.60') + revenue_score * D('0.40'))


def _active_freezes(context, team, active_market_ids):
    return [
        item for item in getattr(context, 'compliance_freezes', set())
        if item[0] == team.id and item[1] in active_market_ids
    ]


def _stakeholder_component(context, team, stakeholder_fit, active_market_ids):
    team_freezes = _active_freezes(context, team, active_market_ids)
    penalty = D('0')
    if team_freezes:
        penalty += min(D('0.30'), D('0.12') * D(len(team_freezes)))
    return _clamp01(stakeholder_fit - penalty)


def _execution_resilience_component(context, team, max_revenue, active_market_ids):
    capacity_factor = D(str(getattr(context, 'sc_capacity_factor', {}).get(team.id, 1) or 1))
    disruption_cost = D(str(getattr(context, 'sc_disruption_costs', {}).get(team.id, 0) or 0))
    freeze_count = len(_active_freezes(context, team, active_market_ids))

    capacity_score = _clamp01(capacity_factor)
    incident_penalty = min(D('0.45'), D('0.18') * D(freeze_count))
    cost_penalty = _clamp01(disruption_cost / max(max_revenue, D('1'))) * D('0.50')
    return _clamp01(capacity_score - incident_penalty - cost_penalty)


def calculate_performance_index(context):
    """
    Calculate a strategic-management performance index.

    The persisted satisfaction_score field stores the final composite score
    because the result model predates the five-component breakdown.
    """
    scenario = context.scenario
    current_round = context.round_number
    sensitivity = D(str(get_config(scenario, 'performance_index_sensitivity', default=20.0)))

    all_segments = list(SegmentDefinition.objects.filter(scenario=scenario).select_related('market'))
    financials_by_team = getattr(context, 'financials', {}) or {}
    revenues = [D(str(values.get('total_revenue', 0) or 0)) for values in financials_by_team.values()]
    net_incomes = [abs(D(str(values.get('net_income', 0) or 0))) for values in financials_by_team.values()]
    max_revenue = max(revenues) if revenues else D('0')
    max_abs_net_income = max(net_incomes) if net_incomes else D('0')

    for team in context.teams:
        active_market_ids = set(
            TeamMarketPresence.objects.filter(
                team=team, status='active',
            ).values_list('market_id', flat=True)
        )

        customer_score = _segment_score(context, team, all_segments, active_market_ids, {'customer'})
        stakeholder_fit = _segment_score(
            context, team, all_segments, active_market_ids,
            {'investor', 'regulator', 'channel_partner', 'community'},
        )
        market_score = _market_component(context, team, customer_score, max_revenue)
        capability_score = _strategic_capability_component(team, current_round)
        financial_score = _financial_component(context, team, max_revenue, max_abs_net_income)
        stakeholder_score = _stakeholder_component(context, team, stakeholder_fit, active_market_ids)
        resilience_score = _execution_resilience_component(context, team, max_revenue, active_market_ids)

        composite_score = (
            market_score * PI_WEIGHTS['market']
            + capability_score * PI_WEIGHTS['capability']
            + financial_score * PI_WEIGHTS['financial']
            + stakeholder_score * PI_WEIGHTS['stakeholder']
            + resilience_score * PI_WEIGHTS['resilience']
        ).quantize(D('0.0001'), rounding=ROUND_HALF_UP)

        index_change = ((composite_score - D('0.5')) * sensitivity).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )

        previous_index = team.performance_index
        new_index = max(D('0'), previous_index + index_change)

        # Update team
        team.performance_index = new_index
        team.save()

        # Write result
        RoundResultPerformanceIndex.objects.update_or_create(
            game=context.game, round_number=current_round, team=team,
            defaults={
                'satisfaction_score': composite_score,
                'index_change': index_change,
                'index_value': new_index,
            },
        )

        context.log.append(
            f'Performance index: {team.name} '
            f'{previous_index} → {new_index} '
            f'({"+" if index_change >= 0 else ""}{index_change}); '
            f'market={market_score:.3f}, capability={capability_score:.3f}, '
            f'financial={financial_score:.3f}, stakeholder={stakeholder_score:.3f}, '
            f'resilience={resilience_score:.3f}'
        )
