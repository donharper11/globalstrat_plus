"""
Engine Step 4: Strategy Option Effect Application.
From 03-engine-logic.md Section 4.
CC-31A: Compliance processing (B2) and IP exposure processing (B3).
"""
import math
from decimal import Decimal

from core.models.decisions import (
    DecisionMarketEntry, DecisionPartnership, DecisionPlant,
    DecisionESG, DecisionFinancing, DecisionAcquisition,
    DecisionSubmission,
)
from core.models.team_state import (
    TeamMarketPresence, TeamPlant, TeamPartnership,
    TeamStrategyFeatureLevel,
)
from core.models.scenario import (
    FeatureDefinition, StrategyOptionEffect, EntryModeDefinition,
)
from core.models.cc31_models import (
    ComplianceInvestment, TeamMarketCompliance, OriginTrustModifier,
    GovernanceCommitmentType, TeamGovernanceCommitment,
)
from core.engine.utils import clamp, get_config


def apply_strategy_effects(context):
    """
    Engine Step 4: Apply strategy decisions and ongoing effects.
    - Reset strategy-layer features to defaults
    - Process market entry, partnerships, plants, ESG, financing
    - Apply ongoing partnership/entry mode effects
    - Complete plant construction
    """
    game = context.game
    scenario = context.scenario
    current_round = context.round_number

    # Get all strategy-layer features for this scenario
    strategy_features = FeatureDefinition.objects.filter(
        scenario=scenario, layer='strategy',
    )

    for team in context.teams:
        # Reset strategy features to defaults for this round
        _reset_strategy_features(team, strategy_features, current_round)

        submission = DecisionSubmission.objects.filter(
            team=team, round__round_number=current_round, round__game=game,
        ).first()

        if submission:
            # Process this round's decisions
            _process_market_entries(team, submission, current_round)
            _process_partnerships(team, submission, current_round)
            _process_plants(team, submission, current_round)
            _process_esg(team, submission, strategy_features, current_round)
            _process_financing(team, submission)

        # Apply ongoing effects from existing presences and partnerships
        _apply_ongoing_entry_mode_effects(team, strategy_features, current_round)
        _apply_ongoing_partnership_effects(team, strategy_features, current_round)

        # Complete plant construction
        _complete_plant_construction(team, current_round)

        # CC-31A B2: Compliance processing
        _process_compliance(team, submission, context)

        # CC-31A B3: IP exposure processing
        _process_ip_exposure(team, context)

        context.log.append(
            f'Strategy effects applied for team "{team.name}"'
        )


def _reset_strategy_features(team, strategy_features, current_round):
    """Reset strategy-layer feature levels.

    Derived features (calculated from financials at step 12.7) carry
    forward from the previous round so the preference engine (step 5)
    sees real values, not meaningless defaults.  Non-derived features
    are reset to defaults and rewritten by strategy effects.
    """
    DERIVED_FEATURE_CODES = {
        'financial_stability', 'dividend_consistency', 'revenue_momentum',
        'profitability', 'innovation_intensity', 'market_expansion',
        'sustainability_commitment', 'governance_quality',
        'social_responsibility', 'local_manufacturing',
        'distribution_commitment', 'market_tenure',
    }

    prev_round = current_round - 1

    for feature in strategy_features:
        if feature.code in DERIVED_FEATURE_CODES:
            # Carry forward previous round's value (all markets)
            TeamStrategyFeatureLevel.objects.filter(
                team=team, feature=feature, round_number=current_round,
            ).delete()

            prev_levels = TeamStrategyFeatureLevel.objects.filter(
                team=team, feature=feature, round_number=prev_round,
            )
            if prev_levels.exists():
                for prev in prev_levels:
                    TeamStrategyFeatureLevel.objects.create(
                        team=team,
                        feature=feature,
                        market=prev.market,
                        current_level=prev.current_level,
                        round_number=current_round,
                    )
            else:
                # No previous value — use default
                TeamStrategyFeatureLevel.objects.create(
                    team=team,
                    feature=feature,
                    market=None,
                    current_level=feature.default_value,
                    round_number=current_round,
                )
        else:
            # Non-derived: reset to default (will be overwritten by effects)
            TeamStrategyFeatureLevel.objects.filter(
                team=team, feature=feature, round_number=current_round,
            ).delete()
            TeamStrategyFeatureLevel.objects.create(
                team=team,
                feature=feature,
                market=None,
                current_level=feature.default_value,
                round_number=current_round,
            )


def _process_market_entries(team, submission, current_round):
    """Process DecisionMarketEntry decisions."""
    for entry_dec in submission.market_entries.all():
        if entry_dec.action == 'enter':
            # Check if already present
            existing = TeamMarketPresence.objects.filter(
                team=team, market=entry_dec.market,
            ).exclude(status='exited').first()
            if existing:
                continue

            # Check re-entry cooling period (1 round after exit)
            recent_exit = DecisionMarketEntry.objects.filter(
                submission__team=team,
                market=entry_dec.market,
                action='exit',
                submission__round__game=team.game,
                submission__round__round_number__gte=current_round - 1,
            ).exists()
            if recent_exit:
                # Cannot re-enter within 1 round of exit
                continue

            setup_rounds = entry_dec.entry_mode.setup_rounds

            # CC-32B: Apply org structure decision speed modifier to setup time
            try:
                from core.models.cc32b_models import TeamOrganizationalStructure
                org = TeamOrganizationalStructure.objects.filter(
                    game=team.game, team=team,
                ).select_related('current_structure').first()
                if org and org.current_structure and org.transition_rounds_remaining <= 0:
                    import math
                    speed = float(org.current_structure.decision_speed_modifier)
                    if speed > 0 and speed != 1.0:
                        setup_rounds = max(1, math.floor(setup_rounds / speed)) if setup_rounds > 0 else 0
            except Exception:
                pass

            status = 'setup' if setup_rounds > 0 else 'active'

            TeamMarketPresence.objects.create(
                team=team,
                market=entry_dec.market,
                entry_mode=entry_dec.entry_mode,
                established_round=current_round,
                initial_investment=entry_dec.initial_investment,
                status=status,
                setup_rounds_remaining=setup_rounds,
            )

        elif entry_dec.action == 'change_mode':
            presence = TeamMarketPresence.objects.filter(
                team=team, market=entry_dec.market,
            ).exclude(status='exited').first()
            if presence:
                presence.entry_mode = entry_dec.entry_mode
                presence.save()

        elif entry_dec.action == 'exit':
            presences = TeamMarketPresence.objects.filter(
                team=team, market=entry_dec.market,
            ).exclude(status='exited')
            presences.update(status='exited')

            # Deactivate all TeamProductMarket entries for this market
            from core.models.team_state import TeamProductMarket
            TeamProductMarket.objects.filter(
                team_product__team=team,
                market=entry_dec.market,
                is_active=True,
            ).update(is_active=False)

            # Calculate exit cost = 20% of initial entry investment
            # and store on team for the financial engine to pick up
            exit_investment = entry_dec.initial_investment or Decimal('0')
            exit_cost = (exit_investment * Decimal('0.20')).quantize(
                Decimal('0.01'),
            )
            if not hasattr(team, '_exit_costs'):
                team._exit_costs = Decimal('0')
            team._exit_costs += exit_cost


def _process_partnerships(team, submission, current_round):
    """Process DecisionPartnership decisions."""
    for part_dec in submission.partnerships.all():
        if part_dec.action == 'establish':
            TeamPartnership.objects.create(
                team=team,
                market=part_dec.market,
                strategy_option=part_dec.strategy_option,
                annual_investment=part_dec.annual_investment,
                established_round=current_round,
                status='active',
            )

        elif part_dec.action == 'modify':
            existing = TeamPartnership.objects.filter(
                team=team, market=part_dec.market,
                strategy_option=part_dec.strategy_option,
                status='active',
            ).first()
            if existing:
                existing.annual_investment = part_dec.annual_investment
                existing.save()

        elif part_dec.action == 'terminate':
            TeamPartnership.objects.filter(
                team=team, market=part_dec.market,
                strategy_option=part_dec.strategy_option,
                status='active',
            ).update(status='terminated', terminated_round=current_round)


def _process_plants(team, submission, current_round):
    """Process DecisionPlant decisions."""
    for plant_dec in submission.plant_decisions.all():
        market = plant_dec.market

        if plant_dec.action == 'build':
            if not market.allows_manufacturing:
                continue

            build_rounds = market.plant_build_rounds

            # CC-32B: Apply org structure decision speed modifier
            try:
                from core.models.cc32b_models import TeamOrganizationalStructure
                import math
                org = TeamOrganizationalStructure.objects.filter(
                    game=team.game, team=team,
                ).select_related('current_structure').first()
                if org and org.current_structure and org.transition_rounds_remaining <= 0:
                    speed = float(org.current_structure.decision_speed_modifier)
                    if speed > 0 and speed != 1.0 and build_rounds > 0:
                        build_rounds = max(1, math.floor(build_rounds / speed))
            except Exception:
                pass

            TeamPlant.objects.create(
                team=team,
                market=market,
                status='under_construction',
                capacity_units=market.plant_capacity_units or 0,
                construction_started_round=current_round,
                completion_round=current_round + build_rounds,
            )

        elif plant_dec.action == 'expand':
            plant = TeamPlant.objects.filter(
                team=team, market=market, status='operational',
            ).first()
            if plant and plant_dec.capacity_units:
                plant.capacity_units += plant_dec.capacity_units
                plant.save()

        elif plant_dec.action == 'contract_mfg':
            # Contract manufacturing: validate capacity cap and store on context
            if not market.contract_mfg_available:
                continue
            cap = market.contract_mfg_capacity_cap or 30000
            requested = plant_dec.contract_mfg_volume or 0
            capped_volume = min(requested, cap)
            # Store contract mfg volume in a context-accessible location
            # (used by costs.py to enforce capacity limits)
            if not hasattr(team, '_contract_mfg_volumes'):
                team._contract_mfg_volumes = {}
            team._contract_mfg_volumes[market.id] = capped_volume


def _process_esg(team, submission, strategy_features, current_round):
    """
    Process DecisionESG effects on strategy features.

    CC-31J: Governance commitments are now differentiated with per-commitment
    costs, benefits, interactions, amplifiers, and revocation penalties.
    Falls back to legacy len() logic if no GovernanceCommitmentType records exist.
    """
    try:
        esg = submission.esg
    except Exception:
        return

    if not esg:
        return

    # Find the esg_track_record strategy feature
    esg_feature = None
    for feature in strategy_features:
        if feature.code == 'esg_track_record':
            esg_feature = feature
            break

    if not esg_feature:
        return

    # Investment-based level: logarithmic curve, halflife $2M
    total_investment = float(esg.environmental_investment) + float(esg.social_investment)
    halflife = 2_000_000.0
    if total_investment > 0:
        investment_level = 1.0 + 7.0 * (1.0 - math.exp(-total_investment / halflife))
    else:
        investment_level = 0.0

    # --- CC-31J: Differentiated governance processing ---
    game = team.game_set.first() if hasattr(team, 'game_set') else None
    if not game:
        from core.models.core import Game
        game = Game.objects.filter(teams=team).first()

    scenario = game.scenario if game else None
    commitment_types = GovernanceCommitmentType.objects.filter(
        scenario=scenario,
    ) if scenario else GovernanceCommitmentType.objects.none()

    if commitment_types.exists():
        # NEW: Differentiated governance processing
        governance_bonus = _process_governance_commitments_differentiated(
            team, game, esg, commitment_types, current_round,
        )
    else:
        # LEGACY fallback: simple count * 0.8
        gov_val = esg.governance_commitments or 0
        gov_count = len(gov_val) if isinstance(gov_val, (list, dict)) else int(gov_val)
        governance_bonus = gov_count * 0.8

    # Apply ESG visibility amplifier if Public ESG Reporting is active
    esg_visibility_mult = 1.0
    if game and commitment_types.exists():
        reporting_active = TeamGovernanceCommitment.objects.filter(
            game=game, team=team, is_active=True,
            commitment_type__code='public_esg_reporting',
        ).exists()
        if reporting_active:
            # Check for greenwashing (cumulative ESG investment < $1M)
            if total_investment < 1_000_000:
                pass  # Don't apply amplifier when greenwashing
            else:
                amplifier = commitment_types.filter(code='public_esg_reporting').first()
                if amplifier and amplifier.amplifier:
                    esg_visibility_mult = float(amplifier.amplifier.get('multiplier', 1.0))

    esg_level = min((investment_level * esg_visibility_mult) + governance_bonus, 10.0)

    if esg_level > 0:
        _add_to_strategy_level(
            team, esg_feature, None, current_round, esg_level,
        )


def _process_governance_commitments_differentiated(team, game, esg, commitment_types, current_round):
    """
    CC-31J: Process each governance commitment with differentiated effects.

    1. Detect revocations (was active last round, now unchecked)
    2. Detect new adoptions
    3. Sum governance_quality boosts from active commitments
    4. Calculate interaction costs
    5. Process revocation penalties (active even after uncommitting)

    Returns: governance_bonus (float) for esg_track_record
    """
    from core.models.talent import DecisionTalent

    current_codes = set()
    gov_val = esg.governance_commitments
    if isinstance(gov_val, (list,)):
        current_codes = set(gov_val)
    elif isinstance(gov_val, dict):
        current_codes = set(gov_val.keys())

    governance_bonus = 0.0
    total_governance_cost = Decimal('0')
    interaction_costs = Decimal('0')

    # Detect revocations: was active but not in current decisions
    for tgc in TeamGovernanceCommitment.objects.filter(game=game, team=team, is_active=True):
        if tgc.commitment_type.code not in current_codes:
            # REVOCATION
            tgc.is_active = False
            tgc.revoked_round = current_round
            penalty = tgc.commitment_type.revocation_penalty or {}
            tgc.penalty_rounds_remaining = penalty.get('duration_rounds', 2)
            tgc.save()

    # Detect new adoptions and process active commitments
    for ct in commitment_types:
        tgc, _ = TeamGovernanceCommitment.objects.get_or_create(
            game=game, team=team, commitment_type=ct,
            defaults={'is_active': False},
        )

        if ct.code in current_codes:
            if not tgc.is_active:
                tgc.is_active = True
                tgc.activated_round = current_round
                tgc.save()

            # Apply ongoing cost
            total_governance_cost += ct.ongoing_cost_per_round

            # Sum governance_quality boosts
            for benefit in (ct.benefits or []):
                if benefit.get('target') == 'governance_quality':
                    governance_bonus += float(benefit.get('boost', 0))

            # Evaluate interactions
            for interaction in (ct.interactions or []):
                condition = interaction.get('condition', {})
                if _evaluate_interaction_condition(condition, team, game, esg):
                    effect = interaction.get('effect', {})
                    cost = _calculate_interaction_cost(effect, team, game)
                    interaction_costs += cost

        # Process revocation penalties (even for inactive commitments)
        if tgc.penalty_rounds_remaining > 0:
            tgc.penalty_rounds_remaining -= 1
            tgc.save()

    # Store governance costs on the context for the cost engine to pick up
    # We use a marker on the team to pass costs through
    team._governance_cost = total_governance_cost + interaction_costs

    return governance_bonus


def _evaluate_interaction_condition(condition, team, game, esg):
    """Check if a governance commitment interaction condition is met."""
    attr = condition.get('attribute', '')
    op = condition.get('operator', '')
    value = condition.get('value')

    if attr == 'salary_level_any_pool':
        from core.models.talent import DecisionTalent
        from core.models.decisions import DecisionSubmission
        sub = DecisionSubmission.objects.filter(
            team=team, round__game=game, round__round_number=game.current_round,
        ).first()
        if sub:
            try:
                talent = sub.talent
                salary_levels = [talent.rd_salary_level, talent.commercial_salary_level, talent.operations_salary_level]
                threshold = int(value) if value else 2
                if op == '<':
                    return any(sl < threshold for sl in salary_levels)
            except Exception:
                pass
        return False

    elif attr == 'entry_mode_in_any_market':
        presences = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).select_related('entry_mode')
        target_mode = str(value).lower()
        return any(p.entry_mode.code.lower() == target_mode for p in presences)

    elif attr == 'uses_contract_manufacturing':
        # True if team has active presence in any market that uses contract manufacturing
        presences = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).select_related('market')
        return any(p.market.contract_mfg_available for p in presences)

    elif attr == 'total_esg_investment':
        total = float(esg.environmental_investment or 0) + float(esg.social_investment or 0)
        threshold = float(value) if value else 0
        if op == '<':
            return total < threshold
        return False

    return False


def _calculate_interaction_cost(effect, team, game):
    """Calculate additional cost from a governance interaction effect."""
    effect_type = effect.get('type', '')

    if effect_type == 'jv_monitoring_cost':
        magnitude = Decimal(str(effect.get('magnitude', 0)))
        per = effect.get('per', '')
        if per == 'jv_market':
            jv_count = TeamMarketPresence.objects.filter(
                team=team, status='active', entry_mode__code='jv',
            ).count()
            return magnitude * jv_count
        return magnitude

    # Other interaction types don't have direct costs
    return Decimal('0')


def _process_financing(team, submission):
    """Process DecisionFinancing — financial state updates handled in CC-6."""
    # Financing effects on team resources (cash, debt, equity) are
    # handled in CC-6 (financial engine). Here we just note it was processed.
    pass


def _apply_ongoing_entry_mode_effects(team, strategy_features, current_round):
    """Apply effects from active market presences."""
    presences = TeamMarketPresence.objects.filter(
        team=team, status__in=['active', 'setup'],
    ).select_related('entry_mode')

    for presence in presences:
        # Advance setup presences
        if presence.status == 'setup':
            presence.setup_rounds_remaining = max(presence.setup_rounds_remaining - 1, 0)
            if presence.setup_rounds_remaining <= 0:
                presence.status = 'active'
            presence.save()
            if presence.status != 'active':
                continue

        # Apply entry mode effects
        for effect in StrategyOptionEffect.objects.filter(
            strategy_option__code=presence.entry_mode.code,
            strategy_option__scenario=team.game.scenario,
        ):
            market = presence.market if effect.market_specific else None
            _apply_effect(team, effect, market, current_round)


def _apply_ongoing_partnership_effects(team, strategy_features, current_round):
    """Apply effects from active partnerships."""
    partnerships = TeamPartnership.objects.filter(
        team=team, status='active',
    ).select_related('strategy_option')

    for partnership in partnerships:
        for effect in partnership.strategy_option.effects.all():
            market = partnership.market if effect.market_specific else None
            _apply_effect(team, effect, market, current_round)


def _complete_plant_construction(team, current_round):
    """Complete plants where construction is done."""
    plants = TeamPlant.objects.filter(
        team=team,
        status='under_construction',
        completion_round__lte=current_round,
    )
    plants.update(status='operational')


def _apply_effect(team, effect, market, current_round):
    """Apply a single StrategyOptionEffect to a team's strategy feature level."""
    feature = effect.feature
    if feature.layer != 'strategy':
        return

    try:
        level = TeamStrategyFeatureLevel.objects.get(
            team=team, feature=feature, market=market,
            round_number=current_round,
        )
    except TeamStrategyFeatureLevel.DoesNotExist:
        level = TeamStrategyFeatureLevel.objects.create(
            team=team, feature=feature, market=market,
            current_level=feature.default_value,
            round_number=current_round,
        )

    current = float(level.current_level)

    if effect.effect_type == 'set':
        new_val = float(effect.effect_value)
    elif effect.effect_type == 'add':
        new_val = current + float(effect.effect_value)
    elif effect.effect_type == 'multiply':
        new_val = current * float(effect.effect_value)
    else:
        return

    new_val = clamp(new_val, float(feature.min_value), float(feature.max_value))
    level.current_level = Decimal(str(round(new_val, 2)))
    level.save()


def _add_to_strategy_level(team, feature, market, current_round, amount):
    """Add a value to a strategy feature level."""
    try:
        level = TeamStrategyFeatureLevel.objects.get(
            team=team, feature=feature, market=market,
            round_number=current_round,
        )
    except TeamStrategyFeatureLevel.DoesNotExist:
        level = TeamStrategyFeatureLevel.objects.create(
            team=team, feature=feature, market=market,
            current_level=feature.default_value,
            round_number=current_round,
        )

    new_val = float(level.current_level) + amount
    new_val = clamp(new_val, float(feature.min_value), float(feature.max_value))
    level.current_level = Decimal(str(round(new_val, 2)))
    level.save()


def _process_compliance(team, submission, context):
    """
    CC-31A B2: Process compliance investment for each active market.
    Updates cumulative investment, compliance level (diminishing returns),
    and trust multiplier erosion.
    """
    scenario = context.scenario
    scale_factor = float(get_config(scenario, 'compliance_scale_factor', default=5000000))

    presences = TeamMarketPresence.objects.filter(
        team=team, status='active',
    ).select_related('market')

    for presence in presences:
        market = presence.market

        # Read compliance investment decision
        investment_amount = Decimal('0')
        if submission:
            ci = ComplianceInvestment.objects.filter(
                submission=submission, market=market,
            ).first()
            if ci:
                investment_amount = ci.investment_amount

        # Get or create compliance record
        record, _ = TeamMarketCompliance.objects.get_or_create(
            game=context.game, team=team, market=market,
        )
        record.cumulative_investment += investment_amount
        record.rounds_present += 1

        # Compliance level: diminishing returns curve
        record.compliance_level = min(
            Decimal('1.00'),
            Decimal(str(round(
                1 - math.exp(-float(record.cumulative_investment) / scale_factor), 2,
            ))),
        )

        # Trust erosion: improve trust multiplier based on sustained presence + compliance
        origin_trust = OriginTrustModifier.objects.filter(
            scenario=scenario,
            origin_market=team.home_market,
            host_market=market,
        ).first() if team.home_market_id else None

        if origin_trust:
            base_trust = origin_trust.customer_trust_multiplier
            erosion_rate = origin_trust.trust_erosion_rate

            # Trust improves each round: faster with higher compliance
            compliance_accelerator = Decimal('1.0') + record.compliance_level
            rounds_improvement = Decimal(str(record.rounds_present)) * erosion_rate * compliance_accelerator

            record.current_trust_multiplier = min(
                Decimal('1.00'),
                base_trust + rounds_improvement,
            )
        else:
            record.current_trust_multiplier = Decimal('1.00')

        record.save()


def _process_ip_exposure(team, context):
    """
    CC-31A B3: Accumulate IP exposure for JV/licensing entry modes.
    """
    presences = TeamMarketPresence.objects.filter(
        team=team, status='active',
    ).select_related('entry_mode')

    for presence in presences:
        mode_code = presence.entry_mode.code.upper() if presence.entry_mode else ''
        if mode_code not in ('JV', 'LICENSING'):
            continue

        # Base rate per round
        base_rate = Decimal('0.03') if mode_code == 'JV' else Decimal('0.05')

        # Local Strategic Partner increases rate slightly
        has_local_strategic = TeamPartnership.objects.filter(
            team=team, market=presence.market, status='active',
            strategy_option__code='LOCAL_STRATEGIC',
        ).exists()
        if has_local_strategic:
            base_rate += Decimal('0.02')

        presence.ip_exposure_cumulative = min(
            Decimal('1.00'),
            presence.ip_exposure_cumulative + base_rate,
        )
        presence.save(update_fields=['ip_exposure_cumulative'])
