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


def _process_platform_development(team, submission, current_round):
    """
    Process DecisionPlatformDevelopment decisions and advance
    in-development platforms.
    """
    # Process new platform development decisions
    for dev_decision in submission.platform_developments.all():
        gen = dev_decision.platform_generation

        # Check if team already has this generation
        existing = TeamPlatform.objects.filter(
            team=team, platform_generation=gen,
        ).exclude(status='retired').first()

        if existing:
            continue  # Already have this platform

        # Create new platform in development
        dev_rounds = gen.development_rounds

        # CC-32B: Apply org structure decision speed modifier
        try:
            from core.models.cc32b_models import TeamOrganizationalStructure
            import math
            org = TeamOrganizationalStructure.objects.filter(
                game=team.game, team=team,
            ).select_related('current_structure').first()
            if org and org.current_structure and org.transition_rounds_remaining <= 0:
                speed = float(org.current_structure.decision_speed_modifier)
                if speed > 0 and speed != 1.0 and dev_rounds > 0:
                    dev_rounds = max(1, math.floor(dev_rounds / speed))
        except Exception:
            pass

        TeamPlatform.objects.create(
            team=team,
            platform_generation=gen,
            name=dev_decision.platform_name or gen.name,
            status='in_development',
            development_method=dev_decision.method,
            development_started_round=current_round,
            development_rounds_remaining=dev_rounds,
        )

    # Advance existing in-development platforms
    in_dev = TeamPlatform.objects.filter(team=team, status='in_development')
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
                    for feat_id_str, level in dev_decision.feature_levels.items():
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
    for investment in submission.rd_investments.all():
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
    pending = PendingFeatureGain.objects.filter(
        team_platform__team=team,
        applies_round=current_round,
        applied=False,
    )
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

    for create_dec in submission.product_creates.all():
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
    for retire_dec in submission.product_retires.all():
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
