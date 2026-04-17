"""
Engine Step 11: Cost Calculations (COGS, logistics, tariffs, opex, interest, tax, inventory).
From 03-engine-logic.md Sections 10A-10F.
CC-24: ESG, talent, and partnership economic effects wired into costs.
"""
import math
from decimal import Decimal, ROUND_HALF_UP

from core.models.decisions import (
    DecisionMarketing, DecisionSubmission, DecisionRDInvestment,
    DecisionPlatformDevelopment, DecisionMarketEntry, DecisionPartnership,
    DecisionESG, DecisionAcquisition,
    DecisionPlant,
)
from core.models.team_state import TeamPlant, TeamMarketPresence, TeamPartnership
from core.models.cc31_models import CulturalDistanceMatrix, TeamGovernanceCommitment
from core.models.results import ActiveModifier
from core.models.scenario import ScenarioConfig
from core.engine.utils import get_config
from core.engine.strategic_economics import (
    calculate_esg_cogs_modifier,
    calculate_esg_tariff_reduction,
    calculate_esg_tax_reduction,
    get_partnership_effects,
)

D = Decimal


def calculate_cogs(context):
    """
    For each team, product, market: base unit cost × learning curve × units produced.
    """
    scenario = context.scenario

    base_cost_cfg = D(str(get_config(scenario, 'base_unit_cost', default=50.0)))
    learning_factor = get_config(scenario, 'learning_curve_factor', default=0.05)

    context.cogs = {}  # (team_id, product_id, market_id) → dict

    # CC-24: Initialize ESG/talent savings tracking
    if not hasattr(context, 'esg_savings'):
        context.esg_savings = {}
    if not hasattr(context, 'talent_savings'):
        context.talent_savings = {}

    # Pre-compute per-team ESG COGS modifiers
    _esg_cogs_mods = {}
    for team in context.teams:
        _esg_cogs_mods[team.id] = calculate_esg_cogs_modifier(team, context)

    for key, rev in context.revenue.items():
        team_id, product_id, market_id = key
        units_produced = int(rev['units_produced'])

        if units_produced == 0:
            context.cogs[key] = {
                'unit_cost': D('0'), 'total_cogs': D('0'),
                'units_produced': 0,
            }
            continue

        # Get product/platform info
        from core.models.team_state import TeamProduct
        try:
            product = TeamProduct.objects.select_related(
                'team_platform__platform_generation',
            ).get(id=product_id)
        except TeamProduct.DoesNotExist:
            context.cogs[key] = {
                'unit_cost': D('0'), 'total_cogs': D('0'),
                'units_produced': units_produced,
            }
            continue

        gen_order = product.team_platform.platform_generation.generation_order
        gen_factor = D('1') + D(str(gen_order - 1)) * D('0.20')

        # Get production source market
        submission = DecisionSubmission.objects.filter(
            team_id=team_id,
            round__round_number=context.round_number,
            round__game=context.game,
        ).first()
        mkt_dec = None
        if submission:
            mkt_dec = DecisionMarketing.objects.filter(
                submission=submission,
                team_product_id=product_id,
                market_id=market_id,
            ).first()

        from core.models.scenario import MarketDefinition
        if mkt_dec and mkt_dec.production_source_market_id:
            try:
                source_market = MarketDefinition.objects.get(
                    id=mkt_dec.production_source_market_id,
                )
                location_cost = source_market.base_manufacturing_cost
            except MarketDefinition.DoesNotExist:
                location_cost = D('1')
        else:
            location_cost = D('1')

        base_unit_cost = base_cost_cfg * gen_factor * location_cost

        # Contract manufacturing premium
        sales_market = MarketDefinition.objects.filter(id=market_id).first()
        has_own_plant = TeamPlant.objects.filter(
            team_id=team_id, market_id=mkt_dec.production_source_market_id if mkt_dec else market_id,
            status='operational',
        ).exists() if mkt_dec else False

        if not has_own_plant and sales_market and sales_market.contract_mfg_available:
            base_unit_cost *= sales_market.contract_mfg_cost_multiplier

        # Learning curve
        plant = TeamPlant.objects.filter(
            team_id=team_id,
            market_id=mkt_dec.production_source_market_id if mkt_dec else market_id,
            status='operational',
        ).first()
        cumulative = plant.cumulative_production if plant else 0
        if cumulative > 0:
            learning_discount = D(str(
                1 - learning_factor * math.log2(max(cumulative / 1000, 1))
            ))
            learning_discount = max(learning_discount, D('0.70'))
        else:
            learning_discount = D('1')

        # CC-16: Operations talent efficiency modifier
        from core.engine.talent import get_talent_level
        from core.engine.utils import clamp as _clamp
        from core.models.core import Team as _Team
        _team = _Team.objects.get(id=team_id)
        ops_talent = get_talent_level(_team, 'operations', context.round_number)
        ops_efficiency = _clamp(
            D('1.0') - (ops_talent - D('3')) * D('0.04'),
            D('0.70'), D('1.15'),
        )

        # CC-24: ESG supply chain efficiency modifier
        esg_cogs_mod = _esg_cogs_mods.get(team_id, D('1.00'))

        effective_unit_cost = (base_unit_cost * learning_discount * ops_efficiency * esg_cogs_mod).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )
        total_cogs = (D(str(units_produced)) * effective_unit_cost).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )

        # CC-24: Track COGS savings from ESG and talent for impact reporting
        baseline_unit_cost = (base_unit_cost * learning_discount).quantize(D('0.01'), rounding=ROUND_HALF_UP)
        baseline_cogs = D(str(units_produced)) * baseline_unit_cost
        esg_only_cost = (base_unit_cost * learning_discount * esg_cogs_mod).quantize(D('0.01'), rounding=ROUND_HALF_UP)

        if team_id not in context.esg_savings:
            context.esg_savings[team_id] = {}
        esg_cogs_saving = baseline_cogs - D(str(units_produced)) * esg_only_cost
        context.esg_savings[team_id]['cogs_savings'] = (
            context.esg_savings[team_id].get('cogs_savings', D('0')) + max(esg_cogs_saving, D('0'))
        )
        context.esg_savings[team_id]['cogs_base'] = (
            context.esg_savings[team_id].get('cogs_base', D('0')) + baseline_cogs
        )
        context.esg_savings[team_id]['cogs_effective'] = (
            context.esg_savings[team_id].get('cogs_effective', D('0')) + total_cogs
        )

        # Track talent COGS savings (ops_efficiency vs baseline 1.0)
        if team_id not in context.talent_savings:
            context.talent_savings[team_id] = {}
        talent_only_cogs = D(str(units_produced)) * (base_unit_cost * learning_discount * ops_efficiency).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )
        talent_cogs_saving = baseline_cogs - talent_only_cogs
        context.talent_savings[team_id]['cogs_savings'] = (
            context.talent_savings[team_id].get('cogs_savings', D('0')) + max(talent_cogs_saving, D('0'))
        )

        context.cogs[key] = {
            'unit_cost': effective_unit_cost,
            'total_cogs': total_cogs,
            'units_produced': units_produced,
        }

        # Update cumulative production for learning curve tracking
        if plant:
            plant.cumulative_production += units_produced
            plant.save()

    context.log.append('COGS calculated')


def calculate_logistics_tariffs(context):
    """
    Cross-border: logistics = units × base cost × entry_mode multiplier.
    Tariff = product_value × effective_tariff_rate if tariff_applies.
    CC-24: ESG tariff reduction, partnership logistics/tariff reduction, plant visibility.
    """
    scenario = context.scenario
    base_logistics = D(str(get_config(scenario, 'logistics_base_cost_per_unit', default=5.0)))
    current_round = context.round_number

    context.logistics = {}  # (team_id, product_id, market_id) → dict

    # CC-24: Initialize savings tracking dicts
    if not hasattr(context, 'esg_savings'):
        context.esg_savings = {}
    if not hasattr(context, 'partnership_savings'):
        context.partnership_savings = {}

    # CC-24: Pre-compute per-team-market partnership effects
    _partnership_cache = {}
    for team in context.teams:
        from core.models.scenario import MarketDefinition as _MD
        for mkt in _MD.objects.filter(scenario=scenario):
            _partnership_cache[(team.id, mkt.id)] = get_partnership_effects(team, mkt, context)

    for key, rev in context.revenue.items():
        team_id, product_id, market_id = key

        submission = DecisionSubmission.objects.filter(
            team_id=team_id,
            round__round_number=current_round,
            round__game=context.game,
        ).first()
        mkt_dec = None
        if submission:
            mkt_dec = DecisionMarketing.objects.filter(
                submission=submission,
                team_product_id=product_id,
                market_id=market_id,
            ).first()

        source_market_id = mkt_dec.production_source_market_id if mkt_dec else market_id

        if source_market_id == market_id:
            # Local production — no tariff, minimal logistics
            context.logistics[key] = {
                'logistics_cost': D('0'), 'tariff_cost': D('0'),
            }
            continue

        units_sold = rev['units_sold']

        # Get entry mode for logistics multiplier
        presence = TeamMarketPresence.objects.filter(
            team_id=team_id, market_id=market_id, status='active',
        ).select_related('entry_mode').first()

        logistics_multiplier = D('1')
        tariff_applies = True
        if presence and presence.entry_mode:
            logistics_multiplier = presence.entry_mode.logistics_cost_multiplier
            tariff_applies = presence.entry_mode.tariff_applies

        logistics_cost = (units_sold * base_logistics * logistics_multiplier).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )

        # Apply cost modifiers from events
        cost_mods = ActiveModifier.objects.filter(
            game=context.game,
            modifier_type='cost',
            target_market_id=market_id,
            target_field='logistics_cost',
            started_round__lte=current_round,
        ).exclude(expires_round__lte=current_round)
        for mod in cost_mods:
            logistics_cost = (logistics_cost * (D('1') + mod.modifier_value)).quantize(
                D('0.01'), rounding=ROUND_HALF_UP,
            )

        # CC-24: Partnership logistics reduction
        p_effects = _partnership_cache.get((team_id, market_id), {})
        logistics_before_partnership = logistics_cost
        if 'logistics_cost_reduction' in p_effects:
            reduction = p_effects['logistics_cost_reduction']
            logistics_cost = (logistics_cost * (D('1') - reduction)).quantize(
                D('0.01'), rounding=ROUND_HALF_UP,
            )
            # Track partnership savings
            p_obj = p_effects.get('_distribution_partnership')
            if p_obj:
                if team_id not in context.partnership_savings:
                    context.partnership_savings[team_id] = {}
                if p_obj.id not in context.partnership_savings[team_id]:
                    context.partnership_savings[team_id][p_obj.id] = {}
                prev = context.partnership_savings[team_id][p_obj.id].get(
                    'logistics_savings', {'amount': 0, 'description': ''},
                )
                saved = logistics_before_partnership - logistics_cost
                context.partnership_savings[team_id][p_obj.id]['logistics_savings'] = {
                    'amount': float(prev['amount']) + float(saved),
                    'description': f'Distribution partnership: {float(reduction)*100:.0f}% logistics reduction',
                }

        tariff_cost = D('0')
        if tariff_applies:
            mkt_state = context.markets.get(market_id)
            base_tariff_rate = D(str(
                mkt_state.effective_tariff_rate if mkt_state else 0,
            ))
            product_value = units_sold * rev['retail_price']

            # CC-24: ESG tariff reduction
            from core.models.core import Team as _Team
            _team = _Team.objects.get(id=team_id)
            from core.models.scenario import MarketDefinition as _MD2
            _market = _MD2.objects.get(id=market_id)

            effective_rate, esg_reduction, esg_level = calculate_esg_tariff_reduction(
                _team, _market, base_tariff_rate, context,
            )
            effective_tariff_rate = D(str(effective_rate))

            # CC-24: Government partnership tariff reduction
            if 'tariff_reduction' in p_effects:
                govt_reduction = p_effects['tariff_reduction']
                effective_tariff_rate = max(effective_tariff_rate - govt_reduction, D('0'))
                p_obj = p_effects.get('_govt_partnership')
                if p_obj:
                    govt_saved = product_value * govt_reduction
                    if team_id not in context.partnership_savings:
                        context.partnership_savings[team_id] = {}
                    if p_obj.id not in context.partnership_savings[team_id]:
                        context.partnership_savings[team_id][p_obj.id] = {}
                    prev = context.partnership_savings[team_id][p_obj.id].get(
                        'tariff_savings', {'amount': 0, 'description': ''},
                    )
                    context.partnership_savings[team_id][p_obj.id]['tariff_savings'] = {
                        'amount': float(prev['amount']) + float(govt_saved),
                        'description': 'Government partnership: 2pp tariff reduction',
                    }

            tariff_cost = (product_value * effective_tariff_rate).quantize(
                D('0.01'), rounding=ROUND_HALF_UP,
            )

            # CC-24: Track ESG tariff savings
            if esg_reduction > 0:
                base_tariff_cost = float(product_value * base_tariff_rate)
                effective_tariff_cost = float(tariff_cost)
                if team_id not in context.esg_savings:
                    context.esg_savings[team_id] = {}
                if 'tariff' not in context.esg_savings[team_id]:
                    context.esg_savings[team_id]['tariff'] = {}
                prev_t = context.esg_savings[team_id]['tariff'].get(market_id, {
                    'base_tariff_cost': 0, 'effective_tariff_cost': 0, 'savings': 0,
                    'base_rate': float(base_tariff_rate), 'effective_rate': effective_rate,
                })
                esg_tariff_saving = float(product_value) * esg_reduction
                context.esg_savings[team_id]['tariff'][market_id] = {
                    'base_tariff_cost': prev_t['base_tariff_cost'] + base_tariff_cost,
                    'effective_tariff_cost': prev_t['effective_tariff_cost'] + effective_tariff_cost,
                    'savings': prev_t['savings'] + esg_tariff_saving,
                    'base_rate': float(base_tariff_rate),
                    'effective_rate': effective_rate,
                }

        context.logistics[key] = {
            'logistics_cost': logistics_cost,
            'tariff_cost': tariff_cost,
        }

    context.log.append('Logistics & tariffs calculated (CC-24: ESG + partnership effects)')


def calculate_operating_expenses(context):
    """
    Aggregate per team: R&D, marketing, strategy, research, admin overhead.
    """
    scenario = context.scenario
    current_round = context.round_number
    admin_fixed = D(str(get_config(scenario, 'admin_overhead_fixed', default=500000.0)))
    admin_pct = D(str(get_config(scenario, 'admin_overhead_pct', default=0.03)))
    capitalize_platform = get_config(
        scenario, 'capitalize_platform_development', default=False, cast_type=bool,
    )

    context.opex = {}  # team_id → dict

    for team in context.teams:
        submission = DecisionSubmission.objects.filter(
            team=team, round__round_number=current_round, round__game=context.game,
        ).first()

        rd_expense = D('0')
        marketing_expense = D('0')
        strategy_expense = D('0')

        if submission:
            # R&D expense
            for inv in submission.rd_investments.all():
                rd_expense += inv.amount
            if not capitalize_platform:
                for dev in submission.platform_developments.all():
                    rd_expense += dev.committed_cost

            # Marketing expense
            try:
                sales_rep_cost = Decimal(ScenarioConfig.objects.get(
                    scenario=context.scenario, config_key='sales_rep_cost_per_round',
                ).config_value)
            except ScenarioConfig.DoesNotExist:
                sales_rep_cost = Decimal('100000')

            for md in submission.marketing_decisions.all():
                rep_cost = sales_rep_cost * md.sales_team_count
                marketing_expense += md.promotion_budget + rep_cost

            # Strategy expense: entry costs + exit costs + partnerships + ESG + acquisitions
            for entry in submission.market_entries.all():
                if entry.action == 'enter':
                    strategy_expense += entry.initial_investment
                elif entry.action == 'exit':
                    # Exit cost = 20% of initial investment as write-down
                    exit_cost = (entry.initial_investment * D('0.20')).quantize(
                        D('0.01'), rounding=ROUND_HALF_UP,
                    )
                    strategy_expense += exit_cost

            # Active partnerships (annual investment)
            for p in TeamPartnership.objects.filter(team=team, status='active'):
                strategy_expense += p.annual_investment

            # ESG
            try:
                esg = submission.esg
                if esg:
                    strategy_expense += esg.environmental_investment + esg.social_investment
            except Exception:
                pass

            # CC-31J: Governance commitment costs (set by strategy_effects)
            governance_cost = getattr(team, '_governance_cost', None)
            if governance_cost:
                strategy_expense += governance_cost

            # Acquisitions (base acquisition cost) — only charge if actually fulfilled
            from core.models.team_state import TeamAcquisition as _TeamAcqCost
            for acq in submission.acquisitions.select_related('acquisition_target').all():
                if _TeamAcqCost.objects.filter(
                    team=team, acquisition_target=acq.acquisition_target,
                ).exists():
                    strategy_expense += acq.acquisition_target.base_acquisition_cost

            # Integration costs for ongoing acquisitions (CC-20)
            from core.models.team_state import TeamAcquisition as _TeamAcq
            for tacq in _TeamAcq.objects.filter(
                team=team, integration_complete=False,
            ).select_related('acquisition_target'):
                strategy_expense += tacq.acquisition_target.integration_cost_per_round

            # Plant maintenance for operational plants
            from core.models.scenario import PlatformGenerationDefinition
            for plant in TeamPlant.objects.filter(team=team, status='operational'):
                # Use annual_maintenance_cost from platform gen (simplified)
                strategy_expense += D('0')  # Maintenance handled at scenario level

            # CC-16: Talent/HR costs
            from core.models.talent import DecisionTalent, TeamTalentState
            try:
                talent_decision = submission.talent
            except DecisionTalent.DoesNotExist:
                talent_decision = None

            if talent_decision:
                talent_cost = D('0')
                for prefix in ['rd', 'commercial', 'operations']:
                    hc = getattr(talent_decision, f'{prefix}_headcount')
                    sl = getattr(talent_decision, f'{prefix}_salary_level')
                    training = D(str(getattr(talent_decision, f'{prefix}_training_budget')))

                    salary_base = {
                        1: 15000, 2: 22500, 3: 30000, 4: 40000, 5: 55000,
                    }[sl]
                    pool_salary = D(str(hc * salary_base))

                    prev_state = TeamTalentState.objects.filter(
                        team=team, talent_pool=prefix,
                        round_number=current_round - 1,
                    ).first()
                    prev_hc = prev_state.headcount if prev_state else 0
                    new_hires = max(hc - prev_hc, 0)
                    layoffs = max(prev_hc - hc, 0)
                    recruitment_cost = D(str(new_hires)) * D('10000')
                    layoff_cost = D(str(layoffs)) * D('20000')

                    talent_cost += pool_salary + training + recruitment_cost + layoff_cost

                strategy_expense += talent_cost

                # CC-24: Track talent cost for impact reporting
                if not hasattr(context, 'talent_savings'):
                    context.talent_savings = {}
                if team.id not in context.talent_savings:
                    context.talent_savings[team.id] = {}
                context.talent_savings[team.id]['talent_cost'] = talent_cost

        # Total revenue for this team
        total_team_revenue = D('0')
        for (t_id, m_id), mr in context.market_revenue.items():
            if t_id == team.id:
                total_team_revenue += mr['home_revenue']

        admin_overhead = admin_fixed + (total_team_revenue * admin_pct).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )

        # Capex (plant construction) - tracked separately for balance sheet
        capex = D('0')
        if submission:
            for pd in submission.plant_decisions.all():
                if pd.action == 'build':
                    market = pd.market
                    if market.plant_build_cost:
                        capex += market.plant_build_cost

        # CC-32B: Add organizational structure overhead costs
        org_overhead = D('0')
        if hasattr(context, 'org_structure_costs'):
            org_overhead = context.org_structure_costs.get(team.id, D('0'))
        strategy_expense += org_overhead

        context.opex[team.id] = {
            'rd_expense': rd_expense,
            'marketing_expense': marketing_expense,
            'strategy_expense': strategy_expense,
            'research_expense': D('0'),
            'admin_overhead': admin_overhead,
            'total_revenue': total_team_revenue,
            'capex': capex,
        }

    context.log.append('Operating expenses calculated')


def calculate_interest(context):
    """Interest = outstanding_debt × debt_interest_rate."""
    scenario = context.scenario
    interest_rate = D(str(get_config(scenario, 'debt_interest_rate', default=0.06)))

    context.interest = {}  # team_id → Decimal

    for team in context.teams:
        outstanding_debt = team.total_debt
        interest = (outstanding_debt * interest_rate).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )
        context.interest[team.id] = interest

    context.log.append('Interest calculated')


def calculate_tax(context):
    """
    Per market: if market profit > 0, tax = profit × market.tax_rate.
    Losses in one market do NOT offset profits in another.
    CC-24: ESG tax incentives reduce effective tax rate.
    """
    scenario = context.scenario
    allow_consolidation = get_config(
        scenario, 'allow_tax_consolidation', default=False, cast_type=bool,
    )

    context.tax = {}              # team_id → Decimal
    context.market_profit = {}    # (team_id, market_id) → Decimal
    context.tax_structure_savings = {}   # CC-32C: team_id → Decimal
    context.tax_structure_maintenance = {}  # CC-32C: team_id → Decimal

    # CC-24: Initialize ESG savings tracking
    if not hasattr(context, 'esg_savings'):
        context.esg_savings = {}

    # CC-32C: Load tax structures for all teams
    from core.models.cc32c_models import TeamTaxStructure
    team_tax_structures = {}
    for tts in TeamTaxStructure.objects.filter(
        game=context.game,
    ).select_related('current_structure'):
        team_tax_structures[tts.team_id] = tts

    for team in context.teams:
        total_tax = D('0')
        total_tax_structure_savings = D('0')

        # CC-32C: Get team's tax structure
        tts = team_tax_structures.get(team.id)
        structure = tts.current_structure if tts else None

        # Gather total revenue and per-market revenue for opex allocation
        team_total_rev = D('0')
        market_revenues = {}  # m_id → revenue
        for (t_id, m_id), mr in context.market_revenue.items():
            if t_id != team.id:
                continue
            market_revenues[m_id] = mr['home_revenue']
            team_total_rev += mr['home_revenue']

        # Get total opex (R&D, marketing, strategy, research, admin, interest)
        # to allocate against market profits for tax purposes
        opex = context.opex.get(team.id, {})
        total_opex = (
            opex.get('rd_expense', D('0')) + opex.get('marketing_expense', D('0'))
            + opex.get('strategy_expense', D('0')) + opex.get('research_expense', D('0'))
            + opex.get('admin_overhead', D('0'))
        )
        interest = context.interest.get(team.id, D('0'))
        total_deductions = total_opex + interest

        # Calculate per-market taxable profit
        for (t_id, m_id), mr in context.market_revenue.items():
            if t_id != team.id:
                continue

            market = mr['market']
            market_rev = mr['home_revenue']

            # Direct costs for this team-market
            market_costs = D('0')
            for (rt, rp, rm), cogs_data in context.cogs.items():
                if rt == team.id and rm == m_id:
                    market_costs += cogs_data['total_cogs']
            for (rt, rp, rm), log_data in context.logistics.items():
                if rt == team.id and rm == m_id:
                    market_costs += log_data['logistics_cost'] + log_data['tariff_cost']

            # Allocate opex proportionally by revenue share
            if team_total_rev > 0:
                rev_share = market_rev / team_total_rev
            else:
                rev_share = D('1')
            allocated_opex = (total_deductions * rev_share).quantize(
                D('0.01'), rounding=ROUND_HALF_UP,
            )

            market_profit = market_rev - market_costs - allocated_opex
            context.market_profit[(team.id, m_id)] = market_profit

            if market_profit > 0:
                # CC-24: ESG tax incentive
                effective_rate, tax_reduction, esg_level = calculate_esg_tax_reduction(
                    team, market, market.tax_rate, context,
                )
                effective_tax_rate = D(str(effective_rate))

                # CC-32C: Apply tax structure reduction on foreign markets
                is_home = (m_id == getattr(team, 'home_market_id', None))
                if structure and not is_home:
                    struct_reduction = structure.effective_tax_reduction_pct
                    effective_tax_rate = max(D('0.05'), effective_tax_rate - struct_reduction)

                tax = (market_profit * effective_tax_rate).quantize(
                    D('0.01'), rounding=ROUND_HALF_UP,
                )
                base_tax = (market_profit * market.tax_rate).quantize(
                    D('0.01'), rounding=ROUND_HALF_UP,
                )
                total_tax += tax

                # CC-32C: Track tax structure savings (difference from ESG-only rate)
                if structure and not is_home and structure.effective_tax_reduction_pct > 0:
                    esg_only_tax = (market_profit * D(str(effective_rate))).quantize(
                        D('0.01'), rounding=ROUND_HALF_UP,
                    )
                    total_tax_structure_savings += max(D('0'), esg_only_tax - tax)

                # CC-24: Track ESG tax savings
                if tax_reduction > 0:
                    if team.id not in context.esg_savings:
                        context.esg_savings[team.id] = {}
                    if 'tax' not in context.esg_savings[team.id]:
                        context.esg_savings[team.id]['tax'] = {}
                    context.esg_savings[team.id]['tax'][m_id] = {
                        'base_tax': float(base_tax),
                        'effective_tax': float(tax),
                        'savings': float(base_tax - tax),
                        'base_rate': float(market.tax_rate),
                        'effective_rate': float(effective_tax_rate),
                    }
            else:
                # No tax on losses
                pass

        # CC-32C: Deduct maintenance cost and track savings
        maintenance = D('0')
        if structure:
            maintenance = structure.annual_maintenance_cost
        context.tax[team.id] = total_tax
        context.tax_structure_savings[team.id] = total_tax_structure_savings
        context.tax_structure_maintenance[team.id] = maintenance

        # CC-32C: Update cumulative savings on TeamTaxStructure
        if tts and structure:
            tts.cumulative_tax_savings = (tts.cumulative_tax_savings or D('0')) + total_tax_structure_savings
            tts.save(update_fields=['cumulative_tax_savings'])

    context.log.append('Tax calculated (CC-24: ESG, CC-32C: Tax structure)')


def calculate_inventory_costs(context):
    """
    Excess units = units_produced - units_sold.
    Inventory cost = excess × unit_cost × holding_cost_pct.
    """
    scenario = context.scenario
    holding_pct = D(str(get_config(scenario, 'inventory_holding_cost_pct', default=0.05)))

    context.inventory_costs = {}  # (team_id, product_id, market_id) → dict

    for key, rev in context.revenue.items():
        units_unsold = rev['units_unsold']
        cogs_data = context.cogs.get(key, {})
        unit_cost = cogs_data.get('unit_cost', D('0'))

        inv_cost = (units_unsold * unit_cost * holding_pct).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )
        inv_value = (units_unsold * unit_cost).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )

        context.inventory_costs[key] = {
            'units_unsold': units_unsold,
            'inventory_cost': inv_cost,
            'inventory_value': inv_value,
        }

    context.log.append('Inventory costs calculated')


def calculate_retirement_costs(context):
    """
    Products retired this round incur costs for remaining inventory.
    Unsold units are liquidated at a fraction of unit COST (not retail),
    guaranteeing a net loss:
      - Immediate retirement: recover 25% of cost → 75% loss
      - End-of-round retirement: recover 50% of cost → 50% loss

    Fire-sale recovery offsets part of the write-off but never eliminates it.
    """
    from core.models.results_financials import RoundResultProductMarket

    context.retirement_costs = {}     # team_id → net retirement expense (always positive)
    context.retirement_revenue = {}   # team_id → fire-sale recovery

    current_round = context.round_number
    immediate_recovery = D(str(get_config(context.scenario, 'retirement_immediate_recovery_pct', default=0.25)))
    endofround_recovery = D(str(get_config(context.scenario, 'retirement_endofround_recovery_pct', default=0.50)))

    for team in context.teams:
        from core.models.decisions import DecisionSubmission
        submission = DecisionSubmission.objects.filter(
            team=team, round__round_number=current_round, round__game=context.game,
        ).first()
        if not submission:
            continue

        team_retire_expense = D('0')
        team_liquidate_revenue = D('0')

        for retire_dec in submission.product_retires.select_related('team_product').all():
            product = retire_dec.team_product

            prev_round = current_round - 1
            if prev_round < 0:
                continue

            prior_results = RoundResultProductMarket.objects.filter(
                game=context.game, team=team, team_product=product,
                round_number=prev_round,
            )

            for pr in prior_results:
                unsold = D(str(pr.units_unsold or 0))
                if unsold <= 0:
                    continue

                unit_cost = D(str(pr.unit_cost or 0))
                inventory_value = (unsold * unit_cost).quantize(D('0.01'), rounding=ROUND_HALF_UP)

                if retire_dec.timing == 'immediate':
                    recovery_pct = immediate_recovery
                else:
                    recovery_pct = endofround_recovery

                recovery = (inventory_value * recovery_pct).quantize(D('0.01'), rounding=ROUND_HALF_UP)
                net_expense = inventory_value - recovery

                team_liquidate_revenue += recovery
                team_retire_expense += net_expense

        if team_retire_expense > 0 or team_liquidate_revenue > 0:
            context.retirement_costs[team.id] = team_retire_expense
            context.retirement_revenue[team.id] = team_liquidate_revenue
            context.log.append(
                f"Team {team.id}: inventory write-off={team_retire_expense + team_liquidate_revenue:,.0f}, "
                f"fire-sale recovery={team_liquidate_revenue:,.0f}, "
                f"net retirement cost={team_retire_expense:,.0f}"
            )

    context.log.append('Retirement costs calculated')


def calculate_repatriation_costs(context):
    """
    CC-31A B6: Repatriation cost for foreign market profits.
    CC-32C: Tax structure can reduce repatriation costs.
    """
    scenario = context.scenario
    context.repatriation_costs = {}  # team_id → Decimal

    # CC-32C: Load tax structures
    from core.models.cc32c_models import TeamTaxStructure
    team_tax_structures = {}
    for tts in TeamTaxStructure.objects.filter(
        game=context.game,
    ).select_related('current_structure'):
        team_tax_structures[tts.team_id] = tts

    for team in context.teams:
        total_repatriation = D('0')

        if not team.home_market_id:
            context.repatriation_costs[team.id] = D('0')
            continue

        # CC-32C: Get repatriation reduction from tax structure
        tts = team_tax_structures.get(team.id)
        structure = tts.current_structure if tts else None
        repat_reduction = D('0')
        if structure:
            repat_reduction = structure.repatriation_cost_reduction_pct

        for (t_id, m_id), profit in context.market_profit.items():
            if t_id != team.id:
                continue

            # Skip home market
            if m_id == team.home_market_id:
                continue

            if profit <= 0:
                continue

            # Get cultural distance for repatriation pct
            distance = CulturalDistanceMatrix.objects.filter(
                scenario=scenario,
                from_market=team.home_market,
                to_market_id=m_id,
            ).first()

            if distance and distance.repatriation_cost_pct > 0:
                effective_repat_pct = distance.repatriation_cost_pct * (D('1') - repat_reduction)
                repatriation_cost = (profit * effective_repat_pct).quantize(
                    D('0.01'), rounding=ROUND_HALF_UP,
                )
                total_repatriation += repatriation_cost

        context.repatriation_costs[team.id] = total_repatriation

    context.log.append('CC-31A: Repatriation costs calculated (CC-32C: structure reduction applied)')


def calculate_entry_mode_overhead(context):
    """
    CC-31A B7: Entry mode consequence costs.
    Brand Preservation: +15% operating overhead in that market.
    Dual Brand: +25% operating overhead.
    Full Integration: no additional cost.
    """
    context.entry_mode_overhead = {}  # (team_id, market_id) → Decimal multiplier

    for team in context.teams:
        presences = TeamMarketPresence.objects.filter(
            team=team, status='active',
        )
        for presence in presences:
            # Check if this was an acquisition with integration strategy
            entry_dec = DecisionMarketEntry.objects.filter(
                submission__team=team,
                market=presence.market,
                submission__round__game=context.game,
                integration_strategy__isnull=False,
            ).order_by('-submission__round__round_number').first()

            overhead = D('1.00')
            if entry_dec:
                if entry_dec.integration_strategy == 'BRAND_PRESERVE':
                    overhead = D('1.15')
                elif entry_dec.integration_strategy == 'DUAL_BRAND':
                    overhead = D('1.25')

            # Also check brand_preserved flag on presence
            if presence.brand_preserved and overhead == D('1.00'):
                overhead = D('1.15')

            context.entry_mode_overhead[(team.id, presence.market_id)] = overhead

    context.log.append('CC-31A: Entry mode overhead calculated')


def process_tax_structure_costs(context):
    """
    CC-32C: Process tax structure maintenance costs, setup costs for newly
    adopted structures, and audit rolls.
    Called after tax + repatriation in the engine pipeline.
    """
    import random
    from core.models.cc32c_models import TeamTaxStructure, TaxStructureType

    context.tax_audit_penalties = {}  # team_id → Decimal

    for team in context.teams:
        tts, _created = TeamTaxStructure.objects.get_or_create(
            game=context.game, team=team,
            defaults={'current_structure': None},
        )

        structure = tts.current_structure
        if not structure:
            context.tax_audit_penalties[team.id] = D('0')
            continue

        # Setup cost: deduct in the round it was adopted (if not already paid)
        if not tts.setup_cost_paid and structure.setup_cost > 0:
            team.cash_on_hand -= structure.setup_cost
            tts.setup_cost_paid = True
            tts.save(update_fields=['setup_cost_paid'])
            context.log.append(
                f'CC-32C: {team.name} paid {structure.name} setup cost '
                f'${float(structure.setup_cost):,.0f}'
            )

        # Maintenance cost tracked on context for financial statements
        # (already tracked in context.tax_structure_maintenance from calculate_tax)

        # Audit roll
        if structure.audit_probability_per_round > 0:
            audit_prob = float(structure.audit_probability_per_round)

            # Anti-Corruption + aggressive → increased audit probability
            if structure.anti_corruption_conflict:
                has_anti_corruption = TeamGovernanceCommitment.objects.filter(
                    game=context.game, team=team,
                    commitment_type__code='anti_corruption',
                    is_active=True,
                ).exists()
                if has_anti_corruption:
                    audit_prob *= 1.3  # 30% more likely

            # Compliance investment reduces audit probability (up to 20%)
            from core.models.cc31_models import TeamMarketCompliance
            compliance_records = TeamMarketCompliance.objects.filter(
                game=context.game, team=team,
            )
            if compliance_records.exists():
                avg_compliance = sum(
                    float(c.compliance_level) for c in compliance_records
                ) / compliance_records.count()
                audit_prob *= (1 - avg_compliance * 0.2)

            if random.random() < audit_prob:
                # AUDIT TRIGGERED — calculate back-taxes from recent savings
                recent_savings = tts.cumulative_tax_savings or D('0')
                # Approximate last 3 rounds of savings
                rounds_active = max(context.round_number - tts.adopted_round, 1)
                avg_savings_per_round = recent_savings / rounds_active if rounds_active > 0 else D('0')
                back_taxes = avg_savings_per_round * min(rounds_active, 3)
                penalty = (back_taxes * structure.audit_penalty_multiplier).quantize(
                    D('0.01'), rounding=ROUND_HALF_UP,
                )

                tts.times_audited += 1
                tts.cumulative_audit_penalties = (tts.cumulative_audit_penalties or D('0')) + penalty
                tts.last_audit_round = context.round_number
                tts.save(update_fields=['times_audited', 'cumulative_audit_penalties', 'last_audit_round'])

                context.tax_audit_penalties[team.id] = penalty
                context.log.append(
                    f'CC-32C: {team.name} TAX AUDIT — penalty ${float(penalty):,.0f} '
                    f'({structure.audit_penalty_multiplier}x back-taxes)'
                )
            else:
                context.tax_audit_penalties[team.id] = D('0')
        else:
            context.tax_audit_penalties[team.id] = D('0')

    # CC-32C: Apply regulator modifier to regulatory_govt feature levels
    _apply_regulator_modifiers(context)

    context.log.append('CC-32C: Tax structure costs processed')


def _apply_regulator_modifiers(context):
    """
    CC-32C: Adjust regulatory_govt strategy feature level based on
    each team's tax structure regulator_modifier (all markets).
    """
    from core.models.cc32c_models import TeamTaxStructure
    from core.models.scenario import FeatureDefinition
    from core.models.team_state import TeamStrategyFeatureLevel, TeamMarketPresence

    reg_feature = FeatureDefinition.objects.filter(
        scenario=context.scenario, code='regulatory_govt',
    ).first()
    if not reg_feature:
        return

    for team in context.teams:
        tts = TeamTaxStructure.objects.filter(
            game=context.game, team=team,
        ).select_related('current_structure').first()

        structure = tts.current_structure if tts else None
        if not structure or float(structure.regulator_modifier) == 0:
            continue

        modifier = float(structure.regulator_modifier)

        # Apply to all active markets
        active_markets = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).values_list('market_id', flat=True)

        for market_id in active_markets:
            fl, created = TeamStrategyFeatureLevel.objects.get_or_create(
                team=team, feature=reg_feature, market_id=market_id,
                round_number=context.round_number,
                defaults={'current_level': D(str(reg_feature.default_value))},
            )
            new_level = max(D('1'), min(D('5'), fl.current_level + D(str(modifier))))
            if new_level != fl.current_level:
                fl.current_level = new_level
                fl.save(update_fields=['current_level'])
