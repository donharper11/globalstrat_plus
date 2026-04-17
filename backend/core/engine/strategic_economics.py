"""
CC-24: Strategic Investment Economic Effects.

Helpers for calculating and recording economic impacts of ESG, talent,
partnerships, and plant ownership. Called from costs.py and advance_round.py.
"""
from decimal import Decimal, ROUND_HALF_UP

from core.models.team_state import TeamStrategyFeatureLevel, TeamPartnership, TeamPlant
from core.models.cc24_models import ESGEconomicImpact, TalentEconomicImpact, PartnershipEconomicImpact
from core.engine.talent import get_talent_level
from core.engine.utils import get_config, clamp

D = Decimal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_esg_level(team, round_number):
    """Get the team's esg_track_record strategy feature level."""
    sl = TeamStrategyFeatureLevel.objects.filter(
        team=team,
        feature__code='esg_track_record',
        market=None,
        round_number=round_number,
    ).first()
    return float(sl.current_level) if sl else 0.0


def get_partnership_type(partnership):
    """
    Determine partnership type from strategy_option code.
    Returns: 'distribution', 'technology', 'government_regulatory', 'brand_ambassador', or 'unknown'.
    """
    code = partnership.strategy_option.code if partnership.strategy_option else ''
    type_map = {
        'distribution_partner': 'distribution',
        'technology_partner': 'technology',
        'govt_advisor': 'government_regulatory',
        'brand_ambassador': 'brand_ambassador',
    }
    return type_map.get(code, 'unknown')


# ---------------------------------------------------------------------------
# Part A: ESG Economic Effects (used by costs.py)
# ---------------------------------------------------------------------------

def calculate_esg_tariff_reduction(team, market, base_tariff_rate, context):
    """
    Calculate ESG-based tariff rate reduction.
    Returns (effective_tariff_rate, reduction_amount, esg_level).
    """
    esg_level = get_esg_level(team, context.round_number)

    if esg_level < 4:
        return float(base_tariff_rate), 0.0, esg_level

    # Per-market multiplier (EU rewards most, APAC least)
    market_code = getattr(market, 'code', '') or ''
    market_mult = get_config(
        context.scenario,
        f'esg_tariff_reduction_multiplier_{market_code}',
        default=0.5,
    )

    # Tiered reduction
    if esg_level >= 8:
        base_reduction_pct = 0.60
    elif esg_level >= 6:
        base_reduction_pct = 0.40
    elif esg_level >= 4:
        base_reduction_pct = 0.15
    else:
        base_reduction_pct = 0.0

    reduction_pct = base_reduction_pct * market_mult
    reduction = float(base_tariff_rate) * reduction_pct
    effective_rate = max(float(base_tariff_rate) - reduction, 0.0)

    return effective_rate, reduction, esg_level


def calculate_esg_tax_reduction(team, market, base_tax_rate, context):
    """
    Calculate ESG-based tax rate reduction.
    Returns (effective_tax_rate, reduction_amount, esg_level).
    """
    esg_level = get_esg_level(team, context.round_number)

    if esg_level < 3:
        return float(base_tax_rate), 0.0, esg_level

    market_code = getattr(market, 'code', '') or ''
    market_mult = get_config(
        context.scenario,
        f'esg_tax_incentive_multiplier_{market_code}',
        default=0.5,
    )

    # Tiered percentage-point reduction
    if esg_level >= 7:
        base_pp_reduction = 0.04
    elif esg_level >= 5:
        base_pp_reduction = 0.02
    elif esg_level >= 3:
        base_pp_reduction = 0.01
    else:
        base_pp_reduction = 0.0

    pp_reduction = base_pp_reduction * market_mult
    effective_rate = max(float(base_tax_rate) - pp_reduction, 0.05)  # Floor 5%

    return effective_rate, float(base_tax_rate) - effective_rate, esg_level


def calculate_esg_cogs_modifier(team, context):
    """
    Sustainability investment reduces COGS through supply chain efficiency.
    Returns Decimal multiplier (e.g. 0.94 = 6% reduction).
    """
    esg_level = get_esg_level(team, context.round_number)

    if esg_level >= 8:
        return D('0.94')  # 6% COGS reduction
    elif esg_level >= 6:
        return D('0.97')  # 3% COGS reduction
    elif esg_level >= 4:
        return D('0.99')  # 1% COGS reduction
    else:
        return D('1.00')  # No benefit


# ---------------------------------------------------------------------------
# Part C: Partnership Economic Effects (used by costs.py)
# ---------------------------------------------------------------------------

def get_partnership_effects(team, market, context):
    """
    Calculate economic effects of active partnerships in a market.
    Returns dict of effect_type → value.

    CC-32D: Benefits are scaled by alliance satisfaction (benefit_delivery_pct).
    """
    effects = {}
    partnerships = TeamPartnership.objects.filter(
        team=team, market=market, status='active',
    ).select_related('strategy_option')

    for p in partnerships:
        ptype = get_partnership_type(p)

        # CC-32D: Look up benefit_delivery_pct from alliance state
        delivery_pct = _get_benefit_delivery_pct(team, market, p, context)

        if ptype == 'distribution':
            effects['logistics_cost_reduction'] = D('0.10') * delivery_pct
            effects['_distribution_partnership'] = p

        elif ptype == 'technology':
            effects['rd_cost_reduction'] = D('0.08') * delivery_pct
            effects['_technology_partnership'] = p

        elif ptype == 'government_regulatory':
            effects['tariff_reduction'] = D('0.02') * delivery_pct
            effects['admin_cost_reduction'] = D('0.15') * delivery_pct
            effects['_govt_partnership'] = p

        elif ptype == 'brand_ambassador':
            effects['promotion_effectiveness'] = D('0.15') * delivery_pct
            effects['_brand_partnership'] = p

    return effects


def _get_benefit_delivery_pct(team, market, partnership, context):
    """Get alliance benefit delivery percentage. Returns D('1.00') if no alliance state."""
    try:
        from core.models.cc32d_models import AlliancePartnerProfile, TeamAllianceState
        code = partnership.strategy_option.code if partnership.strategy_option else ''
        alliance = TeamAllianceState.objects.filter(
            game=context.game,
            team=team,
            partner_profile__partnership_code=code,
            market=market,
        ).exclude(status='DISSOLVED').first()
        if alliance:
            return alliance.benefit_delivery_pct
    except Exception:
        pass
    return D('1.00')


# ---------------------------------------------------------------------------
# Part E: Record economic impacts (called from advance_round.py)
# ---------------------------------------------------------------------------

def record_esg_impacts(context):
    """Record all ESG economic impact records for this round."""
    for team in context.teams:
        esg_level = get_esg_level(team, context.round_number)
        if esg_level < 3:
            continue

        # Tariff savings
        tariff_savings = context.esg_savings.get(team.id, {}).get('tariff', {})
        for market_id, info in tariff_savings.items():
            if info['savings'] > 0:
                ESGEconomicImpact.objects.update_or_create(
                    game=context.game, team=team,
                    round_number=context.round_number,
                    market_id=market_id, benefit_type='tariff_reduction',
                    defaults={
                        'base_value': D(str(info['base_tariff_cost'])),
                        'effective_value': D(str(info['effective_tariff_cost'])),
                        'savings': D(str(info['savings'])),
                        'esg_level': D(str(esg_level)),
                        'description': (
                            f"Tariff reduced from {info['base_rate']:.1%} to "
                            f"{info['effective_rate']:.1%} (ESG level {esg_level:.1f})"
                        ),
                    },
                )

        # Tax savings
        tax_savings = context.esg_savings.get(team.id, {}).get('tax', {})
        for market_id, info in tax_savings.items():
            if info['savings'] > 0:
                ESGEconomicImpact.objects.update_or_create(
                    game=context.game, team=team,
                    round_number=context.round_number,
                    market_id=market_id, benefit_type='tax_incentive',
                    defaults={
                        'base_value': D(str(info['base_tax'])),
                        'effective_value': D(str(info['effective_tax'])),
                        'savings': D(str(info['savings'])),
                        'esg_level': D(str(esg_level)),
                        'description': (
                            f"Tax rate reduced from {info['base_rate']:.1%} to "
                            f"{info['effective_rate']:.1%} (ESG level {esg_level:.1f})"
                        ),
                    },
                )

        # COGS savings
        cogs_savings = context.esg_savings.get(team.id, {}).get('cogs_savings', D('0'))
        if cogs_savings > 0:
            ESGEconomicImpact.objects.update_or_create(
                game=context.game, team=team,
                round_number=context.round_number,
                market=None, benefit_type='cogs_reduction',
                defaults={
                    'base_value': context.esg_savings[team.id].get('cogs_base', D('0')),
                    'effective_value': context.esg_savings[team.id].get('cogs_effective', D('0')),
                    'savings': cogs_savings,
                    'esg_level': D(str(esg_level)),
                    'description': f"Supply chain efficiency (ESG level {esg_level:.1f})",
                },
            )

    context.log.append('ESG economic impacts recorded')


def record_talent_impacts(context):
    """Record talent economic impact records for this round."""
    for team in context.teams:
        rd_talent = get_talent_level(team, 'rd', context.round_number)
        commercial_talent = get_talent_level(team, 'commercial', context.round_number)
        ops_talent = get_talent_level(team, 'operations', context.round_number)

        # R&D modifier: 5% cost reduction per level above 3
        rd_modifier = D('1.0') - (rd_talent - D('3')) * D('0.05')
        rd_modifier = clamp(rd_modifier, D('0.50'), D('1.15'))

        # Ops modifier: 4% COGS reduction per level above 3 (already applied in costs.py)
        ops_modifier = D('1.0') - (ops_talent - D('3')) * D('0.04')
        ops_modifier = clamp(ops_modifier, D('0.70'), D('1.15'))

        # Commercial modifier: 8% campaign effectiveness per level above 3
        commercial_modifier = D('1.0') + (commercial_talent - D('3')) * D('0.08')
        commercial_modifier = clamp(commercial_modifier, D('0.50'), D('2.00'))

        opex = context.opex.get(team.id, {})
        rd_expense = opex.get('rd_expense', D('0'))
        total_revenue = opex.get('total_revenue', D('0'))

        # Calculate savings vs baseline (level 3 = modifier 1.0)
        if rd_modifier < D('1.0') and rd_modifier > D('0'):
            rd_baseline = rd_expense / rd_modifier
            rd_savings = rd_baseline - rd_expense
        else:
            rd_savings = D('0')

        # COGS savings tracked in context from costs.py
        cogs_savings = context.talent_savings.get(team.id, {}).get('cogs_savings', D('0'))

        # Campaign uplift estimate
        if commercial_modifier > D('1.0'):
            campaign_uplift = total_revenue * (commercial_modifier - D('1.0')) / commercial_modifier
        else:
            campaign_uplift = D('0')

        # Talent cost from opex (already calculated)
        talent_cost = context.talent_savings.get(team.id, {}).get('talent_cost', D('0'))

        total_benefit = max(rd_savings, D('0')) + max(cogs_savings, D('0')) + max(campaign_uplift, D('0'))

        TalentEconomicImpact.objects.update_or_create(
            game=context.game, team=team, round_number=context.round_number,
            defaults={
                'rd_talent_level': rd_talent,
                'rd_cost_modifier': rd_modifier,
                'rd_cost_savings': max(rd_savings, D('0')),
                'commercial_talent_level': commercial_talent,
                'campaign_effectiveness_modifier': commercial_modifier,
                'campaign_revenue_uplift': max(campaign_uplift, D('0')),
                'operations_talent_level': ops_talent,
                'cogs_modifier': ops_modifier,
                'cogs_savings': max(cogs_savings, D('0')),
                'total_talent_cost': talent_cost,
                'total_talent_benefit': total_benefit,
                'net_talent_roi': total_benefit - talent_cost,
            },
        )

    context.log.append('Talent economic impacts recorded')


def record_partnership_impacts(context):
    """Record partnership economic impact records for this round."""
    partnership_savings = getattr(context, 'partnership_savings', {})

    for team in context.teams:
        team_savings = partnership_savings.get(team.id, {})
        for partnership_id, benefits in team_savings.items():
            try:
                partnership = TeamPartnership.objects.get(id=partnership_id)
            except TeamPartnership.DoesNotExist:
                continue

            for benefit_type, info in benefits.items():
                if benefit_type.startswith('_'):
                    continue
                PartnershipEconomicImpact.objects.update_or_create(
                    game=context.game, team=team,
                    round_number=context.round_number,
                    partnership=partnership,
                    benefit_type=benefit_type,
                    defaults={
                        'benefit_amount': D(str(info.get('amount', 0))),
                        'description': info.get('description', ''),
                    },
                )

    context.log.append('Partnership economic impacts recorded')


# ---------------------------------------------------------------------------
# Part A5: ESG Event Protection
# ---------------------------------------------------------------------------

def calculate_event_esg_modifier(team, event_instance, context):
    """
    Calculate ESG-based protection/amplification for event impacts.
    Returns a multiplier (< 1.0 = protection, > 1.0 = amplification).
    """
    esg_level = get_esg_level(team, context.round_number)
    template = event_instance.event_template

    # Check event category and name for ESG relevance
    category = getattr(template, 'category', '') or ''
    name = (template.name or '').lower()

    multiplier = 1.0
    reason = ''

    if category == 'regulatory' or 'regulat' in name:
        if 'carbon' in name or 'environment' in name or 'green' in name or 'emission' in name:
            if esg_level >= 7:
                multiplier = 0.3
                reason = 'High sustainability shields from environmental regulation'
            elif esg_level >= 5:
                multiplier = 0.6
                reason = 'Moderate sustainability partially shields'
            elif esg_level < 3:
                multiplier = 1.5
                reason = 'Low sustainability amplifies regulatory impact'

        if 'compliance' in name or 'governance' in name:
            if esg_level >= 7:
                multiplier = min(multiplier, 0.2)
                reason = 'Strong governance prepared for compliance events'
            elif esg_level < 4:
                multiplier = max(multiplier, 1.3)
                reason = 'Weak governance increases compliance vulnerability'

    if category == 'social' or 'social' in name or 'labor' in name:
        if esg_level >= 6:
            multiplier = min(multiplier, 0.5)
            reason = 'Social investment provides community goodwill'

    return multiplier, reason
