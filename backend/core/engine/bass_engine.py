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
    RoundResultAdoption, RoundResultAIAdoption,
    RoundResultDemandReconciliation,
)
from core.engine.utils import (InvalidScenarioConfiguration,
                               get_config, high_price_demand_multiplier,
                               scenario_high_price_elasticity,
                               scenario_reference_prices)


def run_bass_adoption(context):
    """
    Engine Steps 8-9: Bass adoption and competitive demand allocation.
    For each customer segment in each market:
    1. Calculate total adoption pool using Bass model
    2. Calculate each team's attractiveness (fit^exponent × readiness)
    3. Include AI competitors
    4. Distribute pool proportionally
    5. Cap by production availability
    6. Record adoption results
    """
    game = context.game
    scenario = context.scenario
    current_round = context.round_number

    competition_sharpness = get_config(
        scenario, 'competition_sharpness', default=1.5,
    )

    # V2-023 rework. Preference fit scores price on a bounded feature that
    # reaches its floor at 1.5x the reference price and clamps there, so above
    # that point price stops reducing demand through fit while revenue keeps
    # multiplying by price -- the original unbounded scaling, surviving above
    # the clamp. This multiplier is an absolute demand response with no floor.
    reference_prices = scenario_reference_prices(scenario)
    high_price_elasticity = scenario_high_price_elasticity(scenario)
    # Keyed with the product's positioning: the elasticity is measured against
    # the same tier reference that price competitiveness is, so a premium
    # product priced at the premium reference is not treated as expensive.
    retail_prices = {
        (team_id, product_id, market_id): (float(price), positioning)
        for team_id, product_id, market_id, price, positioning
        in DecisionMarketing.objects
        .filter(submission__round__game=game,
                submission__round__round_number=current_round)
        # Ordered because the CRV2-01 boundary requires every iterated queryset
        # to declare one. This dict comprehension is order-insensitive in its
        # result, but the rule is deliberately unconditional: an exemption
        # judged case by case is how the last unordered loop got in.
        .order_by('submission__team_id', 'team_product_id', 'market_id', 'pk')
        .values_list('submission__team_id', 'team_product_id', 'market_id',
                     'retail_price', 'team_product__positioning')
    }

    # Initialize production remaining from marketing decisions
    _init_production_remaining(context)

    # Process each segment in each market
    for seg_id, seg_state in context.segments.items():
        segment = seg_state.segment_def
        market = segment.market

        # Non-customer segments: record fit scores only, no Bass adoption
        if segment.segment_type != 'customer':
            _record_non_customer_segment(context, segment, market, current_round)
            continue

        # Skip global segments (no market)
        if market is None:
            continue

        # Bass model parameters
        M = seg_state.effective_population
        p = float(segment.bass_p)
        q = float(segment.bass_q)

        # Get cumulative adoption across ALL teams for this segment+market
        N_prev = _get_total_cumulative(game, segment, market, current_round)

        # Calculate adoption pool
        if M <= 0:
            adoption_pool = 0.0
        else:
            adoption_pool = (p + q * N_prev / max(M, 1)) * max(M - N_prev, 0)
            adoption_pool = max(adoption_pool, 0.0)

        # Calculate each team's attractiveness
        team_attractiveness = {}
        total_attractiveness = 0.0

        # Human teams
        for team in context.teams:
            key = (team.id, segment.id, market.id)
            if (team.id, market.id) in getattr(context, 'compliance_freezes', set()):
                context.adjusted_fit_scores[key] = 0.0
                team_attractiveness[('team', team.id)] = 0.0
                continue

            fit = context.fit_scores.get(key, 0.0)
            # Use adjusted fit if available (post-campaign)
            fit = context.adjusted_fit_scores.get(key, fit)
            product = context.best_products.get(key)

            if fit == 0.0 or product is None:
                team_attractiveness[('team', team.id)] = 0.0
                continue

            # Get readiness
            readiness = context.readiness.get(
                (team.id, product.id, market.id), 1.0,
            )

            raw_attract = (fit ** competition_sharpness) * readiness

            # Acquisition market share bonus: completed acquisitions in this
            # market boost attractiveness (e.g. 0.04 → 1.04× multiplier)
            acq_bonus = _get_acquisition_market_share_bonus(team, market)
            raw_attract *= (1.0 + acq_bonus)

            team_attractiveness[('team', team.id)] = raw_attract
            total_attractiveness += raw_attract

        # AI competitors (CC-20: dynamic fit scores).  Their attractiveness
        # has always diluted human share.  Keep it separate so we can publish
        # the exact take without feeding it into N (Fix A: accounting only).
        ai_allocations = []
        ai_competitors = (AICompetitorDefinition.objects.filter(
            scenario=context.scenario,
        )).order_by('name')
        for ai_comp in ai_competitors:
            ai_fit_score = calculate_ai_competitor_fit(
                ai_comp, segment, market, current_round, context,
            )

            # CC-31A B5: IP exposure boosts aggressive AI competitors
            if getattr(ai_comp, 'strategy_type', '') == 'aggressive' or \
               AICompetitorBehavior.objects.filter(
                   ai_competitor=ai_comp, strategy_type='aggressive',
               ).exists():
                for team in context.teams:
                    presence = TeamMarketPresence.objects.filter(
                        team=team, market=market, status='active',
                    ).first()
                    if presence and float(presence.ip_exposure_cumulative) > 0.10:
                        boost = float(presence.ip_exposure_cumulative) * 0.05
                        ai_fit_score = min(ai_fit_score + boost, 0.95)

            ai_attract = ai_fit_score ** competition_sharpness
            team_attractiveness[('ai', ai_comp.id)] = ai_attract
            total_attractiveness += ai_attract
            ai_allocations.append((ai_comp, ai_fit_score, ai_attract))

        # Distribute adoption pool
        # Sum the same cent-rounded values published in RoundResultAdoption;
        # otherwise independently rounding every team's result can make the
        # aggregate reconciliation differ by a cent.
        human_new_adopters = Decimal('0.00')
        for team in context.teams:
            key = (team.id, segment.id, market.id)
            fit = context.adjusted_fit_scores.get(
                key, context.fit_scores.get(key, 0.0),
            )
            product = context.best_products.get(key)
            frozen = (team.id, market.id) in getattr(context, 'compliance_freezes', set())
            if frozen:
                fit = 0.0
                product = None
                context.best_products[key] = None

            attract = team_attractiveness.get(('team', team.id), 0.0)

            if total_attractiveness == 0:
                team_share = 0.0
            else:
                team_share = attract / total_attractiveness

            team_new_adopters = adoption_pool * team_share

            # Absolute high-price demand response, before the production cap:
            # a team cannot sell what nobody will buy at that price, and the
            # production ceiling is a separate constraint. Applied to the
            # team's own adopters rather than to its share, so that every team
            # raising price together still loses demand.
            price_multiplier = 1.0
            if product:
                entry = retail_prices.get((team.id, product.id, market.id))
                if entry is not None:
                    price, positioning = entry
                    if positioning not in reference_prices:
                        raise InvalidScenarioConfiguration(
                            f'product {product.id} has positioning '
                            f'{positioning!r}, which has no authored reference '
                            f'price; demand cannot be scored for it')
                    price_multiplier = high_price_demand_multiplier(
                        price, reference_prices[positioning],
                        high_price_elasticity)
                    team_new_adopters *= price_multiplier

            # Cap by production availability
            if product:
                prod_key = (team.id, product.id, market.id)
                remaining = context.production_remaining.get(prod_key, 0.0)
                team_new_adopters = min(team_new_adopters, remaining)
                # Deduct from remaining
                context.production_remaining[prod_key] = remaining - team_new_adopters

            # Get previous cumulative for this team
            prev_cumulative = _get_team_cumulative(
                game, team, segment, market, current_round,
            )
            new_cumulative = prev_cumulative + team_new_adopters

            # Get readiness for best product
            readiness_pct = 0.0
            if product:
                readiness_pct = context.readiness.get(
                    (team.id, product.id, market.id), 1.0,
                )
            if frozen:
                readiness_pct = 0.0

            # Store adoption result
            context.adoption[key] = team_new_adopters
            human_new_adopters += Decimal(str(round(team_new_adopters, 2)))

            # Write to database
            RoundResultAdoption.objects.update_or_create(
                game=game,
                round_number=current_round,
                team=team,
                segment=segment,
                market=market,
                defaults={
                    'best_product': product,
                    'fit_score': Decimal(str(round(
                        context.fit_scores.get(key, 0.0), 4,
                    ))),
                    'adjusted_fit_score': Decimal(str(round(fit, 4))),
                    'market_readiness_pct': Decimal(str(round(readiness_pct, 4))),
                    'adoption_pool': Decimal(str(round(adoption_pool, 2))),
                    'team_attractiveness': Decimal(str(round(attract, 4))),
                    'team_share_pct': Decimal(str(round(team_share, 4))),
                    'new_adopters': Decimal(str(round(team_new_adopters, 2))),
                    'cumulative_adopters': Decimal(str(round(new_cumulative, 2))),
                },
            )

        _record_ai_take_and_reconciliation(
            game=game,
            round_number=current_round,
            segment=segment,
            market=market,
            adoption_pool=adoption_pool,
            human_adopters=human_new_adopters,
            total_attractiveness=total_attractiveness,
            ai_allocations=ai_allocations,
        )

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
