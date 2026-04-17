"""
Engine Step 4.5: Talent Processing.
CC-16: Calculate talent levels from salary, training, headcount, and turnover.
CC-31A: Talent allocation & effective multipliers per market.
Update TeamTalentState and TeamStrategyFeatureLevel for talent features.

Called in the engine pipeline after strategy effects (Step 4),
before preference matching (Step 5).
"""
import math
from decimal import Decimal

from core.models.decisions import DecisionSubmission
from core.models.talent import DecisionTalent, TeamTalentState
from core.models.scenario import FeatureDefinition
from core.models.team_state import TeamStrategyFeatureLevel, TeamMarketPresence
from core.models.cc31_models import TalentAllocation, CulturalDistanceMatrix, TeamMarketCompliance
from core.engine.utils import get_config, clamp

D = Decimal


def get_talent_level(team, pool, round_number):
    """Get the current talent level for a pool. Returns Decimal."""
    state = TeamTalentState.objects.filter(
        team=team, talent_pool=pool, round_number=round_number,
    ).first()
    if state:
        return state.talent_level
    return D('3.00')  # Default baseline


def process_talent(context):
    """
    Process talent decisions for all teams.
    Calculate talent levels from salary, training, headcount, and turnover.
    Update TeamTalentState and TeamStrategyFeatureLevel for talent features.
    """
    for team in context.teams:
        submission = DecisionSubmission.objects.filter(
            team=team,
            round__round_number=context.round_number,
            round__game=context.game,
        ).first()

        talent_decision = None
        if submission:
            try:
                talent_decision = submission.talent
            except DecisionTalent.DoesNotExist:
                talent_decision = None

        if not talent_decision:
            _carry_forward_talent(team, context.round_number)
            continue

        for pool, prefix in [('rd', 'rd'), ('commercial', 'commercial'), ('operations', 'operations')]:
            headcount = getattr(talent_decision, f'{prefix}_headcount')
            salary_level = getattr(talent_decision, f'{prefix}_salary_level')
            training_budget = D(str(getattr(talent_decision, f'{prefix}_training_budget')))

            # Get previous state
            prev_state = TeamTalentState.objects.filter(
                team=team, talent_pool=pool, round_number=context.round_number - 1,
            ).first()

            prev_cumulative_training = prev_state.cumulative_training if prev_state else D('0')
            prev_headcount = prev_state.headcount if prev_state else 50

            # === Calculate turnover ===
            salary_turnover_map = {
                1: D('0.25'),  # Below market: 25% leave per round
                2: D('0.15'),  # Market rate: 15%
                3: D('0.08'),  # Above market: 8%
                4: D('0.04'),  # Premium: 4%
                5: D('0.02'),  # Top of market: 2%
            }
            base_turnover = salary_turnover_map.get(salary_level, D('0.10'))

            if team.is_in_distress:
                base_turnover += D('0.10')

            headcount_change_pct = abs(headcount - prev_headcount) / max(prev_headcount, 1)
            if headcount_change_pct > 0.20:
                base_turnover += D('0.05')

            turnover_rate = clamp(base_turnover, D('0.01'), D('0.50'))

            # === Calculate cumulative training ===
            training_decay = D('0.10')
            new_cumulative = prev_cumulative_training * (1 - training_decay) + training_budget

            # === Calculate talent level ===
            # Salary component: maps salary_level 1-5 to score 2-10
            salary_score = D(str(salary_level * 2))

            # Training component: diminishing returns
            training_halflife = D(str(get_config(context.scenario, 'training_halflife', 5000000)))
            training_score = D(str(
                1 + 9 * (1 - math.exp(-float(new_cumulative) / float(training_halflife)))
            ))

            # Headcount efficiency
            optimal_headcount = {
                'rd': int(get_config(context.scenario, 'optimal_rd_headcount', 60)),
                'commercial': int(get_config(context.scenario, 'optimal_commercial_headcount', 40)),
                'operations': int(get_config(context.scenario, 'optimal_operations_headcount', 50)),
            }[pool]

            headcount_ratio = headcount / max(optimal_headcount, 1)
            if headcount_ratio < 0.5:
                headcount_score = D('2')
            elif headcount_ratio < 0.8:
                headcount_score = D('5')
            elif headcount_ratio <= 1.2:
                headcount_score = D('8')
            elif headcount_ratio <= 1.5:
                headcount_score = D('6')
            else:
                headcount_score = D('4')

            # Retention component
            retention_score = D(str(10 * (1 - float(turnover_rate))))

            # Weighted combination
            talent_level = (
                salary_score * D('0.40') +
                training_score * D('0.35') +
                headcount_score * D('0.15') +
                retention_score * D('0.10')
            )
            talent_level = clamp(talent_level, D('1.00'), D('10.00'))

            # === Save state ===
            TeamTalentState.objects.update_or_create(
                team=team,
                talent_pool=pool,
                round_number=context.round_number,
                defaults={
                    'headcount': headcount,
                    'salary_level': salary_level,
                    'cumulative_training': new_cumulative,
                    'talent_level': talent_level,
                    'turnover_rate': turnover_rate,
                }
            )

            # === Update strategy feature level ===
            feature_code = f'{pool}_talent'
            feature = FeatureDefinition.objects.filter(
                scenario=context.scenario, code=feature_code,
            ).first()
            if feature:
                TeamStrategyFeatureLevel.objects.update_or_create(
                    team=team,
                    feature=feature,
                    market=None,
                    round_number=context.round_number,
                    defaults={'current_level': talent_level},
                )

    # CC-31A B1: Calculate effective talent multipliers per market
    _calculate_market_talent_multipliers(context)

    context.log.append('Talent processed')


def _calculate_market_talent_multipliers(context):
    """
    CC-31A B1: For each team × pool × active market, compute effective
    talent multiplier = global_talent_level × localization_factor.
    Cache results on TeamMarketCompliance.
    """
    scenario = context.scenario
    hq_baseline = int(get_config(scenario, 'localization_staff_baseline', default=10))

    for team in context.teams:
        # Get talent allocations for this round
        submission = DecisionSubmission.objects.filter(
            team=team,
            round__round_number=context.round_number,
            round__game=context.game,
        ).first()

        allocations = {}
        if submission:
            for alloc in TalentAllocation.objects.filter(submission=submission):
                allocations[alloc.talent_pool] = alloc

        # Get active markets
        presences = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).select_related('market')

        for presence in presences:
            market = presence.market

            # Get or create compliance record
            compliance, _ = TeamMarketCompliance.objects.get_or_create(
                game=context.game, team=team, market=market,
            )

            for pool in ['rd', 'commercial', 'operations']:
                global_level = get_talent_level(team, pool, context.round_number)

                # Home market = full effectiveness
                if team.home_market_id and market.id == team.home_market_id:
                    localization_factor = D('1.0')
                else:
                    # Cultural distance base effectiveness
                    distance = CulturalDistanceMatrix.objects.filter(
                        scenario=scenario,
                        from_market=team.home_market,
                        to_market=market,
                    ).first()
                    base_effectiveness = D(str(distance.base_effectiveness)) if distance else D('0.65')

                    # Market headcount from allocation
                    alloc = allocations.get(pool)
                    market_count = 0
                    if alloc:
                        market_count = alloc.market_allocation.get(market.code, 0)

                    staffing_ratio = min(D('1.0'), D(str(market_count)) / D(str(max(hq_baseline, 1))))

                    compliance_boost = D('1.0') + (compliance.compliance_level * D('0.3'))

                    localization_factor = base_effectiveness + (D('1.0') - base_effectiveness) * staffing_ratio * compliance_boost
                    localization_factor = min(D('1.0'), localization_factor)

                # CC-32B: Apply org structure talent modifiers
                org_mods = getattr(context, 'org_modifiers', {}).get(team.id, {})
                if team.home_market_id and market.id == team.home_market_id:
                    org_talent_mod = org_mods.get('hq_modifier', D('1.00'))
                else:
                    org_talent_mod = org_mods.get('local_modifier', D('1.00'))

                effective_multiplier = (global_level * localization_factor * org_talent_mod).quantize(D('0.01'))

                setattr(compliance, f'effective_{pool}_multiplier', effective_multiplier)

            compliance.save()


def _carry_forward_talent(team, round_number):
    """If no talent decisions made, carry forward previous state with decay."""
    for pool in ['rd', 'commercial', 'operations']:
        prev = TeamTalentState.objects.filter(
            team=team, talent_pool=pool, round_number=round_number - 1,
        ).first()
        if prev:
            new_cumulative = prev.cumulative_training * D('0.90')
            TeamTalentState.objects.update_or_create(
                team=team, talent_pool=pool, round_number=round_number,
                defaults={
                    'headcount': prev.headcount,
                    'salary_level': prev.salary_level,
                    'cumulative_training': new_cumulative,
                    'talent_level': max(prev.talent_level - D('0.20'), D('1.00')),
                    'turnover_rate': prev.turnover_rate,
                }
            )
