"""
Engine Step 3: Platform & Feature Level Updates (R&D Processing).
From 03-engine-logic.md Section 3.
"""
from decimal import Decimal

from core.models.decisions import (
    DecisionRDInvestment, DecisionPlatformDevelopment,
    DecisionProductCreate, DecisionProductRetire, DecisionSubmission,
)
from core.models.team_state import (
    TeamPlatform, TeamPlatformFeatureLevel, PendingFeatureGain,
    TeamProduct, TeamProductMarket,
)
from core.models.scenario import PlatformFeatureCeiling
from core.engine.utils import calculate_level_gain


def process_rd(context):
    """
    Engine Step 3: Process R&D investments and platform development.
    - Complete platform developments
    - Apply licensed feature gains immediately
    - Create pending gains for in-house R&D
    - Apply pending gains from prior rounds
    - Process product create/retire decisions
    """
    game = context.game
    scenario = context.scenario
    current_round = context.round_number

    for team in context.teams:
        submission = DecisionSubmission.objects.filter(
            team=team, round__round_number=current_round, round__game=game,
        ).first()
        if not submission:
            continue

        # ----- Platform development completion -----
        _process_platform_development(team, submission, current_round)

        # ----- Feature investments (R&D) -----
        _process_feature_investments(team, submission, scenario, current_round, context)

        # ----- Apply pending feature gains from earlier rounds -----
        _apply_pending_gains(team, current_round)

        # ----- Product creation -----
        _process_product_creates(team, submission, current_round)

        # ----- Product retirement -----
        _process_product_retires(team, submission, current_round)

        context.log.append(
            f'R&D processed for team "{team.name}"'
        )


#: A platform is never ready in the round it is created. A generation authored
#: at 0 still waits this long; the scenario's `max_platform_development_rounds`
#: bounds the other end.
MIN_DEVELOPMENT_ROUNDS = 1


def _development_rounds_for(team, gen):
    """The authored wait for one generation, bounded by the scenario."""
    import math
    from core.engine.utils import get_config
    try:
        scenario_max = int(get_config(
            team.game.scenario, 'max_platform_development_rounds', 2))
    except (TypeError, ValueError):
        scenario_max = 2
    dev_rounds = max(MIN_DEVELOPMENT_ROUNDS,
                     min(scenario_max, gen.development_rounds or 0))

    # CC-32B: organisational structure speed modifier, never below the
    # minimum -- an org chart cannot make a platform ready in the round it
    # was started.
    try:
        from core.models.cc32b_models import TeamOrganizationalStructure
        org = TeamOrganizationalStructure.objects.filter(
            game=team.game, team=team,
        ).select_related('current_structure').first()
        if org and org.current_structure and org.transition_rounds_remaining <= 0:
            speed = float(org.current_structure.decision_speed_modifier)
            if speed > 0 and speed != 1.0 and dev_rounds > 0:
                dev_rounds = max(MIN_DEVELOPMENT_ROUNDS,
                                 math.floor(dev_rounds / speed))
    except Exception:
        pass
    return dev_rounds


def _process_platform_development(team, submission, current_round):
    """Process platform development decisions and advance in-development rows.

    Funding is decided **once for the whole team**, over every candidate this
    round: the drafts carried from earlier rounds and the new requests in this
    submission. V2-045: deciding it one platform at a time against an
    unreserved balance let two $1,000,000 drafts both start against $1,500,000
    of cash, and the accounting path then booked $2,000,000.

    Priority is carried drafts first, then new requests, each in generation
    order and then by name. Drafts first because a team that committed in an
    earlier round and could not pay should not be pushed further back by a
    request it made later; without a stated rule an old draft can starve
    indefinitely. The order is deterministic either way, which is what the
    accounting depends on.
    """
    from core.services.rd_costs import allocate_platform_funding

    # -- carried drafts, oldest commitment first --------------------------
    #
    # A draft is only a candidate if the team holds no other non-retired
    # platform for its generation. Runtime f39b853 could leave exactly that
    # residue -- one platform funded and one draft for the same generation --
    # and promoting the draft would create a second live platform for one
    # generation. Phase 1 refuses that state outright; this guard is the
    # defence, not the repair, so nothing is silently promoted if the engine is
    # reached another way.
    # Count every non-retired row per generation, drafts included. A
    # generation holding more than one is invalid inventory, not a choice
    # between candidates: **no** draft for it is promoted.
    #
    # An earlier version built this set by excluding unfunded_draft, so two
    # carried drafts for one generation were invisible to it and the
    # de-duplication then promoted the first one -- picking a winner from
    # inventory that should have been refused outright. Phase 1 does refuse
    # that state before the allocator is reached, but this defence has to hold
    # on its own terms, not because something upstream usually fires first.
    from collections import Counter
    non_retired = list(TeamPlatform.objects
                       .filter(team=team).exclude(status='retired')
                       .order_by('platform_generation_id', 'id')
                       .values_list('platform_generation_id', 'status'))
    per_generation = Counter(generation for generation, _ in non_retired)
    conflicted = {generation for generation, count in per_generation.items()
                  if count > 1}
    live_generations = {generation for generation, status in non_retired
                        if status != 'unfunded_draft'}

    drafts = [draft for draft in TeamPlatform.objects
              .filter(team=team, status='unfunded_draft')
              .select_related('platform_generation')
              .order_by('platform_generation__generation_order', 'name', 'id')
              if draft.platform_generation_id not in live_generations
              and draft.platform_generation_id not in conflicted]

    # -- new requests -------------------------------------------------------
    #
    # Two independent exclusions, both needed. A generation the team already
    # holds -- active, in development, or carried as an unfunded draft -- is
    # not a new candidate. And a generation already taken by an earlier row in
    # this same submission is not a second candidate: collecting candidates
    # before creating any platform means every row sees the same pre-loop
    # database state, so without this a duplicate pair was funded twice and
    # created twice (V2-046).
    #
    # The write surfaces and the Phase-1 precondition both refuse a duplicate
    # pair outright. This exclusion is deliberately not their substitute: it
    # keeps the allocator's inventory correct on its own terms, so no path can
    # produce two live platforms for one team and generation.
    held = set(TeamPlatform.objects
               .filter(team=team).exclude(status='retired')
               .order_by('platform_generation_id', 'id')
               .values_list('platform_generation_id', flat=True))
    new_requests = []
    claimed = set()
    for dev_decision in submission.platform_developments.all().order_by(
            'platform_generation__generation_order', 'platform_name', 'id'):
        generation_id = dev_decision.platform_generation_id
        if generation_id in held or generation_id in claimed:
            continue
        claimed.add(generation_id)
        new_requests.append(dev_decision)

    candidates = (
        [(('draft', draft.id), draft.platform_generation,
          draft.development_method) for draft in drafts]
        + [(('new', decision.id), decision.platform_generation,
            decision.method) for decision in new_requests])
    funded = allocate_platform_funding(team, candidates)

    # -- promote the drafts that fit --------------------------------------
    for draft in drafts:
        if ('draft', draft.id) not in funded:
            continue        # stays a draft: no funding round, no clock
        draft.status = 'in_development'
        draft.development_started_round = current_round
        draft.funded_round = current_round
        draft.development_rounds_remaining = _development_rounds_for(
            team, draft.platform_generation)
        draft.save(update_fields=['status', 'development_started_round',
                                  'funded_round',
                                  'development_rounds_remaining'])

    # -- create this round's requests, funded or not -----------------------
    for decision in new_requests:
        gen = decision.platform_generation
        affordable = ('new', decision.id) in funded
        TeamPlatform.objects.create(
            team=team,
            platform_generation=gen,
            name=decision.platform_name or gen.name,
            status='in_development' if affordable else 'unfunded_draft',
            development_method=decision.method,
            development_started_round=current_round if affordable else None,
            funded_round=current_round if affordable else None,
            development_rounds_remaining=(
                _development_rounds_for(team, gen) if affordable else None),
        )

    # Advance in-development platforms started in an *earlier* round.
    #
    # The filter on development_started_round is the V2-040 repair. Without it
    # this loop decremented platforms created a few lines above, in the same
    # call for the same round, so the authored development_rounds was always
    # one more than the number of rounds a team actually waited -- and an
    # authored 0 went straight to -1 and became active immediately.
    in_dev = (TeamPlatform.objects
              .filter(team=team, status='in_development',
                      development_started_round__lt=current_round)
              .order_by('name'))
    for platform in in_dev:
        if platform.development_rounds_remaining is not None:
            platform.development_rounds_remaining -= 1
            if platform.development_rounds_remaining <= 0:
                platform.status = 'active'
                platform.activated_round = current_round
                # Initialize only the features the user selected (max 5)
                # Find the DecisionPlatformDevelopment that created this platform
                dev_decision = DecisionPlatformDevelopment.objects.filter(
                    submission__team=team,
                    platform_generation=platform.platform_generation,
                ).order_by('-submission__round__round_number').first()

                if dev_decision and dev_decision.feature_levels:
                    from core.models.scenario import FeatureDefinition
                    # Every named feature is initialised. The cap is enforced
                    # on the write surfaces and refused at the engine
                    # precondition; it is deliberately NOT applied by slicing
                    # here. Truncating an over-cap decision activated an
                    # arbitrary subset while the stored row still named more,
                    # so the evidence disagreed with the platform built from
                    # it -- a decision silently replaced with a different one,
                    # which is the shape V2-037 taught this handoff to refuse.
                    for feat_id_str, level in sorted(
                            dev_decision.feature_levels.items()):
                        if level and float(level) > 0:
                            try:
                                feat = FeatureDefinition.objects.get(pk=int(feat_id_str))
                                TeamPlatformFeatureLevel.objects.update_or_create(
                                    team_platform=platform,
                                    feature=feat,
                                    defaults={'current_level': float(level)},
                                )
                            except FeatureDefinition.DoesNotExist:
                                continue
                else:
                    # Fallback: no decision found (e.g. starter platforms)
                    # Use ceilings but cap at max_platform_features
                    from core.engine.utils import get_config
                    max_features = get_config(
                        team.game.scenario, 'max_platform_features', 5, int,
                    )
                    ceilings = PlatformFeatureCeiling.objects.filter(
                        platform_generation=platform.platform_generation,
                    ).order_by('-starting_value')[:max_features]
                    for ceiling in ceilings:
                        TeamPlatformFeatureLevel.objects.update_or_create(
                            team_platform=platform,
                            feature=ceiling.feature,
                            defaults={'current_level': ceiling.starting_value},
                        )
            platform.save()


def _process_feature_investments(team, submission, scenario, current_round, context=None):
    """Process DecisionRDInvestment records — level-based or legacy dollar-based."""
    for investment in submission.rd_investments.all().order_by(
            'team_platform__name', 'feature__code', 'method'):
        tp = investment.team_platform
        feature = investment.feature

        # Must be on an active platform
        if tp.status != 'active':
            continue

        # Get current level
        fl, _ = TeamPlatformFeatureLevel.objects.get_or_create(
            team_platform=tp,
            feature=feature,
            defaults={'current_level': feature.default_value},
        )
        current_level = float(fl.current_level)

        # Get ceiling
        try:
            ceiling = PlatformFeatureCeiling.objects.get(
                platform_generation=tp.platform_generation,
                feature=feature,
            )
            ceiling_val = float(ceiling.ceiling_value)
        except PlatformFeatureCeiling.DoesNotExist:
            ceiling_val = float(feature.max_value)

        if current_level >= ceiling_val:
            continue  # Already at max

        # CC-16: Apply R&D talent cost modifier
        # Talent level 3 = baseline (1.0x), level 7 = 0.80x (20% cheaper)
        from core.engine.talent import get_talent_level
        from core.engine.utils import clamp as _clamp
        rd_talent = get_talent_level(team, 'rd', current_round)
        talent_cost_modifier = Decimal('1.0') - (rd_talent - Decimal('3')) * Decimal('0.05')
        talent_cost_modifier = _clamp(talent_cost_modifier, Decimal('0.60'), Decimal('1.20'))

        # Level-based R&D (new model)
        if investment.target_level and investment.target_level > int(current_level):
            target = min(investment.target_level, int(ceiling_val))

            if investment.method == 'license':
                if not feature.is_licensable:
                    continue
                # Licensed: immediate effect
                fl.current_level = Decimal(str(target))
                fl.save()
            elif investment.method == 'in_house':
                # In-house: delayed effect
                applies_round = current_round + feature.time_lag_rounds
                gain = target - current_level
                # CC-32B: Apply org innovation modifier
                if context:
                    org_mods = getattr(context, 'org_modifiers', {}).get(team.id, {})
                    innovation_mod = float(org_mods.get('innovation_modifier', 1.0))
                    gain = gain * innovation_mod
                PendingFeatureGain.objects.create(
                    team_platform=tp,
                    feature=feature,
                    gain_amount=Decimal(str(round(gain, 2))),
                    applies_round=applies_round,
                )
        else:
            # Legacy dollar-based fallback
            # CC-16: Talent modifier makes each dollar more effective
            amount = float(investment.amount) / float(talent_cost_modifier)
            if amount <= 0:
                continue

            if investment.method == 'license':
                if not feature.is_licensable:
                    continue
                effective_amount = amount / float(feature.license_cost_multiplier)
                gain = calculate_level_gain(
                    effective_amount, current_level,
                    feature.cost_curve_type, float(feature.cost_base),
                    scenario=scenario,
                )
                # CC-32B: Apply org innovation modifier
                if context:
                    org_mods = getattr(context, 'org_modifiers', {}).get(team.id, {})
                    innovation_mod = float(org_mods.get('innovation_modifier', 1.0))
                    gain = gain * innovation_mod
                new_level = min(current_level + gain, ceiling_val)
                fl.current_level = Decimal(str(round(new_level, 2)))
                fl.save()

            elif investment.method == 'in_house':
                gain = calculate_level_gain(
                    amount, current_level,
                    feature.cost_curve_type, float(feature.cost_base),
                    scenario=scenario,
                )
                # CC-32B: Apply org innovation modifier
                if context:
                    org_mods = getattr(context, 'org_modifiers', {}).get(team.id, {})
                    innovation_mod = float(org_mods.get('innovation_modifier', 1.0))
                    gain = gain * innovation_mod
                if gain > 0:
                    applies_round = current_round + feature.time_lag_rounds
                    PendingFeatureGain.objects.create(
                        team_platform=tp,
                        feature=feature,
                        gain_amount=Decimal(str(round(gain, 2))),
                        applies_round=applies_round,
                    )


def _apply_pending_gains(team, current_round):
    """Apply PendingFeatureGain records that are due this round."""
    pending = (PendingFeatureGain.objects.filter(
        team_platform__team=team,
        applies_round=current_round,
        applied=False,
    )).order_by('team_platform__name', 'feature__code')
    for pg in pending:
        tp = pg.team_platform
        feature = pg.feature

        fl, _ = TeamPlatformFeatureLevel.objects.get_or_create(
            team_platform=tp,
            feature=feature,
            defaults={'current_level': feature.default_value},
        )
        current_level = float(fl.current_level)

        try:
            ceiling = PlatformFeatureCeiling.objects.get(
                platform_generation=tp.platform_generation,
                feature=feature,
            )
            ceiling_val = float(ceiling.ceiling_value)
        except PlatformFeatureCeiling.DoesNotExist:
            ceiling_val = float(feature.max_value)

        new_level = min(current_level + float(pg.gain_amount), ceiling_val)
        fl.current_level = Decimal(str(round(new_level, 2)))
        fl.save()

        pg.applied = True
        pg.save()


def _process_product_creates(team, submission, current_round):
    """Process DecisionProductCreate records."""
    from core.models.scenario import MarketDefinition

    for create_dec in submission.product_creates.all().order_by('product_name'):
        product = TeamProduct.objects.create(
            team=team,
            team_platform=create_dec.team_platform,
            name=create_dec.product_name,
            positioning=create_dec.positioning,
            status='active',
            created_round=current_round,
        )
        # Create market links
        for market_id in create_dec.target_market_ids:
            try:
                market = MarketDefinition.objects.get(id=market_id)
                TeamProductMarket.objects.create(
                    team_product=product,
                    market=market,
                    first_offered_round=current_round,
                )
            except MarketDefinition.DoesNotExist:
                pass


def _process_product_retires(team, submission, current_round):
    """Process DecisionProductRetire records."""
    for retire_dec in submission.product_retires.all().order_by('team_product__name'):
        product = retire_dec.team_product
        if retire_dec.timing == 'immediate':
            product.status = 'retired'
            product.retired_round = current_round
            product.save()
            TeamProductMarket.objects.filter(team_product=product).update(
                is_active=False,
            )
        elif retire_dec.timing == 'end_of_round':
            # Mark for retirement at end — handled after adoption
            product.status = 'retired'
            product.retired_round = current_round
            product.save()
