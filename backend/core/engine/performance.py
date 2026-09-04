"""
Engine Step 13: Performance Index Calculation.
From 03-engine-logic.md Section 12.
"""
from decimal import Decimal, ROUND_HALF_UP

from core.models.scenario import SegmentDefinition
from core.models.team_state import TeamMarketPresence
from core.models.decisions import DecisionSubmission
from core.models.results_financials import RoundResultPerformanceIndex
# InvalidScenarioConfiguration is re-exported: it moved to utils when the
# preference engine needed it too, and callers already import it from here.
from core.engine.utils import (  # noqa: F401
    InvalidScenarioConfiguration, get_config, scenario_optimal_headcounts,
    staffing_adequacy)

D = Decimal


PI_WEIGHTS = {
    'market': D('0.30'),
    'capability': D('0.25'),
    'financial': D('0.15'),
    'stakeholder': D('0.15'),
    'resilience': D('0.15'),
}

COMMERCIAL_INACTIVITY_COMPOSITE_CAP = D('0.25')

# V2-021. Strategic capability used to score R&D as `rd_spend / rd_budget`,
# where the denominator was the team's *own declared budget*. That measured
# self-consistency rather than investment: declaring $1 and spending $1 scored
# a perfect 1.00 while a $100,000 programme against a $2,000,000 budget scored
# 0.05 — cheaper and higher-scoring, whatever opponents did.
#
# The denominator is now a scenario constant the team cannot choose. It is not
# normalised against the cohort maximum, because that would hand $1 full credit
# whenever $1 happened to be the largest spend in the room.
RD_SPEND_TARGET_CONFIG_KEY = 'rd_spend_target'




def scenario_rd_spend_target(scenario):
    """Validate the configured R&D spend target, or refuse to score.

    R10 / V2-053 removed the term that divided by this, so nothing scores
    against it now. The V2-021 precondition is deliberately left standing
    rather than quietly dropped: removing a fail-closed guard an audit
    installed is not this change's business, and the handoff fences
    `rd_spend_target` off from being touched. It is now an orphaned
    requirement, recorded as such for the owner.
    """
    raw = get_config(scenario, RD_SPEND_TARGET_CONFIG_KEY, default=None)
    if raw is None:
        raise InvalidScenarioConfiguration(
            f'scenario {getattr(scenario, "id", scenario)} has no '
            f'{RD_SPEND_TARGET_CONFIG_KEY!r} configured; strategic capability '
            f'cannot be scored without it')
    target = D(str(raw))
    if target <= 0:
        raise InvalidScenarioConfiguration(
            f'scenario {getattr(scenario, "id", scenario)} sets '
            f'{RD_SPEND_TARGET_CONFIG_KEY}={target}; it must be greater than '
            f'zero. It was the denominator of the R&D capability score until '
            f'R10 retired that term; the check stands, the score does not.')
    return target


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


def _strategic_capability_component(team, current_round, rd_spend_target,
                                    optimal_headcounts):
    """Capability earned by decisions, scaled by whether anyone is staffed.

    V2-025. The score below is what the team's spending and actions earn; the
    multiplicative staffing factor is whether it has the people to do any of
    it. Before this, emptying all three talent pools saved $1,200,000 of
    payroll and moved this component by exactly 0.0000 -- headcount was not
    read here at all -- so stripping the firm was free index, and won 9 of 9
    holdout cells independently of opponents.
    """
    submission = (
        DecisionSubmission.objects
        .filter(team=team, round__round_number=current_round)
        .first()
    )
    if submission is None:
        return D('0.35')

    # R10 / V2-053: the R&D-spend term is gone. It scored the *amount* of a
    # DecisionRDInvestment, so a team earned strategic capability by spending
    # rather than by delivering anything -- and after R9 retired the upgrade
    # path, the money bought no capability at all. Money spent is a financial
    # consequence, not a capability.
    #
    # Nothing replaces it. Platform development already registers below through
    # `has_product_action`, and what it delivers is scored where capability is
    # actually felt: market fit, revenue and profit.

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
    # The surviving terms keep their authored 30:30 ratio and are normalised
    # over their own weights, so removing a term does not silently deflate
    # every team's ceiling to 0.60. This is removal, not a re-weighting: no
    # weight was retuned, and the handoff forbids that in this change.
    earned = _clamp01((product_score * D('0.30') + strategy_score * D('0.30'))
                      / D('0.60'))

    from core.models.talent import DecisionTalent
    try:
        talent = submission.talent
    except DecisionTalent.DoesNotExist:
        talent = None
    headcounts = {
        pool: (getattr(talent, f'{pool}_headcount', 0) if talent else 0)
        for pool in ('rd', 'commercial', 'operations')
    }
    adequacy = D(str(staffing_adequacy(headcounts, optimal_headcounts)))
    return _clamp01(earned * adequacy)


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


def material_revenue_floor(revenues):
    """The revenue below which a team is not competing, for this round.

    V2-022. The old test asked whether a team had *declared* production,
    promotion, distribution or staffing. It tested intent, so setting
    `production_volume = 1` escaped the composite cap for $181.86 — with
    revenue of exactly zero, because nothing was sold. Declaring an intention
    to produce is not competing.

    The floor is one percent of the largest positive revenue in the round, and
    never less than a dollar, so a cohort where nobody sells anything still
    classifies everybody as inactive rather than dividing by zero.
    """
    positive = [D(str(value)) for value in revenues if D(str(value)) > 0]
    highest = max(positive) if positive else D('0')
    return max(D('1'), (highest * D('0.01')))


def is_commercially_inactive(revenue, floor):
    """One classification, shared by the composite cap and the ranking guard.

    Both controls express the same idea — a firm that did not compete must not
    outrank one that did — and they used to test it differently: one on
    declared decisions, the other on revenue being exactly zero. Two tests for
    one idea is one test too many.
    """
    return D(str(revenue or 0)) < floor


def _enforce_inactive_revenue_invariant(candidates):
    """Keep a commercially inactive firm from outranking one that competed.

    Written against zero revenue until V2-022; it now uses the same
    `commercially_inactive` classification the composite cap uses, so the two
    controls cannot disagree about who was competing.
    """
    active_indexes = [
        item['new_index'] for item in candidates
        if not item['commercially_inactive']
    ]
    if not active_indexes:
        return

    ceiling = max(D('0'), min(active_indexes) - D('0.01'))
    for item in candidates:
        if item['commercially_inactive'] and item['new_index'] >= min(active_indexes):
            item['new_index'] = ceiling
            item['guard_applied'] = True


def calculate_performance_index(context):
    """
    Calculate a strategic-management performance index.

    The persisted satisfaction_score field stores the final composite score
    because the result model predates the five-component breakdown.
    """
    scenario = context.scenario
    current_round = context.round_number
    sensitivity = D(str(get_config(scenario, 'performance_index_sensitivity', default=20.0)))
    # Fails closed: a scenario without a usable target is not scored at all.
    rd_spend_target = scenario_rd_spend_target(scenario)
    optimal_headcounts = scenario_optimal_headcounts(scenario)

    all_segments = list((SegmentDefinition.objects.filter(scenario=scenario).select_related('market')).order_by('pk'))
    financials_by_team = getattr(context, 'financials', {}) or {}
    revenues = [D(str(values.get('total_revenue', 0) or 0)) for values in financials_by_team.values()]
    net_incomes = [abs(D(str(values.get('net_income', 0) or 0))) for values in financials_by_team.values()]
    max_revenue = max(revenues) if revenues else D('0')
    revenue_floor = material_revenue_floor(revenues)
    max_abs_net_income = max(net_incomes) if net_incomes else D('0')

    candidates = []
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
        capability_score = _strategic_capability_component(
            team, current_round, rd_spend_target, optimal_headcounts)
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

        commercially_inactive = is_commercially_inactive(
            _team_financials(context, team).get('total_revenue', 0), revenue_floor,
        )
        if commercially_inactive:
            composite_score = min(
                composite_score, COMMERCIAL_INACTIVITY_COMPOSITE_CAP,
            )

        index_change = ((composite_score - D('0.5')) * sensitivity).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )

        previous_index = team.performance_index
        new_index = max(D('0'), previous_index + index_change)

        candidates.append({
            'team': team,
            'previous_index': previous_index,
            'new_index': new_index,
            'revenue': D(str(_team_financials(context, team).get('total_revenue', 0) or 0)),
            'composite_score': composite_score,
            'market_score': market_score,
            'capability_score': capability_score,
            'financial_score': financial_score,
            'stakeholder_score': stakeholder_score,
            'resilience_score': resilience_score,
            'guard_applied': False,
            'commercially_inactive': commercially_inactive,
        })

    _enforce_inactive_revenue_invariant(candidates)

    for item in candidates:
        team = item['team']
        previous_index = item['previous_index']
        new_index = item['new_index']
        composite_score = item['composite_score']
        index_change = (new_index - previous_index).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )

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
            f'market={item["market_score"]:.3f}, '
            f'capability={item["capability_score"]:.3f}, '
            f'financial={item["financial_score"]:.3f}, '
            f'stakeholder={item["stakeholder_score"]:.3f}, '
            f'resilience={item["resilience_score"]:.3f}'
            + ('; commercial-inactivity cap applied'
               if item['commercially_inactive'] else '')
            + ('; zero-revenue ranking guard applied' if item['guard_applied'] else '')
        )
