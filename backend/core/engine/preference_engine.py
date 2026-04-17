"""
Engine Step 5: Preference Matching (Fit Score Calculation).
From 03-engine-logic.md Section 5.

Core algorithm: For each team × segment × market, calculate how well
the team's offering matches the segment's preferences using Gaussian
decay across all three feature layers.
"""
import math
from decimal import Decimal

from core.models.decisions import DecisionMarketing, DecisionSubmission
from core.models.team_state import (
    TeamMarketPresence, TeamPlatform, TeamPlatformFeatureLevel,
    TeamProduct, TeamProductMarket, TeamStrategyFeatureLevel,
)
from core.models.scenario import (
    SegmentDefinition, SegmentPreference, PlatformFeatureCeiling,
    PlatformGenerationDefinition,
)
from core.models.results import ActiveModifier
from core.models.financials import FinancialExpense
from core.models.cc31_models import TeamMarketCompliance
from core.engine.utils import gaussian_fit, clamp, get_config


def calculate_fit_scores(context):
    """
    Engine Step 5: For each team × segment × market, calculate the
    preference fit score. Uses Gaussian decay on weighted feature
    distances across all three layers (platform, marketing, strategy).
    """
    game = context.game
    scenario = context.scenario
    current_round = context.round_number

    for team in context.teams:
        # Get markets where team has active presence
        presences = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).select_related('market')
        active_market_ids = [p.market_id for p in presences]

        # Get team's submission for marketing decisions
        submission = DecisionSubmission.objects.filter(
            team=team, round__round_number=current_round, round__game=game,
        ).first()

        for market_id, seg_state in context.segments.items():
            segment = seg_state.segment_def
            market = segment.market

            # Skip global segments here (no market) — handled separately
            if market is None:
                _score_global_segment(context, team, segment, seg_state)
                continue

            if market.id not in active_market_ids:
                continue

            # Get team's products in this market
            products = _get_team_products_in_market(team, market)

            # Filter by generation eligibility: only products on platforms
            # that meet the segment's minimum generation requirement qualify.
            # A team having a Gen 2 platform is not enough — they must have
            # a marketed product on that platform.
            if segment.min_generation_required:
                products = [
                    p for p in products
                    if p.team_platform.platform_generation.generation_order
                    >= segment.min_generation_required
                ]
                if not products:
                    context.fit_scores[(team.id, segment.id, market.id)] = 0.0
                    context.best_products[(team.id, segment.id, market.id)] = None
                    continue

            best_fit = 0.0
            best_product = None

            for product in products:
                fit = _calculate_product_segment_fit(
                    context, team, product, segment, market,
                    seg_state, submission, current_round,
                )
                if fit > best_fit:
                    best_fit = fit
                    best_product = product

            # CC-31A B4: Apply origin trust modifier to customer segments
            if segment.segment_type == 'customer' and best_fit > 0:
                best_fit = _apply_origin_trust(team, market, best_fit)

            context.fit_scores[(team.id, segment.id, market.id)] = best_fit
            context.best_products[(team.id, segment.id, market.id)] = best_product

    context.log.append(
        f'Preference matching: {len(context.fit_scores)} '
        f'team-segment-market combinations scored'
    )


def _score_global_segment(context, team, segment, seg_state):
    """Score a global segment (no market). Uses only strategy-layer features."""
    preferences = SegmentPreference.objects.filter(
        segment=segment,
    ).select_related('feature')

    total_weighted_score = 0.0
    total_weight = 0.0

    for pref in preferences:
        feature = pref.feature
        weight = float(pref.weight)
        ideal = float(pref.ideal_value)
        tolerance = float(pref.tolerance)

        # For global segments, use global strategy level
        actual = _get_strategy_value(
            team, feature, None, context.round_number,
        )

        # Apply preference modifiers
        effective_ideal = _apply_pref_modifiers(
            ideal, seg_state, feature, pref,
        )
        effective_ideal = clamp(
            effective_ideal, float(feature.min_value), float(feature.max_value),
        )

        feature_fit = gaussian_fit(actual, effective_ideal, tolerance)
        total_weighted_score += feature_fit * weight
        total_weight += weight

    fit = total_weighted_score / total_weight if total_weight > 0 else 0.0

    # Store with market=None using a sentinel key
    context.fit_scores[(team.id, segment.id, None)] = fit
    context.best_products[(team.id, segment.id, None)] = None


def _calculate_product_segment_fit(
    context, team, product, segment, market,
    seg_state, submission, current_round,
):
    """
    Calculate fit between a product and a segment in a market.
    Central formula from 03-engine-logic.md Section 5.
    """
    preferences = SegmentPreference.objects.filter(
        segment=segment,
    ).select_related('feature')

    total_weighted_score = 0.0
    total_weight = 0.0

    # Get the marketing decision for this product+market.
    # A product without a marketing decision has no pricing, promotion,
    # or production — it cannot compete for adoption.
    mkt_decision = None
    if submission:
        mkt_decision = DecisionMarketing.objects.filter(
            submission=submission,
            team_product=product,
            market=market,
        ).first()

    if not mkt_decision:
        return 0.0

    for pref in preferences:
        feature = pref.feature
        weight = float(pref.weight)
        ideal = float(pref.ideal_value)
        tolerance = float(pref.tolerance)

        # Get the team's actual value for this feature
        if feature.layer == 'platform':
            actual = _get_platform_value(team, product, feature)
        elif feature.layer == 'marketing':
            actual = _get_marketing_feature_value(
                context, team, product, market, feature,
                mkt_decision, segment, current_round,
            )
        elif feature.layer == 'strategy':
            actual = _get_strategy_value(team, feature, market, current_round)
        else:
            actual = float(feature.default_value)

        # Apply active preference modifiers (from events)
        effective_ideal = _apply_pref_modifiers(
            ideal, seg_state, feature, pref,
        )
        effective_ideal = clamp(
            effective_ideal, float(feature.min_value), float(feature.max_value),
        )

        feature_fit = gaussian_fit(actual, effective_ideal, tolerance)
        total_weighted_score += feature_fit * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return total_weighted_score / total_weight


def _apply_pref_modifiers(ideal, seg_state, feature, pref):
    """Apply preference modifiers from events."""
    modifier = seg_state.preference_modifiers.get(feature.id, 0.0)
    return ideal + modifier


def _get_platform_value(team, product, feature):
    """Get the team's platform feature level for a product."""
    try:
        fl = TeamPlatformFeatureLevel.objects.get(
            team_platform=product.team_platform,
            feature=feature,
        )
        return float(fl.current_level)
    except TeamPlatformFeatureLevel.DoesNotExist:
        return float(feature.default_value)


def _get_strategy_value(team, feature, market, current_round):
    """Get the team's strategy feature level."""
    try:
        sl = TeamStrategyFeatureLevel.objects.get(
            team=team, feature=feature, market=market,
            round_number=current_round,
        )
        return float(sl.current_level)
    except TeamStrategyFeatureLevel.DoesNotExist:
        # Try global (market=None)
        if market is not None:
            try:
                sl = TeamStrategyFeatureLevel.objects.get(
                    team=team, feature=feature, market=None,
                    round_number=current_round,
                )
                return float(sl.current_level)
            except TeamStrategyFeatureLevel.DoesNotExist:
                pass
        return float(feature.default_value)


def _get_marketing_feature_value(
    context, team, product, market, feature,
    mkt_decision, segment, current_round,
):
    """
    Derive marketing feature values from decisions.
    Implements all 5 derivation formulas from 03-engine-logic.md Section 5.
    """
    scenario = context.scenario
    f_min = float(feature.min_value)
    f_max = float(feature.max_value)

    if feature.code == 'price_competitiveness':
        return _derive_price_competitiveness(
            context, team, product, market, mkt_decision, f_min, f_max,
        )
    elif feature.code == 'promotion_reach':
        return _derive_promotion_reach(
            context, team, product, market, mkt_decision,
            segment, scenario, f_min, f_max,
        )
    elif feature.code == 'distribution_coverage':
        return _derive_distribution_coverage(
            context, team, product, market, mkt_decision,
            scenario, f_min, f_max,
        )
    elif feature.code == 'brand_awareness':
        return _derive_brand_awareness(
            context, team, product, market, mkt_decision,
            scenario, current_round, f_min, f_max,
        )
    elif feature.code == 'product_availability':
        return _derive_product_availability(
            context, team, product, market, mkt_decision, f_min, f_max,
        )
    else:
        return float(feature.default_value)


def _derive_price_competitiveness(
    context, team, product, market, mkt_decision, f_min, f_max,
):
    """
    price_competitiveness: inverse ratio vs market average price.
    ratio < 1 = cheaper = high competitiveness.
    """
    if not mkt_decision:
        return (f_max + f_min) / 2

    team_price = float(mkt_decision.retail_price)

    # Calculate market average price from all teams' marketing decisions
    all_mkt_decisions = DecisionMarketing.objects.filter(
        submission__round__game=context.game,
        submission__round__round_number=context.round_number,
        market=market,
        team_product__positioning=product.positioning,
    ).exclude(team_product__team=team)

    prices = [float(d.retail_price) for d in all_mkt_decisions]
    prices.append(team_price)
    market_avg_price = sum(prices) / len(prices) if prices else team_price

    if market_avg_price == 0:
        return (f_max + f_min) / 2

    ratio = team_price / market_avg_price
    # ratio of 0.5 → ~max, ratio of 1.0 → ~mid, ratio of 1.5 → ~min
    value = f_max * (1.5 - ratio)
    return clamp(value, f_min, f_max)


def _derive_promotion_reach(
    context, team, product, market, mkt_decision,
    segment, scenario, f_min, f_max,
):
    """
    promotion_reach: spend relative to segment population × benchmark.
    """
    if not mkt_decision:
        return f_min

    spend = float(mkt_decision.promotion_budget)
    benchmark = get_config(scenario, 'promotion_benchmark_per_unit', default=10.0)
    seg_pop = context.segments.get(segment.id)
    population = seg_pop.effective_population if seg_pop else float(segment.population_size)
    expected_spend = population * benchmark
    reach_ratio = spend / max(expected_spend, 1)
    value = reach_ratio * (f_max / 2)
    return clamp(value, f_min, f_max)


def _derive_distribution_coverage(
    context, team, product, market, mkt_decision, scenario, f_min, f_max,
):
    """
    distribution_coverage: base reach from strategy + investment bonus.
    """
    if not mkt_decision:
        return f_min

    base_reach_map = {
        'mass_retail': 0.9,
        'selective_retail': 0.6,
        'exclusive_retail': 0.3,
        'direct_online': 0.5,
        'hybrid': 0.7,
    }
    base_reach = base_reach_map.get(mkt_decision.distribution_strategy, 0.5)
    dist_cap = get_config(scenario, 'distribution_investment_cap', default=5000000.0)
    # Distribution investment = sales reps × cost per rep
    rep_cost = get_config(scenario, 'sales_rep_cost_per_round', default=100000.0)
    effective_investment = float(mkt_decision.sales_team_count) * rep_cost
    investment_bonus = min(
        effective_investment / max(dist_cap, 1), 0.1,
    )
    value = (base_reach + investment_bonus) * f_max
    return clamp(value, f_min, f_max)


def _derive_brand_awareness(
    context, team, product, market, mkt_decision,
    scenario, current_round, f_min, f_max,
):
    """
    brand_awareness: cumulative spend → exponential saturation curve.
    """
    # Sum all historical promotion spend for this platform in this market
    from core.models.decisions import DecisionMarketing as DM

    cumulative_spend = 0.0
    historical = DM.objects.filter(
        submission__team=team,
        submission__round__game=context.game,
        submission__round__round_number__lte=current_round,
        market=market,
        team_product__team_platform=product.team_platform,
    )
    for h in historical:
        cumulative_spend += float(h.promotion_budget)

    halflife = get_config(scenario, 'brand_awareness_halflife', default=10000000.0)
    awareness_curve = 1 - math.exp(-cumulative_spend / max(halflife, 1))
    value = awareness_curve * f_max
    return clamp(value, f_min, f_max)


def _derive_product_availability(
    context, team, product, market, mkt_decision, f_min, f_max,
):
    """
    product_availability: production volume vs demand estimate ratio.
    """
    if not mkt_decision:
        return (f_max + f_min) / 2

    production = float(mkt_decision.production_volume)
    estimated_demand = float(mkt_decision.demand_estimate)

    if estimated_demand == 0:
        return (f_max + f_min) / 2

    availability_ratio = production / estimated_demand
    value = availability_ratio * (f_max / 2)
    return clamp(value, f_min, f_max)


def _team_has_generation(team, min_generation_required):
    """Check if a team has a marketed product on a platform at or above the required generation."""
    from core.models.team_state import TeamProductMarket
    return TeamProductMarket.objects.filter(
        team_product__team=team,
        team_product__status='active',
        is_active=True,
        team_product__team_platform__status='active',
        team_product__team_platform__platform_generation__generation_order__gte=min_generation_required,
    ).exists()


def _get_team_products_in_market(team, market):
    """Get all active products a team offers in a given market."""
    product_ids = TeamProductMarket.objects.filter(
        team_product__team=team,
        market=market,
        is_active=True,
        team_product__status='active',
    ).values_list('team_product_id', flat=True)
    return TeamProduct.objects.filter(id__in=product_ids).select_related('team_platform')


def _apply_origin_trust(team, market, fit_score):
    """
    CC-31A B4: Apply origin trust modifier to a customer fit score.
    Brand preservation shields from trust penalty (at most 8% penalty).
    """
    from decimal import Decimal

    compliance = TeamMarketCompliance.objects.filter(
        game=team.game, team=team, market=market,
    ).first()

    if not compliance:
        return fit_score

    trust_multiplier = float(compliance.current_trust_multiplier)

    # Brand preservation shield
    presence = TeamMarketPresence.objects.filter(
        team=team, market=market, status='active',
    ).first()
    if presence and presence.brand_preserved:
        trust_multiplier = max(trust_multiplier, 0.92)

    return fit_score * trust_multiplier
