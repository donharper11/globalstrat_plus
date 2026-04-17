"""
CC-32B: Organizational Structure Engine Integration.
Applies org structure modifiers to talent, R&D, coordination, and speed.
Calculates overhead costs.
"""
import math
from decimal import Decimal

from core.models.cc32b_models import TeamOrganizationalStructure
from core.models.team_state import TeamMarketPresence
from core.models.talent import TeamTalentState
from core.engine.utils import clamp

D = Decimal


def _count_active_markets(team):
    """Count number of active market presences for a team."""
    return TeamMarketPresence.objects.filter(team=team, status='active').count()


def _get_avg_talent_level(team, round_number):
    """Get average talent level across all pools."""
    states = TeamTalentState.objects.filter(
        team=team, round_number=round_number,
    )
    if not states.exists():
        return D('3.00')
    total = sum(s.talent_level for s in states)
    return total / states.count()


def apply_org_structure_modifiers(context):
    """
    CC-32B Step 4.55: Apply organizational structure modifiers.
    After talent processing, before preference matching.
    """
    for team in context.teams:
        try:
            org = TeamOrganizationalStructure.objects.get(
                game=context.game, team=team,
            )
        except TeamOrganizationalStructure.DoesNotExist:
            context.org_modifiers[team.id] = {
                'hq_modifier': D('1.00'),
                'local_modifier': D('1.00'),
                'innovation_modifier': D('1.00'),
                'coordination_modifier': D('1.00'),
                'speed_modifier': D('1.00'),
            }
            continue

        structure = org.current_structure
        if not structure:
            context.org_modifiers[team.id] = {
                'hq_modifier': D('1.00'),
                'local_modifier': D('1.00'),
                'innovation_modifier': D('1.00'),
                'coordination_modifier': D('1.00'),
                'speed_modifier': D('1.00'),
            }
            continue

        # Check transition disruption
        if org.transition_rounds_remaining > 0:
            disruption_factor = D('0.85')  # 15% effectiveness reduction
            org.transition_rounds_remaining -= 1
            org.save()
        else:
            disruption_factor = D('1.00')

        # Check overextension
        active_markets = _count_active_markets(team)
        overextension = max(0, active_markets - structure.optimal_market_range_max)

        if overextension > 0:
            overextension_penalty = structure.overextension_effectiveness_penalty * overextension
            overextension_penalty = min(D('0.30'), overextension_penalty)
        else:
            overextension_penalty = D('0')

        # Networked special: talent-dependent modifiers
        innovation_mod = structure.innovation_modifier
        hq_mod = structure.hq_talent_effectiveness_modifier
        local_mod = structure.local_talent_effectiveness_modifier
        coord_mod = structure.coordination_efficiency

        if structure.code == 'networked':
            avg_talent = _get_avg_talent_level(team, context.round_number)
            if avg_talent < D('3.0'):
                # Chaos without talent — 20% degradation
                degradation = D('0.80')
                hq_mod = hq_mod * degradation
                local_mod = local_mod * degradation
                innovation_mod = innovation_mod * degradation
                coord_mod = coord_mod * degradation
            elif avg_talent > D('4.0'):
                # Talent amplifies the model
                innovation_mod = D('1.35')

        effective_factor = disruption_factor * (D('1') - overextension_penalty)

        context.org_modifiers[team.id] = {
            'hq_modifier': (hq_mod * effective_factor).quantize(D('0.01')),
            'local_modifier': (local_mod * effective_factor).quantize(D('0.01')),
            'innovation_modifier': (innovation_mod * effective_factor).quantize(D('0.01')),
            'coordination_modifier': (coord_mod * effective_factor).quantize(D('0.01')),
            'speed_modifier': structure.decision_speed_modifier,
        }

    context.log.append('CC-32B: Org structure modifiers applied')


def calculate_org_structure_costs(context):
    """
    CC-32B: Calculate organizational structure overhead costs.
    Called during Step 11 (costs).
    """
    if not hasattr(context, 'org_structure_costs'):
        context.org_structure_costs = {}

    for team in context.teams:
        try:
            org = TeamOrganizationalStructure.objects.get(
                game=context.game, team=team,
            )
        except TeamOrganizationalStructure.DoesNotExist:
            context.org_structure_costs[team.id] = D('0')
            continue

        structure = org.current_structure
        if not structure:
            context.org_structure_costs[team.id] = D('0')
            continue

        active_markets = _count_active_markets(team)
        overextension = max(0, active_markets - structure.optimal_market_range_max)

        base = structure.base_overhead_per_round
        coordination = structure.per_market_coordination_cost * active_markets
        overextension_cost = structure.overextension_cost_per_market * overextension

        total = base + coordination + overextension_cost
        context.org_structure_costs[team.id] = total

    context.log.append('CC-32B: Org structure costs calculated')
