"""
Engine Steps 8-9: Bass Adoption & Demand Allocation.
From 03-engine-logic.md Sections 8-9.

The Bass diffusion model drives adoption per segment per market.
Teams compete for a finite adoption pool each round. Higher fit
scores capture more of the pool.
"""
from decimal import Decimal

from core.models.decisions import DecisionMarketing, DecisionSubmission
from core.models.team_state import TeamMarketPresence, TeamProductMarket, TeamAcquisition
from core.models.scenario import AICompetitorFitByRound, AICompetitorDefinition, AICompetitorBehavior
from core.engine.ai_competitors import calculate_ai_competitor_fit
from core.models.results import (
    RoundResultAdoption, RoundResultProductDemand, RoundResultAIAdoption,
    RoundResultDemandReconciliation,
)
from core.engine.utils import (InvalidScenarioConfiguration,
                               get_config, high_price_demand_multiplier,
                               scenario_high_price_elasticity,
                               scenario_reference_prices)


def run_bass_adoption(context):
    """Allocate each customer Bass pool at the product × segment × market grain.

    Like BECSR's current program-grain path, every eligible marketed product
    contributes its own pull and receives its own share.  Firm-level adoption
    rows are a roll-up only; no ``best_product`` may decide capacity, demand,
    revenue, or cumulative Bass adoption.
    """
    game = context.game
    scenario = context.scenario
    current_round = context.round_number
    # Compatibility for narrowly scoped legacy callers that construct a
    # minimal context by hand.  Normal round processing always arrives with
    # product-level scores from ``calculate_fit_scores``.
    if not hasattr(context, 'product_fit_scores'):
        context.product_fit_scores = {}
        context.adjusted_product_fit_scores = {}
        context.products_by_id = {}
        context.product_adoption = {}
    if not context.product_fit_scores:
        for (team_id, segment_id, market_id), fit in context.fit_scores.items():
            product = context.best_products.get((team_id, segment_id, market_id))
            if product is None or market_id is None:
                continue
            product_key = (team_id, product.id, segment_id, market_id)
            context.product_fit_scores[product_key] = fit
            context.adjusted_product_fit_scores[product_key] = (
                context.adjusted_fit_scores.get((team_id, segment_id, market_id), fit))
            context.products_by_id[product.id] = product
    competition_sharpness = get_config(scenario, 'competition_sharpness', default=1.5)
    reference_prices = scenario_reference_prices(scenario)
    high_price_elasticity = scenario_high_price_elasticity(scenario)
    retail_prices = {
        (team_id, product_id, market_id): (float(price), positioning)
        for team_id, product_id, market_id, price, positioning
        in DecisionMarketing.objects.filter(
            submission__round__game=game,
            submission__round__round_number=current_round,
        ).order_by('submission__team_id', 'team_product_id', 'market_id', 'pk')
        .values_list('submission__team_id', 'team_product_id', 'market_id',
                     'retail_price', 'team_product__positioning')
    }
    _init_production_remaining(context)

    for _seg_id, seg_state in sorted(
            context.segments.items(),
            key=lambda item: (
                item[1].segment_def.market.code if item[1].segment_def.market else '',
                item[1].segment_def.name, item[0]),
    ):
        segment = seg_state.segment_def
        market = segment.market
        if segment.segment_type != 'customer':
            _record_non_customer_segment(context, segment, market, current_round)
            continue
        if market is None:
            continue

        M = seg_state.effective_population
        N_prev = _get_total_cumulative(game, segment, market, current_round)
        adoption_pool = 0.0 if M <= 0 else max(
            (float(segment.bass_p) + float(segment.bass_q) * N_prev / max(M, 1))
            * max(M - N_prev, 0), 0.0,
        )

        # Each product's attractiveness participates in one denominator with AI.
        product_attractiveness = {}
        team_attractiveness = {team.id: 0.0 for team in context.teams}
        total_attractiveness = 0.0
        for team in context.teams:
            if (team.id, market.id) in getattr(context, 'compliance_freezes', set()):
                summary_key = (team.id, segment.id, market.id)
                context.adjusted_fit_scores[summary_key] = 0.0
                context.best_products[summary_key] = None
        for product_key, raw_fit in sorted(context.product_fit_scores.items()):
            team_id, product_id, segment_id, market_id = product_key
            if segment_id != segment.id or market_id != market.id:
                continue
            if (team_id, market.id) in getattr(context, 'compliance_freezes', set()):
                context.adjusted_product_fit_scores[product_key] = 0.0
                continue
            product = context.products_by_id[product_id]
            fit = context.adjusted_product_fit_scores.get(product_key, raw_fit)
            entry = retail_prices.get((team_id, product_id, market.id))
            if fit <= 0 or entry is None:
                product_attractiveness[product_key] = 0.0
                continue
            price, positioning = entry
            if positioning not in reference_prices:
                raise InvalidScenarioConfiguration(
                    f'product {product.id} has positioning {positioning!r}, '
                    'which has no authored reference price; demand cannot be scored for it')
            readiness = context.readiness.get((team_id, product_id, market.id), 1.0)
            price_multiplier = high_price_demand_multiplier(
                price, reference_prices[positioning], high_price_elasticity)
            raw_attract = (fit ** competition_sharpness) * readiness * price_multiplier
            team = next(team for team in context.teams if team.id == team_id)
            raw_attract *= 1.0 + _get_acquisition_market_share_bonus(team, market)
            product_attractiveness[product_key] = raw_attract
            team_attractiveness[team_id] += raw_attract
            total_attractiveness += raw_attract

        ai_allocations = []
        ai_competitors = AICompetitorDefinition.objects.filter(
            scenario=context.scenario).order_by('name')
        for ai_comp in ai_competitors:
            ai_fit_score = calculate_ai_competitor_fit(
                ai_comp, segment, market, current_round, context)
            if getattr(ai_comp, 'strategy_type', '') == 'aggressive' or \
               AICompetitorBehavior.objects.filter(
                   ai_competitor=ai_comp, strategy_type='aggressive').exists():
                for team in context.teams:
                    presence = TeamMarketPresence.objects.filter(
                        team=team, market=market, status='active').first()
                    if presence and float(presence.ip_exposure_cumulative) > 0.10:
                        ai_fit_score = min(
                            ai_fit_score + float(presence.ip_exposure_cumulative) * 0.05,
                            0.95)
            ai_attract = ai_fit_score ** competition_sharpness
            total_attractiveness += ai_attract
            ai_allocations.append((ai_comp, ai_fit_score, ai_attract))

        active_product_ids = [key[1] for key in product_attractiveness]
        RoundResultProductDemand.objects.filter(
            game=game, round_number=current_round, segment=segment, market=market,
        ).exclude(team_product_id__in=active_product_ids).delete()

        team_sales = {team.id: Decimal('0.00') for team in context.teams}
        team_shares = {team.id: 0.0 for team in context.teams}
        human_new_adopters = Decimal('0.00')
        for product_key, attract in sorted(product_attractiveness.items()):
            team_id, product_id, _segment_id, _market_id = product_key
            product = context.products_by_id[product_id]
            share = attract / total_attractiveness if total_attractiveness else 0.0
            unconstrained_demand = adoption_pool * share
            production_key = (team_id, product_id, market.id)
            # Persist and deplete at the same cent precision as the product
            # ledger.  A product can serve several segments; independently
            # rounding their float allocations otherwise lets the reported
            # segment rows exceed its reported production by one cent.
            available_production = Decimal(str(round(
                context.production_remaining.get(production_key, 0.0), 2)))
            reported_demand = Decimal(str(round(unconstrained_demand, 2)))
            reported_sold = min(reported_demand, available_production)
            reported_lost_demand = reported_demand - reported_sold
            context.production_remaining[production_key] = float(
                available_production - reported_sold)
            context.product_adoption[product_key] = reported_sold
            team_sales[team_id] += reported_sold
            team_shares[team_id] += share
            human_new_adopters += reported_sold
            raw_fit = context.product_fit_scores[product_key]
            adjusted_fit = context.adjusted_product_fit_scores.get(product_key, raw_fit)
            readiness = context.readiness.get((team_id, product_id, market.id), 1.0)
            RoundResultProductDemand.objects.update_or_create(
                game=game, round_number=current_round, team_id=team_id,
                team_product_id=product_id, segment=segment, market=market,
                defaults={
                    'fit_score': Decimal(str(round(raw_fit, 4))),
                    'adjusted_fit_score': Decimal(str(round(adjusted_fit, 4))),
                    'market_readiness_pct': Decimal(str(round(readiness, 4))),
                    'attractiveness': Decimal(str(round(attract, 4))),
                    'share_pct': Decimal(str(round(share, 6))),
                    'unconstrained_demand': reported_demand,
                    'available_production': available_production,
                    'units_sold': reported_sold,
                    'lost_demand': reported_lost_demand,
                },
            )

        for team in context.teams:
            key = (team.id, segment.id, market.id)
            frozen = (team.id, market.id) in getattr(context, 'compliance_freezes', set())
            product = None if frozen else context.best_products.get(key)
            raw_fit = context.fit_scores.get(key, 0.0)
            adjusted_fit = context.adjusted_fit_scores.get(key, raw_fit)
            readiness = (context.readiness.get((team.id, product.id, market.id), 1.0)
                         if product else 0.0)
            sold = team_sales[team.id]
            context.adoption[key] = float(sold)
            previous = _get_team_cumulative(game, team, segment, market, current_round)
            RoundResultAdoption.objects.update_or_create(
                game=game, round_number=current_round, team=team,
                segment=segment, market=market,
                defaults={
                    'best_product': product,
                    'fit_score': Decimal(str(round(raw_fit, 4))),
                    'adjusted_fit_score': Decimal(str(round(adjusted_fit, 4))),
                    'market_readiness_pct': Decimal(str(round(readiness, 4))),
                    'adoption_pool': Decimal(str(round(adoption_pool, 2))),
                    'team_attractiveness': Decimal(str(round(team_attractiveness[team.id], 4))),
                    'team_share_pct': Decimal(str(round(team_shares[team.id], 4))),
                    'new_adopters': sold,
                    'cumulative_adopters': Decimal(str(round(previous, 2))) + sold,
                },
            )

        _record_ai_take_and_reconciliation(
            game=game, round_number=current_round, segment=segment, market=market,
            adoption_pool=adoption_pool, human_adopters=human_new_adopters,
            total_attractiveness=total_attractiveness, ai_allocations=ai_allocations)

    _log_adoption_summary(context)


def _record_non_customer_segment(context, segment, market, current_round):
    """
    Write RoundResultAdoption for non-customer segments (investor,
    regulator, etc.) with adoption fields zeroed but fit scores populated.
    """
    game = context.game
    for team in context.teams:
        if market:
            key = (team.id, segment.id, market.id)
        else:
            key = (team.id, segment.id, None)

        fit = context.fit_scores.get(key, 0.0)
        adjusted = context.adjusted_fit_scores.get(key, fit)

        if market is None:
            # Global segment (e.g. investors) — use filter + update_or_create
            # since unique_together with NULL market needs explicit handling
            existing = RoundResultAdoption.objects.filter(
                game=game, round_number=current_round,
                team=team, segment=segment, market__isnull=True,
            ).first()
            if existing:
                existing.fit_score = Decimal(str(round(fit, 4)))
                existing.adjusted_fit_score = Decimal(str(round(adjusted, 4)))
                existing.save(update_fields=['fit_score', 'adjusted_fit_score'])
            else:
                RoundResultAdoption.objects.create(
                    game=game, round_number=current_round,
                    team=team, segment=segment, market=None,
                    best_product=None,
                    fit_score=Decimal(str(round(fit, 4))),
                    adjusted_fit_score=Decimal(str(round(adjusted, 4))),
                    market_readiness_pct=Decimal('1.0000'),
                    adoption_pool=Decimal('0.00'),
                    team_attractiveness=Decimal('0.0000'),
                    team_share_pct=Decimal('0.0000'),
                    new_adopters=Decimal('0.00'),
                    cumulative_adopters=Decimal('0.00'),
                )
            continue

        RoundResultAdoption.objects.update_or_create(
            game=game,
            round_number=current_round,
            team=team,
            segment=segment,
            market=market,
            defaults={
                'best_product': None,
                'fit_score': Decimal(str(round(fit, 4))),
                'adjusted_fit_score': Decimal(str(round(adjusted, 4))),
                'market_readiness_pct': Decimal('1.0000'),
                'adoption_pool': Decimal('0.00'),
                'team_attractiveness': Decimal('0.0000'),
                'team_share_pct': Decimal('0.0000'),
                'new_adopters': Decimal('0.00'),
                'cumulative_adopters': Decimal('0.00'),
            },
        )


def _init_production_remaining(context):
    """Initialize production remaining from DecisionMarketing.production_volume."""
    game = context.game
    current_round = context.round_number

    for team in context.teams:
        submission = DecisionSubmission.objects.filter(
            team=team, round__round_number=current_round, round__game=game,
        ).first()
        if not submission:
            continue

        mkt_decisions = (DecisionMarketing.objects.filter(
            submission=submission,
        )).order_by('team_product__name', 'market__code')
        for md in mkt_decisions:
            key = (team.id, md.team_product_id, md.market_id)
            existing = context.production_remaining.get(key, 0.0)
            context.production_remaining[key] = existing + float(md.production_volume)


def _get_total_cumulative(game, segment, market, current_round):
    """Get total cumulative adopters across all teams for a segment+market."""
    prev_round = current_round - 1
    if prev_round < 1:
        return 0.0

    from django.db.models import Sum
    result = RoundResultAdoption.objects.filter(
        game=game,
        segment=segment,
        market=market,
        round_number=prev_round,
    ).aggregate(total=Sum('cumulative_adopters'))
    return float(result['total'] or 0)


def _get_team_cumulative(game, team, segment, market, current_round):
    """Get a single team's cumulative adopters for a segment+market."""
    prev_round = current_round - 1
    if prev_round < 1:
        return 0.0

    try:
        prev = RoundResultAdoption.objects.get(
            game=game,
            team=team,
            segment=segment,
            market=market,
            round_number=prev_round,
        )
        return float(prev.cumulative_adopters)
    except RoundResultAdoption.DoesNotExist:
        return 0.0


def _get_acquisition_market_share_bonus(team, market):
    """Sum market_share_gained from completed acquisitions in this market."""
    completed = (TeamAcquisition.objects.filter(
        team=team,
        acquisition_target__market=market,
        integration_complete=True,
    ).select_related('acquisition_target')).order_by('acquisition_target__target_name')
    return sum(float(a.acquisition_target.market_share_gained or 0) for a in completed)


def _record_ai_take_and_reconciliation(*, game, round_number, segment, market,
                                       adoption_pool, human_adopters,
                                       total_attractiveness, ai_allocations):
    """Persist an auditable accounting identity for one Bass pool.

    This is deliberately after human allocation.  A price multiplier or a
    production ceiling may make part of a human team's theoretical share
    unserved, but it must never be silently reassigned to the AI.  Thus Fix A
    records the take the existing denominator already gave AI competitors and
    leaves both human outcomes and diffusion dynamics unchanged.
    """
    reported_pool = Decimal(str(round(adoption_pool, 2)))
    reported_human = Decimal(str(human_adopters))
    reported_ai = Decimal('0.00')
    ai_ids = []
    ai_rows = []

    for ai_comp, ai_fit_score, ai_attract in ai_allocations:
        share = ai_attract / total_attractiveness if total_attractiveness else 0.0
        take = adoption_pool * share
        reported_take = Decimal(str(round(take, 2)))
        reported_ai += reported_take
        ai_ids.append(ai_comp.id)
        ai_rows.append((ai_comp, ai_fit_score, ai_attract, share, reported_take))

    stale_ai = RoundResultAIAdoption.objects.filter(
        game=game, round_number=round_number, segment=segment, market=market,
    )
    if ai_ids:
        stale_ai = stale_ai.exclude(ai_competitor_id__in=ai_ids)
    stale_ai.delete()

    # Humans cannot exceed their pool before cent rounding.  If they do after
    # it, the allocation logic is wrong rather than something an accounting
    # row may hide.  AI rows are a separate proportional allocation, so their
    # independently rounded sum may be one cent above the remaining pool.  Put
    # that deterministic rounding residue on the final AI row; no team result
    # or diffusion input changes, and the published rows remain additive.
    if reported_human > reported_pool:
        raise RuntimeError(
            'Human demand allocation exceeded its Bass pool for '
            f'segment={segment.id}, market={market.id}, round={round_number}: '
            f'pool={reported_pool}, human={reported_human}'
        )
    available_for_ai = reported_pool - reported_human
    if reported_ai > available_for_ai:
        correction = reported_ai - available_for_ai
        ai_comp, fit, attract, share, take = ai_rows[-1]
        ai_rows[-1] = (ai_comp, fit, attract, share, take - correction)
        reported_ai = available_for_ai

    for ai_comp, ai_fit_score, ai_attract, share, reported_take in ai_rows:
        RoundResultAIAdoption.objects.update_or_create(
            game=game,
            round_number=round_number,
            ai_competitor=ai_comp,
            segment=segment,
            market=market,
            defaults={
                'fit_score': Decimal(str(round(ai_fit_score, 4))),
                'attractiveness': Decimal(str(round(ai_attract, 4))),
                'share_pct': Decimal(str(round(share, 6))),
                'new_adopters': reported_take,
            },
        )

    # The final cent remainder is intentionally put in unserved demand so
    # persisted rows reconcile exactly even when independent allocations
    # straddle a cent.
    unserved = max(reported_pool - reported_human - reported_ai, Decimal('0.00'))
    if reported_human + reported_ai + unserved != reported_pool:
        raise RuntimeError(
            'Demand reconciliation did not close for '
            f'segment={segment.id}, market={market.id}, round={round_number}'
        )
    RoundResultDemandReconciliation.objects.update_or_create(
        game=game,
        round_number=round_number,
        segment=segment,
        market=market,
        defaults={
            'adoption_pool': reported_pool,
            'human_adopters': reported_human,
            'ai_adopters': reported_ai,
            'unserved_adopters': unserved,
        },
    )


def _log_adoption_summary(context):
    """Add adoption summary to context log."""
    total_adopters = sum(context.adoption.values())
    context.log.append(
        f'Bass adoption: {len(context.adoption)} allocations, '
        f'{total_adopters:,.0f} total new adopters'
    )
