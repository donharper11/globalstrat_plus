"""
Engine Steps 1-2: Event firing and market condition updates.
From 03-engine-logic.md Sections 1-2.
CC-7 additions: narrative generation, event response processing.
"""
import random
from decimal import Decimal

from core.models.scenario import (
    EventTemplateDefinition, EventImpactDefinition,
    EventResponseDefinition, FeatureDefinition,
    MarketDefinition, MarketConditionByRound, SegmentDefinition,
)
from core.models.decisions import DecisionSubmission, DecisionEventResponse
from core.models.results import EventInstance, ActiveModifier
from core.models.cc31_models import TeamMarketCompliance
from core.models.team_state import TeamPartnership
from core.engine.utils import MarketEffectiveState, SegmentEffectiveState, clamp
from core.engine.event_conditions import evaluate_all_conditions
from core.engine.llm_runner import build_language_instruction
from core.utils.localization import get_instructor_language


def fire_events(context):
    """
    Engine Step 1: Fire random events based on probability and eligibility.
    Creates EventInstance and ActiveModifier records.
    """
    game = context.game
    scenario = context.scenario
    current_round = context.round_number

    # Expire modifiers from previous rounds
    expired = ActiveModifier.objects.filter(
        game=game, expires_round=current_round,
    ).delete()

    templates = EventTemplateDefinition.objects.filter(scenario=scenario)
    all_markets = list(MarketDefinition.objects.filter(scenario=scenario))

    for template in templates:
        # Check eligibility
        if template.earliest_round > current_round:
            continue
        if template.latest_round and template.latest_round < current_round:
            continue

        # Check max occurrences
        previous_count = EventInstance.objects.filter(
            game=game, event_template=template,
        ).count()
        if previous_count >= template.max_occurrences:
            continue

        # Roll against probability
        base_prob = float(template.probability_per_round)

        # CC-31A B8: For regulatory/geopolitical events, use per-team probability
        event_category = getattr(template, 'category', '') or ''
        if event_category.upper() in ('REGULATORY', 'GEOPOLITICAL', 'SANCTIONS'):
            _fire_compliance_adjusted_event(
                context, template, all_markets, current_round, base_prob,
            )
            continue

        roll = random.random()
        if roll > base_prob:
            continue

        # Fire the event — determine target market first for narrative
        if template.affected_markets:
            affected_codes = set(template.affected_markets)
            target_markets = [m for m in all_markets if m.code in affected_codes]
        elif template.affects_all_markets:
            target_markets = all_markets
        elif template.target_market:
            target_markets = [template.target_market]
        else:
            target_markets = [random.choice(all_markets)] if all_markets else []

        primary_target = target_markets[0] if target_markets and not template.affects_all_markets else None

        # Generate narrative with resolved placeholders
        base_narrative = generate_event_narrative(
            template, primary_target, current_round, scenario,
        )
        # Append context enrichment
        impacts = list(template.impacts.all())
        context_text = generate_event_context(template, impacts)

        # RAG enhancement (CC-11) — deferred to Phase 2 when skip_rag is set
        skip_rag = getattr(context, 'skip_rag', False)
        rag_text = _rag_enhance_event(template, primary_target, base_narrative, scenario, game=game, skip_rag=skip_rag)

        parts = [base_narrative, context_text, rag_text]
        narrative = "\n\n".join(p for p in parts if p)

        event_instance = EventInstance.objects.create(
            game=game,
            event_template=template,
            round_number=current_round,
            narrative=narrative,
        )

        # Set target_market on event instance (first market if specific)
        if target_markets and not template.affects_all_markets:
            event_instance.target_market = target_markets[0]
            event_instance.save()

        # Apply each impact definition
        for impact in template.impacts.all():
            for market in target_markets:
                _apply_event_impact(
                    game, event_instance, impact, market, current_round,
                )

        # CC-24: Record ESG event protection/vulnerability for each team
        _record_esg_event_interactions(context, event_instance, target_markets)

        context.events_fired.append(event_instance)
        context.log.append(
            f'Event fired: "{template.name}" → '
            f'{", ".join(m.name for m in target_markets)} '
            f'(severity: {template.severity})'
        )


def _apply_event_impact(game, event_instance, impact, market, current_round):
    """Create ActiveModifier records from an EventImpactDefinition."""
    expires = None
    if impact.duration_rounds and impact.duration_rounds > 0:
        expires = current_round + impact.duration_rounds

    if impact.impact_type == 'preference_shift':
        ActiveModifier.objects.create(
            game=game,
            modifier_type='preference',
            source_event=event_instance,
            target_segment=impact.target_segment,
            target_feature=impact.target_feature,
            target_market=market,
            modifier_value=impact.impact_value,
            started_round=current_round,
            expires_round=expires,
            is_cumulative=impact.is_cumulative,
        )

    elif impact.impact_type == 'market_condition':
        ActiveModifier.objects.create(
            game=game,
            modifier_type='market_condition',
            source_event=event_instance,
            target_market=market,
            target_field=impact.target_field,
            modifier_value=impact.impact_value,
            started_round=current_round,
            expires_round=expires,
            is_cumulative=impact.is_cumulative,
        )

    elif impact.impact_type == 'demand_shock':
        ActiveModifier.objects.create(
            game=game,
            modifier_type='demand_shock',
            source_event=event_instance,
            target_segment=impact.target_segment,
            target_market=market,
            modifier_value=impact.impact_value,
            started_round=current_round,
            expires_round=expires,
            is_cumulative=impact.is_cumulative,
        )

    elif impact.impact_type == 'cost_change':
        ActiveModifier.objects.create(
            game=game,
            modifier_type='cost',
            source_event=event_instance,
            target_market=market,
            target_field=impact.target_field,
            modifier_value=impact.impact_value,
            started_round=current_round,
            expires_round=expires,
            is_cumulative=impact.is_cumulative,
        )

    elif impact.impact_type == 'exchange_rate':
        # Exchange rate shifts are stored as market_condition modifiers
        ActiveModifier.objects.create(
            game=game,
            modifier_type='market_condition',
            source_event=event_instance,
            target_market=market,
            target_field='exchange_rate',
            modifier_value=impact.impact_value,
            started_round=current_round,
            expires_round=expires,
            is_cumulative=impact.is_cumulative,
        )


def _fire_compliance_adjusted_event(context, template, all_markets, current_round, base_prob):
    """
    CC-31A B8: Per-team compliance-adjusted event firing for regulatory/geopolitical events.
    Each team has an independent probability based on their compliance level.
    """
    game = context.game

    # Determine target markets
    if template.affected_markets:
        # CC-31E: explicit market list takes precedence
        affected_codes = set(template.affected_markets)
        target_markets = [m for m in all_markets if m.code in affected_codes]
    elif template.affects_all_markets:
        target_markets = all_markets
    elif template.target_market:
        target_markets = [template.target_market]
    else:
        target_markets = [random.choice(all_markets)] if all_markets else []

    if not target_markets:
        return

    teams_affected = []

    for team in context.teams:
        # Calculate compliance mitigation across target markets
        max_mitigation = Decimal('0')
        for market in target_markets:
            compliance = TeamMarketCompliance.objects.filter(
                game=game, team=team, market=market,
            ).first()

            if compliance:
                mitigation = compliance.compliance_level * Decimal('0.4')
            else:
                mitigation = Decimal('0')

            # Local strategic partner further reduces
            has_local_strategic = TeamPartnership.objects.filter(
                team=team, market=market, status='active',
                strategy_option__code='LOCAL_STRATEGIC',
            ).exists()
            if has_local_strategic:
                mitigation += Decimal('0.15')

            max_mitigation = max(max_mitigation, mitigation)

        # CC-31E: For TEAM_SPECIFIC events, check trigger conditions
        if template.target_type == 'TEAM_SPECIFIC':
            # Check if team has presence in ANY target market
            from core.models.team_state import TeamMarketPresence
            has_presence = any(
                TeamMarketPresence.objects.filter(
                    team=team, market=market, status='active',
                ).exists()
                for market in target_markets
            )
            if not has_presence:
                continue

            # Check trigger conditions against first target market (or team's most relevant market)
            eval_market = target_markets[0] if target_markets else None
            if eval_market and not evaluate_all_conditions(
                template.trigger_condition, team, game, eval_market,
            ):
                continue

        adjusted_prob = base_prob * float(1 - min(Decimal('0.50'), max_mitigation))

        if random.random() < adjusted_prob:
            teams_affected.append(team)

    if not teams_affected:
        return

    # Create event instance (fires once, affects specific teams)
    primary_target = target_markets[0] if target_markets and not template.affects_all_markets else None

    base_narrative = generate_event_narrative(template, primary_target, current_round, context.scenario)
    impacts = list(template.impacts.all())
    context_text = generate_event_context(template, impacts)
    skip_rag = getattr(context, 'skip_rag', False)
    rag_text = _rag_enhance_event(template, primary_target, base_narrative, context.scenario, game=game, skip_rag=skip_rag)

    parts = [base_narrative, context_text, rag_text]
    narrative = "\n\n".join(p for p in parts if p)

    event_instance = EventInstance.objects.create(
        game=game,
        event_template=template,
        round_number=current_round,
        narrative=narrative,
    )

    if target_markets and not template.affects_all_markets:
        event_instance.target_market = target_markets[0]
        event_instance.save()

    # Apply impacts only for affected teams' markets
    for impact in template.impacts.all():
        for market in target_markets:
            _apply_event_impact(game, event_instance, impact, market, current_round)

    _record_esg_event_interactions(context, event_instance, target_markets)

    context.events_fired.append(event_instance)
    affected_names = ', '.join(t.name for t in teams_affected)
    context.log.append(
        f'Event fired (compliance-adjusted): "{template.name}" → '
        f'{", ".join(m.name for m in target_markets)} '
        f'(affected: {affected_names})'
    )


def update_market_conditions(context):
    """
    Engine Step 2: Update effective market conditions for this round.
    Applies pre-scripted MarketConditionByRound + active event modifiers.
    Grows segment populations.
    """
    game = context.game
    scenario = context.scenario
    current_round = context.round_number

    all_markets = MarketDefinition.objects.filter(scenario=scenario)

    for market in all_markets:
        state = MarketEffectiveState(market)

        # Apply pre-scripted round conditions
        try:
            rc = MarketConditionByRound.objects.get(
                market=market, round_number=current_round,
            )
            state.effective_growth_rate = float(market.base_growth_rate) + float(rc.growth_rate_modifier)
            state.effective_exchange_rate = float(market.exchange_rate_base) * (1 + float(rc.exchange_rate_modifier))
            state.effective_tariff_rate = float(market.tariff_rate) + float(rc.tariff_rate_modifier)
            state.demand_multiplier = float(rc.demand_multiplier)
        except MarketConditionByRound.DoesNotExist:
            pass

        # Layer on active event-driven modifiers
        mkt_modifiers = ActiveModifier.objects.filter(
            game=game,
            modifier_type='market_condition',
            target_market=market,
        ).filter(
            # Active: started <= current AND (expires is NULL or expires > current)
            started_round__lte=current_round,
        ).exclude(expires_round__lte=current_round)

        for mod in mkt_modifiers:
            if mod.target_field == 'growth_rate':
                state.effective_growth_rate += float(mod.modifier_value)
            elif mod.target_field == 'exchange_rate':
                state.effective_exchange_rate *= (1 + float(mod.modifier_value))
            elif mod.target_field == 'tariff_rate':
                state.effective_tariff_rate += float(mod.modifier_value)
            elif mod.target_field == 'demand_multiplier':
                state.demand_multiplier *= float(mod.modifier_value)

        # Clamp exchange rate
        state.effective_exchange_rate = max(state.effective_exchange_rate, 0.01)

        context.markets[market.id] = state

        # Grow segment populations
        segments = SegmentDefinition.objects.filter(
            scenario=scenario, market=market,
        )
        for segment in segments:
            seg_state = SegmentEffectiveState(segment)
            base_pop = float(segment.population_size)
            growth = base_pop * state.effective_growth_rate
            seg_state.effective_population = (base_pop + growth) * state.demand_multiplier

            # Apply demand shock modifiers
            shocks = ActiveModifier.objects.filter(
                game=game,
                modifier_type='demand_shock',
                target_market=market,
                started_round__lte=current_round,
            ).exclude(expires_round__lte=current_round).filter(
                # Match segment or no segment (affects all)
            )
            for shock in shocks:
                if shock.target_segment is None or shock.target_segment_id == segment.id:
                    seg_state.effective_population *= float(shock.modifier_value)

            seg_state.effective_population = max(seg_state.effective_population, 0)

            # Load preference modifiers
            pref_mods = ActiveModifier.objects.filter(
                game=game,
                modifier_type='preference',
                started_round__lte=current_round,
            ).exclude(expires_round__lte=current_round).filter(
                # Match this segment or all segments
            )
            for pm in pref_mods:
                if pm.target_segment is None or pm.target_segment_id == segment.id:
                    if pm.target_feature_id:
                        feat_id = pm.target_feature_id
                        existing = seg_state.preference_modifiers.get(feat_id, 0.0)
                        seg_state.preference_modifiers[feat_id] = existing + float(pm.modifier_value)

            context.segments[segment.id] = seg_state

    # Also handle segments without a specific market (global segments)
    global_segments = SegmentDefinition.objects.filter(
        scenario=scenario, market__isnull=True,
    )
    for segment in global_segments:
        seg_state = SegmentEffectiveState(segment)
        seg_state.effective_population = float(segment.population_size)
        context.segments[segment.id] = seg_state


# ---------------------------------------------------------------------------
# CC-7: Event narrative generation
# ---------------------------------------------------------------------------

def generate_event_narrative(template, target_market, round_number, scenario):
    """
    Resolve placeholders in description_template:
    - {market} → target market name
    - {value} → contextually appropriate value (tariff %, currency %, etc.)
    - {round} → current round number
    """
    narrative = template.description_template

    # Market name
    market_name = target_market.name if target_market else "global markets"
    narrative = narrative.replace('{market}', market_name)

    # Value — derive from the most significant impact
    primary_impact = template.impacts.order_by('-impact_value').first()
    if primary_impact:
        if primary_impact.impact_type == 'cost_change' and 'tariff' in (primary_impact.target_field or ''):
            value = f"{abs(float(primary_impact.impact_value) * 100):.0f}"
        elif primary_impact.impact_type == 'exchange_rate':
            value = f"{abs(float(primary_impact.impact_value) * 100):.0f}"
        elif primary_impact.impact_type == 'demand_shock':
            value = f"{abs((float(primary_impact.impact_value) - 1) * 100):.0f}"
        else:
            value = f"{abs(float(primary_impact.impact_value)):.1f}"
    else:
        value = "significant"
    narrative = narrative.replace('{value}', value)

    narrative = narrative.replace('{round}', str(round_number))

    return narrative


def generate_event_context(template, impacts):
    """
    Generate 2-3 sentences of strategic context for the event.
    Rule-based for now — CC-11 replaces with RAG-grounded analysis.
    """
    context_parts = []

    for impact in impacts:
        if impact.impact_type == 'preference_shift':
            segment = impact.target_segment
            feature = impact.target_feature
            direction = "increased" if impact.impact_value > 0 else "decreased"
            if segment:
                context_parts.append(
                    f"{segment.name} have {direction} their expectations "
                    f"for {feature.name if feature else 'overall quality'}."
                )
            else:
                context_parts.append(
                    f"Market expectations for {feature.name if feature else 'key capabilities'} "
                    f"have {direction} across all segments."
                )

        elif impact.impact_type == 'cost_change':
            direction = "increased" if impact.impact_value > 0 else "decreased"
            context_parts.append(
                f"Operating costs have {direction}. "
                f"Firms with local operations may be better positioned to absorb the impact."
            )

        elif impact.impact_type == 'demand_shock':
            if impact.impact_value > 1:
                context_parts.append(
                    "Market demand is surging. Firms with sufficient production "
                    "capacity stand to benefit."
                )
            else:
                context_parts.append(
                    "Market demand has contracted. Firms may need to adjust "
                    "production volumes to avoid excess inventory."
                )

        elif impact.impact_type == 'exchange_rate':
            if impact.impact_value < 0:
                context_parts.append(
                    "Currency devaluation increases import costs but may benefit "
                    "exporters with local-currency revenue."
                )
            else:
                context_parts.append(
                    "Currency strengthening benefits importers but may hurt "
                    "local pricing competitiveness."
                )

    return " ".join(context_parts[:3])  # Max 3 sentences


# ---------------------------------------------------------------------------
# CC-11: RAG event narrative enhancement
# ---------------------------------------------------------------------------

def _rag_enhance_event(template, target_market, base_narrative, scenario,
                       game=None, skip_rag=False):
    """
    If the event has rag_source_tags and RAG is enabled, add a sentence
    of strategic context grounded in the article corpus.

    CC-32H: skip_rag=True defers RAG enhancement to Phase 2.
    """
    if skip_rag:
        return ""

    import time
    from core.engine.utils import get_config

    rag_enabled = get_config(scenario, 'rag_enabled', False, bool)
    if not rag_enabled or not template.rag_source_tags:
        return ""

    try:
        from core.rag.embeddings import get_embedding
        from core.rag.client import search_articles
        from django.conf import settings

        if not settings.DASHSCOPE_API_KEY:
            return ""

        tags = [t.strip() for t in template.rag_source_tags.split(',')]
        market_name = target_market.name if target_market else 'global'
        query = f"{template.name} {market_name}"
        embedding = get_embedding(query)
        results = search_articles(embedding, tags=tags, limit=2)

        if not results:
            return ""

        import dashscope
        from dashscope import Generation
        dashscope.api_key = settings.DASHSCOPE_API_KEY

        research_text = '\n'.join([r['text'][:300] for r in results])

        # Event narratives are game-wide; use instructor language
        language = get_instructor_language(game) if game else 'en'
        lang_instruction = build_language_instruction(language)

        time.sleep(0.5)  # Rate limit
        response = Generation.call(
            model=settings.DASHSCOPE_MODEL,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        "You are a business news analyst. Add one sentence of "
                        "historical or strategic context to an event brief, "
                        "grounded in the research provided. Do not cite sources. "
                        "Write as: 'Historically,...' or 'Industry analysts note...'"
                    ),
                },
                {
                    'role': 'user',
                    'content': (
                        f"Event: {base_narrative}\n\nResearch:\n{research_text}"
                        + lang_instruction
                    ),
                },
            ],
            max_tokens=80,
            temperature=0.3,
        )

        return response.output.text

    except Exception:
        return ""


# ---------------------------------------------------------------------------
# CC-7: Event response processing
# ---------------------------------------------------------------------------

def process_event_responses(context):
    """
    Called after events fire but before preference matching.
    For each event that required a response, process team responses.
    Apply response effects to the responding team's state.
    """
    from core.models.core import Team

    for event_instance in context.events_fired:
        template = event_instance.event_template
        if not template.response_required:
            continue

        for team in context.teams:
            submission = _get_locked_submission(team, context)
            if not submission:
                continue

            response_decision = DecisionEventResponse.objects.filter(
                submission=submission,
                event_instance=event_instance,
            ).first()

            if response_decision:
                # Team responded — apply response effects
                response_def = response_decision.response
                _apply_response_effects(context, team, response_def, event_instance)
                context.log.append(
                    f'Event response: {team.name} chose "{response_def.name}" '
                    f'for "{template.name}"'
                )
            else:
                # Team did not respond — apply default penalty
                _apply_no_response_penalty(context, team, template, event_instance)
                context.log.append(
                    f'Event no-response penalty: {team.name} did not respond '
                    f'to "{template.name}"'
                )


def _get_locked_submission(team, context):
    """Get the locked DecisionSubmission for a team in the current round."""
    from core.models.core import Round
    try:
        rnd = Round.objects.get(
            game=context.game, round_number=context.round_number,
        )
    except Round.DoesNotExist:
        return None
    return DecisionSubmission.objects.filter(
        team=team, round=rnd, status='locked',
    ).first()


def _apply_response_effects(context, team, response_def, event_instance):
    """Apply the effects defined in EventResponseDefinition.effects JSON."""
    if not response_def.effects:
        return

    for effect in response_def.effects:
        feature_id = effect.get('feature_id')
        effect_type = effect.get('effect_type', 'add')
        effect_value = effect.get('effect_value', 0)
        market_specific = effect.get('market_specific', True)

        if feature_id:
            target_market = event_instance.target_market if market_specific else None
            _apply_strategy_effect_direct(
                context, team, feature_id, effect_type, effect_value, target_market,
            )

    # Deduct response cost from team cash
    if response_def.cost > 0:
        team.cash_on_hand -= response_def.cost
        team.save()


def _apply_strategy_effect_direct(context, team, feature_id, effect_type, effect_value, target_market):
    """Apply a direct strategy feature effect (from event response)."""
    from core.models.scenario import FeatureDefinition
    from core.models.team_state import TeamStrategyFeatureLevel

    try:
        feature = FeatureDefinition.objects.get(id=feature_id)
    except FeatureDefinition.DoesNotExist:
        return

    if feature.layer != 'strategy':
        return

    markets = [target_market] if target_market else list(
        MarketDefinition.objects.filter(scenario=context.scenario)
    )

    for market in markets:
        try:
            level = TeamStrategyFeatureLevel.objects.get(
                team=team, feature=feature, market=market,
                round_number=context.round_number,
            )
        except TeamStrategyFeatureLevel.DoesNotExist:
            level = TeamStrategyFeatureLevel.objects.create(
                team=team, feature=feature, market=market,
                current_level=feature.default_value,
                round_number=context.round_number,
            )

        current = float(level.current_level)

        if effect_type == 'set':
            new_val = float(effect_value)
        elif effect_type == 'add':
            new_val = current + float(effect_value)
        elif effect_type == 'multiply':
            new_val = current * float(effect_value)
        else:
            continue

        new_val = clamp(new_val, float(feature.min_value), float(feature.max_value))
        level.current_level = Decimal(str(round(new_val, 2)))
        level.save()


def _apply_no_response_penalty(context, team, template, event_instance):
    """
    Teams that don't respond to required events suffer a default penalty.
    Penalty: -1.0 to regulatory_govt feature in the affected market.
    """
    regulatory_feature = FeatureDefinition.objects.filter(
        scenario=context.scenario,
        code='regulatory_govt',
    ).first()

    if regulatory_feature:
        _apply_strategy_effect_direct(
            context, team, regulatory_feature.id, 'add', -1.0,
            event_instance.target_market,
        )


# ---------------------------------------------------------------------------
# CC-24: ESG event protection recording
# ---------------------------------------------------------------------------

def _record_esg_event_interactions(context, event_instance, target_markets):
    """
    Record ESG-based event protection/vulnerability for each team.
    Stored in ESGEconomicImpact for visibility on the Strategic Impact report.
    """
    from core.engine.strategic_economics import calculate_event_esg_modifier
    from core.models.cc24_models import ESGEconomicImpact

    template = event_instance.event_template

    for team in context.teams:
        multiplier, reason = calculate_event_esg_modifier(
            team, event_instance, context,
        )
        if multiplier == 1.0:
            continue  # No ESG effect on this event

        # Estimate dollar impact of protection/amplification
        # Use the event's primary impact value as a proxy
        primary_impact = template.impacts.first()
        if not primary_impact:
            continue

        for market in target_markets:
            # Rough estimate: impact_value as % of team revenue in this market
            from core.models.results_financials import RoundResultFinancials
            prev_fin = RoundResultFinancials.objects.filter(
                game=context.game, team=team,
                round_number=context.round_number - 1,
            ).first()
            prev_revenue = float(prev_fin.total_revenue) if prev_fin else 0

            # Impact magnitude estimate
            impact_magnitude = abs(float(primary_impact.impact_value))
            estimated_base_impact = prev_revenue * impact_magnitude * 0.1  # Rough proxy
            estimated_effective = estimated_base_impact * multiplier
            savings = estimated_base_impact - estimated_effective  # Positive = protected

            if abs(savings) > 1:
                ESGEconomicImpact.objects.create(
                    game=context.game,
                    team=team,
                    round_number=context.round_number,
                    market=market,
                    benefit_type='event_protection',
                    base_value=Decimal(str(round(estimated_base_impact, 2))),
                    effective_value=Decimal(str(round(estimated_effective, 2))),
                    savings=Decimal(str(round(max(savings, 0), 2))),
                    esg_level=Decimal(str(round(
                        float(context.esg_savings.get(team.id, {}).get('_esg_level', 0)) or 0, 2,
                    ))),
                    description=reason or f'ESG event interaction: {template.name}',
                )
