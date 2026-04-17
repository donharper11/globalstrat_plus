"""
Round Engine: Orchestrates full end-of-round processing.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

from core.models import (
    SimulationState, SimulationParameters, Round, Team,
    Program, ProgramType, ProgramPortfolio, ProgramFeature,
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # Removed: Segment, Feature
    FinancialRevenue, FinancialExpense,
    TeamIncomeStatement, TeamBalanceSheet, TeamCashFlow,
    TeamPerformance, LeaderboardScore, LeaderboardMetric,
    NewSalesByRound, CumulativeSales,
    Score,
)
from core.services.scoring import (
    distribute_adoption, rollup_esg_scores,
    calculate_alignment,
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # calculate_sdg_coverage, calculate_scope_scores,
    # check_framework_compliance, get_supplier_modifiers,
)
# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# from core.services.competitor_ai import simulate_all_competitors

ZERO = Decimal('0')


def _get_or_create_state():
    """Get the active simulation state, or create one if none exists."""
    state = SimulationState.objects.filter(status='active').first()
    if state:
        return state

    # Find the current active round
    active_round = Round.objects.filter(status='active').order_by('round_number').first()
    if not active_round:
        active_round = Round.objects.order_by('round_number').first()
        if not active_round:
            raise ValueError("No rounds found in the database")

    state = SimulationState.objects.create(
        current_round_id=active_round.round_id,
        status='active',
        last_updated=timezone.now(),
    )
    return state


def _calculate_program_costs(team_id, round_id):
    """Calculate total Program expenses for a team's active programs in this round."""
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # from core.models import ProgramSupplier

    active_programs = Program.objects.filter(team_id=team_id, status='Active')
    total_cost = ZERO

    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Build a lookup of feature cost_factors (prefer FeaturesCost, fallback to Feature.cost_factor)
    # features_cost_map = {}
    # for fc in FeaturesCost.objects.all():
    #     if fc.feature_id and fc.cost_factor:
    #         features_cost_map[fc.feature_id] = fc.cost_factor
    # if not features_cost_map:
    #     for f in Feature.objects.exclude(cost_factor__isnull=True):
    #         features_cost_map[f.feature_id] = f.cost_factor
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # Feature model removed — cost_factor lookup disabled
    features_cost_map = {}

    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # Build supplier cost multiplier lookup per program
    # supplier_map = {}
    # supplier_assignments = ProgramSupplier.objects.filter(
    #     program_id__in=active_programs.values_list('program_id', flat=True),
    #     is_active=True,
    # ).select_related('supplier')
    # for sa in supplier_assignments:
    #     supplier_map[sa.program_id] = sa.supplier.cost_multiplier

    for program in active_programs:
        program_cost = ZERO

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Check implementation cost table first
        # impl_cost = ProgramImplementationCost.objects.filter(
        #     program_id=program.program_id, round_id=round_id
        # ).first()
        # if impl_cost and impl_cost.implementation_cost:
        #     program_cost = impl_cost.implementation_cost
        # else:

        # Base cost per round from program type (operational cost of running the program)
        pt = ProgramType.objects.filter(program_type_id=program.program_type_id).first()
        if pt and pt.base_cost:
            program_cost += pt.base_cost

        # Feature costs: feature_value * cost_factor
        program_features = ProgramFeature.objects.filter(
            program_id=program.program_id
        )
        for pf in program_features:
            cost_factor = features_cost_map.get(pf.feature_id, ZERO)
            if cost_factor and pf.feature_value:
                program_cost += pf.feature_value * cost_factor

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Media budgets
        # media_cost = ProgramMedia.objects.filter(
        #     program_id=program.program_id
        # ).values_list('budget_allocated', flat=True)
        # for mc in media_cost:
        #     if mc:
        #         program_cost += mc

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Resource values
        # resource_cost = ProgramResource.objects.filter(
        #     program_id=program.program_id
        # ).values_list('resource_value', flat=True)
        # for rc in resource_cost:
        #     if rc:
        #         program_cost += rc

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Apply supplier cost multiplier if a supplier is assigned
        # sup_multiplier = supplier_map.get(program.program_id)
        # if sup_multiplier is not None:
        #     program_cost = program_cost * sup_multiplier

        total_cost += program_cost

    return total_cost


def _get_revenue_per_unit(team_id):
    """Get weighted-average revenue per unit from active programs' ProgramType.unit_price."""
    active_programs = Program.objects.filter(team_id=team_id, status='Active')
    total_price = ZERO
    count = 0
    for program in active_programs:
        pt = ProgramType.objects.filter(program_type_id=program.program_type_id).first()
        price = (pt.unit_price if pt and pt.unit_price else None) or \
                (pt.base_cost if pt and pt.base_cost else None)
        if price:
            total_price += price
            count += 1
    if count > 0:
        return total_price / count
    return Decimal('50.00')  # fallback


def _get_operating_costs():
    """Get operating costs from simulation_parameters, fallback to $10,000."""
    param = SimulationParameters.objects.filter(
        parameter_name='operating_costs_per_round'
    ).first()
    if param and param.parameter_value:
        try:
            return Decimal(param.parameter_value)
        except Exception:
            pass
    return Decimal('10000.00')


def _calculate_cogs(team_id, total_units):
    """
    Calculate Cost of Goods Sold from adoption volume.
    Each adopted unit incurs COGS based on ProgramType.cogs_per_unit.
    """
    active_programs = Program.objects.filter(team_id=team_id, status='Active')
    total_cogs_rate = ZERO
    count = 0
    for program in active_programs:
        pt = ProgramType.objects.filter(program_type_id=program.program_type_id).first()
        if pt and pt.cogs_per_unit:
            total_cogs_rate += pt.cogs_per_unit
            count += 1
    if count > 0:
        avg_cogs = total_cogs_rate / count
    else:
        avg_cogs = ZERO
    return avg_cogs * total_units


def _calculate_revenue(team_id, round_id, adoption_results):
    """
    Calculate revenue from adoption volume.
    Each adopted unit generates revenue based on ProgramType.base_cost.
    """
    total_revenue = ZERO
    total_units = 0

    # Sum up adoptions across all stakeholders
    for segment_id, team_adoptions in adoption_results.items():
        units = team_adoptions.get(team_id, 0)
        total_units += units

    revenue_per_unit = _get_revenue_per_unit(team_id)
    total_revenue = revenue_per_unit * total_units

    return total_revenue, total_units


# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# def _check_supplier_risk_events(team_id, instance_id, round_number):
#     """
#     If a team uses a high-risk supplier, there is a 20% chance each round
#     that a negative event fires (supply chain disruption news).
#     """
#     import random
#     from core.models import ProgramSupplier, Newsfeeds
#
#     active_programs = Program.objects.filter(
#         team_id=team_id, status='Active',
#     ).values_list('program_id', flat=True)
#
#     high_risk = ProgramSupplier.objects.filter(
#         program_id__in=active_programs, is_active=True,
#     ).select_related('supplier').filter(supplier__risk_level='high')
#
#     if instance_id is not None:
#         high_risk = high_risk.filter(instance_id=instance_id)
#
#     if not high_risk.exists():
#         return
#
#     if random.random() < 0.20:
#         supplier_name = high_risk.first().supplier.name
#         try:
#             current_round = Round.objects.filter(round_number=round_number).first()
#             round_id = current_round.round_id if current_round else None
#             Newsfeeds.objects.create(
#                 team_id=team_id,
#                 round_id=round_id,
#                 title='Supply Chain Risk Alert',
#                 body=(
#                     f'Reports of labor violations at your supplier {supplier_name} '
#                     f'have surfaced. Stakeholders are demanding immediate action. '
#                     f'This may impact your social and governance scores.'
#                 ),
#                 category='supply_chain',
#             )
#         except Exception:
#             pass


@transaction.atomic
def advance_round(game_id=None):
    """
    Orchestrate full end-of-round processing.
    If game_id is provided, uses that simulation state.
    Otherwise finds/creates the active state.
    Returns dict with round results summary.
    """
    # 1. Get current state
    if game_id:
        state = SimulationState.objects.filter(state_id=game_id).first()
        if not state:
            raise ValueError(f"No simulation state found for state_id={game_id}")
    else:
        state = _get_or_create_state()

    current_round = Round.objects.filter(round_id=state.current_round_id).first()
    if not current_round:
        raise ValueError("No current round found")

    round_id = current_round.round_id
    round_number = current_round.round_number
    instance_id = state.instance_id

    # 2. Lock current round
    current_round.status = 'completed'
    current_round.save()

    # 2b. Process R&D development (before scoring — newly ready platforms
    #     become active and start contributing this round)
    r_and_d_newly_ready = []
    try:
        from core.services.r_and_d import process_r_and_d_development, create_system_message
        r_and_d_newly_ready = process_r_and_d_development(instance_id, round_number)
        for platform in r_and_d_newly_ready:
            create_system_message(
                team_id=int(platform.team_id),
                instance_id=instance_id,
                message=(
                    f"R&D Complete: Your '{platform.program_name}' platform is now "
                    f"ready. Create programs from it in the Program Program Portfolio."
                ),
                round_number=round_number,
            )
    except Exception as exc:
        logger.warning("R&D processing failed for round %s: %s", round_number, exc)

    # 3. Get all teams and stakeholders
    teams = Team.objects.all()
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # Segment model removed — adoption distribution disabled
    adoption_results = {}  # {segment_id: {team_id: units}}

    # 4b. Persist adoption results to cumulative tables
    from django.db import connection as db_conn
    with db_conn.cursor() as cursor:
        for segment_id, team_adoptions in adoption_results.items():
            for tid, units in team_adoptions.items():
                if units <= 0:
                    continue
                # Find a program_id for this team (required by table FK)
                first_program = Program.objects.filter(
                    team_id=tid, status='Active'
                ).values_list('program_id', flat=True).first()
                if not first_program:
                    continue

                # Get previous cumulative for this stakeholder (across all programs)
                cursor.execute(
                    "SELECT COALESCE(SUM(cumulative_engagement), 0) "
                    "FROM cumulative_stakeholder_engagement "
                    "WHERE segment_id = %s",
                    [segment_id],
                )
                prev_cumulative = cursor.fetchone()[0]

                # Insert new row (incremental value stored, Sum query accumulates)
                cursor.execute(
                    "INSERT INTO cumulative_stakeholder_engagement "
                    "(segment_id, program_id, round_id, cumulative_engagement) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (segment_id, program_id, round_id) "
                    "DO UPDATE SET cumulative_engagement = EXCLUDED.cumulative_engagement",
                    [segment_id, first_program, round_id, units],
                )

    # 5. Per team: calculate financials and scores
    team_results = {}
    for team in teams:
        tid = team.team_id

        # Program costs (Program implementation: features)
        program_expenses = _calculate_program_costs(tid, round_id)

        # Revenue from adoption
        total_revenue, total_units = _calculate_revenue(
            tid, round_id, adoption_results
        )

        # COGS — variable cost that scales with adoption volume
        cogs = _calculate_cogs(tid, total_units)

        # Operating costs (from simulation_parameters or default)
        operating_costs = _get_operating_costs()

        # Store financial records
        # Revenue per program
        active_programs = Program.objects.filter(team_id=tid, status='Active')
        program_count = max(active_programs.count(), 1)
        for program in active_programs:
            FinancialRevenue.objects.create(
                round_id=round_id,
                team_id=tid,
                program_id=program.program_id,
                se_units=total_units // program_count,
                revenue=total_revenue / program_count,
            )

            FinancialExpense.objects.create(
                round_id=round_id,
                team_id=tid,
                program_id=program.program_id,
                expense_type='Program Implementation',
                cost_amount=program_expenses / program_count,
            )

            FinancialExpense.objects.create(
                round_id=round_id,
                team_id=tid,
                program_id=program.program_id,
                expense_type='Cost of Goods Sold',
                cost_amount=cogs / program_count,
            )

        # Loan processing: budget vs actual Program spend
        from core.services.budget import calculate_program_budget, process_loans
        program_budget = calculate_program_budget(tid, round_id)
        loan_balance, interest_payment, overage, repayment = process_loans(
            tid, round_id, program_budget, program_expenses
        )

        # Record loan interest as a separate expense
        if interest_payment > ZERO:
            for program in active_programs:
                FinancialExpense.objects.create(
                    round_id=round_id,
                    team_id=tid,
                    program_id=program.program_id,
                    expense_type='Loan Interest',
                    cost_amount=interest_payment / program_count,
                )

        # Income statement: Revenue - COGS = Gross Margin - Program Ops - Interest = Net Profit
        gross_margin = total_revenue - cogs
        program_operating_costs = program_expenses + operating_costs
        net_profit = gross_margin - program_operating_costs - interest_payment
        inc_kwargs = dict(
            team_id=tid,
            round_id=round_id,
            revenue=total_revenue,
            cogs=cogs,
            operating_costs=program_operating_costs,
            net_profit=net_profit,
        )
        if instance_id is not None:
            inc_kwargs['instance_id'] = instance_id
        TeamIncomeStatement.objects.create(**inc_kwargs)

        # Balance sheet (cumulative)
        # Assets = Cash + Retained Earnings growth
        # Liabilities = Loans outstanding
        # Equity = Assets - Liabilities
        prev_balance = TeamBalanceSheet.objects.filter(
            team_id=tid
        ).order_by('-balance_id').first()

        prev_assets = prev_balance.assets if prev_balance and prev_balance.assets else Decimal('100000.00')
        prev_liabilities = prev_balance.liabilities if prev_balance and prev_balance.liabilities else Decimal('50000.00')
        prev_retained = prev_balance.retained_earnings if prev_balance and prev_balance.retained_earnings else ZERO

        new_retained = prev_retained + net_profit
        new_assets = prev_assets + net_profit
        new_liabilities = prev_liabilities + overage - repayment
        new_equity = new_assets - new_liabilities

        bs_kwargs = dict(
            team_id=tid,
            round_id=round_id,
            assets=new_assets,
            liabilities=new_liabilities,
            equity=new_equity,
            retained_earnings=new_retained,
            loan_balance=loan_balance,
        )
        if instance_id is not None:
            bs_kwargs['instance_id'] = instance_id
        TeamBalanceSheet.objects.create(**bs_kwargs)

        # Cash flow statement — split into three activities
        # Operating: revenue minus operating expenses (COGS + Program + operating costs)
        cf_operating = total_revenue - cogs - program_expenses - operating_costs
        # Investing: Program program setup costs (negative = cash out for investments)
        cf_investing = -program_expenses
        # Financing: loan proceeds (overage) minus repayment minus interest
        cf_financing = overage - repayment - interest_payment
        net_cash = cf_operating + cf_investing + cf_financing

        cf_kwargs = dict(
            team_id=tid,
            round_id=round_id,
            cash_inflows=total_revenue,
            cash_outflows=program_expenses + cogs + operating_costs + interest_payment,
            operating_activities=cf_operating,
            investing_activities=cf_investing,
            financing_activities=cf_financing,
            net_cash_change=net_cash,
        )
        if instance_id is not None:
            cf_kwargs['instance_id'] = instance_id
        TeamCashFlow.objects.create(**cf_kwargs)

        # ESG Scorecard
        esg = rollup_esg_scores(tid, round_id)
        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # esg_kwargs = dict(
        #     team_id=tid,
        #     environmental_score=esg.get('E', 0),
        #     social_score=esg.get('S', 0),
        #     governance_score=esg.get('G', 0),
        #     round_number=round_number,
        # )
        # if instance_id is not None:
        #     esg_kwargs['instance_id'] = instance_id
        # ESGScorecard.objects.create(**esg_kwargs)

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # SDG Coverage
        # sdg_count = calculate_sdg_coverage(tid, instance_id, round_number)
        sdg_count = 0

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Scope 1/2/3 Carbon Decomposition
        # scope_scores = calculate_scope_scores(tid, instance_id, round_number)
        scope_scores = {}

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Apply supplier Scope 3 modifier
        # supplier_mods = get_supplier_modifiers(tid, instance_id)
        # if supplier_mods['scope3_modifier'] != 1.0 and 3 in scope_scores:
        #     from core.models import TeamScopeScore, EmissionScope
        #     modified_s3 = round(scope_scores[3] * supplier_mods['scope3_modifier'], 2)
        #     scope_scores[3] = modified_s3
        #     scope3_obj = EmissionScope.objects.filter(scope_number=3).first()
        #     if scope3_obj:
        #         TeamScopeScore.objects.filter(
        #             team_id=tid, instance_id=instance_id,
        #             round_number=round_number, scope_id=scope3_obj.scope_id,
        #         ).update(score=modified_s3)

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Supplier risk event check: 20% chance for high-risk suppliers
        # _check_supplier_risk_events(tid, instance_id, round_number)

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Regulatory Framework Compliance Check
        # compliance_result = check_framework_compliance(tid, instance_id, round_number)
        compliance_result = None

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # International Framework Compliance Check (UNGC, OECD, King)
        # intl_compliance = {}
        # try:
        #     from core.services.intl_frameworks import (
        #         check_international_framework_compliance,
        #         check_oecd_cross_economy_consistency,
        #     )
        #     intl_compliance = check_international_framework_compliance(
        #         tid, instance_id, round_number,
        #     )
        #     from core.models.intl_frameworks import TeamFrameworkCommitment
        #     oecd_commitment = TeamFrameworkCommitment.objects.filter(
        #         team_id=tid, instance_id=instance_id, is_active=True,
        #         framework__code='OECD',
        #     ).first()
        #     if oecd_commitment:
        #         consistent = check_oecd_cross_economy_consistency(
        #             tid, instance_id, round_number,
        #         )
        #         if not consistent:
        #             intl_compliance['OECD_consistency'] = False
        # except Exception as exc:
        #     logger.warning("Intl framework compliance skipped for team %s: %s", tid, exc)
        intl_compliance = {}

        # Segment scores (alignment per stakeholder)
        # score_type_id=3 = "Alignment" in score_types table
        alignments = []
        for s in stakeholders:
            alignment = calculate_alignment(tid, s.segment_id, round_id)
            alignments.append(alignment)
            score_kwargs = dict(
                team_id=tid,
                round_id=round_id,
                segment_id=s.segment_id,
                score_type_id=3,
                score=Decimal(str(round(alignment * 100, 2))),
            )
            if instance_id is not None:
                score_kwargs['instance_id'] = instance_id
            Score.objects.create(**score_kwargs)

        # Team performance
        total_score = sum(esg.values())
        avg_satisfaction = 0.0
        stakeholder_count = stakeholders.count()
        if stakeholder_count > 0:
            avg_satisfaction = sum(alignments) / stakeholder_count

        perf = TeamPerformance.objects.filter(team_id=tid).order_by('-performance_id').first()
        if perf:
            perf.total_score = Decimal(str(total_score))
            perf.average_stakeholder_satisfaction = Decimal(str(round(avg_satisfaction, 4)))
            if instance_id is not None:
                perf.instance_id = instance_id
            perf.save()
        else:
            perf_kwargs = {
                'team_id': tid,
                'total_score': Decimal(str(total_score)),
                'average_stakeholder_satisfaction': Decimal(str(round(avg_satisfaction, 4))),
            }
            if instance_id is not None:
                perf_kwargs['instance_id'] = instance_id
            perf = TeamPerformance.objects.create(**perf_kwargs)

        team_results[tid] = {
            'revenue': float(total_revenue),
            'program_expenses': float(program_expenses),
            'cogs': float(cogs),
            'interest_payment': float(interest_payment),
            'net_profit': float(net_profit),
            'program_budget': float(program_budget),
            'loan_balance': float(loan_balance),
            'esg': esg,
            'total_units': total_units,
            'sdg_count': sdg_count,
            'scope_scores': scope_scores,
            'framework_compliant': compliance_result,
            'intl_compliance': intl_compliance,
            # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
            # 'supplier_cost_multiplier': supplier_mods['cost_multiplier'],
        }

    # 6. Run competitor AI
    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # simulate_all_competitors(round_id)

    # 7. Fire events for the completed round
    event_summary = {}
    try:
        from core.services.event_engine import fire_events
        game_id_for_events = current_round.game_id or 1
        event_summary = fire_events(round_number, game_id_for_events)
    except Exception as exc:
        logger.warning("Event engine failed for round %s: %s", round_number, exc)
        event_summary = {'error': f'event engine skipped: {exc}'}

    # 8. Advance to next round
    # Handle game_id=None by matching on round_number
    next_round = Round.objects.filter(
        round_number=round_number + 1,
    )
    if current_round.game_id is not None:
        next_round = next_round.filter(game_id=current_round.game_id)
    next_round = next_round.first()

    if next_round:
        next_round.status = 'active'
        next_round.save()
        state.current_round_id = next_round.round_id
    else:
        state.status = 'completed'

    state.last_updated = timezone.now()
    state.save()

    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # 9. Get active challenges for the next round
    # challenge_summary = {}
    # try:
    #     from core.services.challenge_engine import present_challenges, check_carryover
    #     next_round_id = next_round.round_id if next_round else round_id
    #     active_challenges = present_challenges(next_round_id)
    #     challenge_summary = {
    #         'active_count': active_challenges.count(),
    #         'challenge_ids': list(active_challenges.values_list('challenge_id', flat=True)),
    #     }
    #     for team in teams:
    #         carryover = check_carryover(team.team_id, round_id)
    #         if carryover:
    #             challenge_summary.setdefault('carryover', {})[team.team_id] = carryover
    # except Exception:
    #     challenge_summary = {'error': 'challenge engine skipped'}
    challenge_summary = {}

    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # 10. Check B-Corp milestones and award certification
    # bcorp_summary = {}
    # try:
    #     from core.services.bcorp import check_milestones, award_certification
    #     game_id_val = current_round.game_id or 1
    #     for team in teams:
    #         milestones = check_milestones(team.team_id, game_id_val)
    #         if milestones:
    #             met_count = sum(1 for m in milestones if m['met'])
    #             all_met = met_count == len(milestones)
    #             bcorp_summary[team.team_id] = {
    #                 'total': len(milestones),
    #                 'met': met_count,
    #                 'all_met': all_met,
    #             }
    #             cert_result = award_certification(team.team_id, game_id_val)
    #             bcorp_summary[team.team_id]['certified'] = cert_result.get('certified', False)
    # except Exception:
    #     bcorp_summary = {'error': 'bcorp engine skipped'}
    bcorp_summary = {}

    # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
    # 11. Ethics scoring — evaluate alignment for each team's decisions
    # ethics_summary = {}
    # try:
    #     from core.services.ethics_engine import evaluate_alignment
    #     dilemma_ids = list(
    #         EthicalDilemma.objects.values_list('dilemma_id', flat=True)
    #     )
    #     for team in teams:
    #         tid = team.team_id
    #         total_score = 0
    #         max_possible = 0
    #         evaluated = 0
    #         for did in dilemma_ids:
    #             result = evaluate_alignment(tid, did)
    #             total_score += result.get('score', 0) or 0
    #             max_possible += result.get('max_possible', 0) or 0
    #             if result.get('score', 0):
    #                 evaluated += 1
    #
    #         if max_possible > 0:
    #             ethical_pct = Decimal(str(round(total_score / max_possible * 100, 2)))
    #         else:
    #             ethical_pct = None
    #
    #         if ethical_pct is not None:
    #             perf = TeamPerformance.objects.filter(team_id=tid).first()
    #             if perf:
    #                 perf.ethical_alignment = ethical_pct
    #                 perf.updated_at = timezone.now()
    #                 perf.save()
    #
    #         ethics_summary[tid] = {
    #             'score': total_score,
    #             'max_possible': max_possible,
    #             'ethical_alignment': float(ethical_pct) if ethical_pct else None,
    #             'dilemmas_evaluated': evaluated,
    #         }
    # except Exception:
    #     ethics_summary = {'error': 'ethics engine skipped'}
    ethics_summary = {}

    # 12. Populate leaderboard scores
    try:
        # Ensure standard metrics exist
        for name, desc in [
            ('ESG Total', 'Combined Environmental + Social + Governance score'),
            ('Revenue', 'Total revenue earned in the round'),
            ('Segment Satisfaction', 'Average stakeholder alignment score'),
        ]:
            LeaderboardMetric.objects.get_or_create(
                metric_name=name, defaults={'description': desc}
            )

        metrics = {m.metric_name: m.metric_id for m in LeaderboardMetric.objects.all()}
        esg_metric = metrics.get('ESG Total')
        revenue_metric = metrics.get('Revenue')
        satisfaction_metric = metrics.get('Segment Satisfaction')

        for team in teams:
            tid = team.team_id
            tr = team_results.get(tid, {})

            def _lb_create(**kwargs):
                if instance_id is not None:
                    kwargs['instance_id'] = instance_id
                LeaderboardScore.objects.create(**kwargs)

            # ESG total score
            if esg_metric:
                _lb_create(
                    team_id=tid, round_id=round_id,
                    metric_id=esg_metric,
                    score=Decimal(str(sum(tr.get('esg', {}).values()))),
                )

            # Revenue
            if revenue_metric:
                _lb_create(
                    team_id=tid, round_id=round_id,
                    metric_id=revenue_metric,
                    score=Decimal(str(tr.get('revenue', 0))),
                )

            # Segment satisfaction
            if satisfaction_metric:
                perf = TeamPerformance.objects.filter(team_id=tid).first()
                if perf and perf.average_stakeholder_satisfaction is not None:
                    _lb_create(
                        team_id=tid, round_id=round_id,
                        metric_id=satisfaction_metric,
                        score=perf.average_stakeholder_satisfaction,
                    )
    except Exception:
        pass  # leaderboard population is non-critical

    # 13. Gamification: evaluate achievements and badges
    gamification_summary = {}
    try:
        from core.services.gamification_engine import process_gamification
        gamification_summary = process_gamification(
            teams, round_id, round_number, team_results,
            bcorp_summary, ethics_summary,
        )
    except Exception:
        gamification_summary = {'error': 'gamification engine skipped'}

    # 14. Generate AI persona reactions for all teams (parallelized)
    persona_summary = {}
    import os as _os
    if _os.environ.get('BEProgram_SKIP_PERSONA'):
        persona_summary = {'skipped': 'BEProgram_SKIP_PERSONA set'}
    else:
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from core.services.persona_engine import generate_persona_reactions

            def _gen_for_team(team):
                import django.db
                django.db.connections.close_all()
                msgs = generate_persona_reactions(team.team_id, round_number)
                return team.team_id, len(msgs)

            with ThreadPoolExecutor(max_workers=min(len(teams), 5)) as executor:
                futures = {executor.submit(_gen_for_team, t): t for t in teams}
                for future in as_completed(futures):
                    try:
                        tid, count = future.result()
                        persona_summary[tid] = count
                    except Exception as e:
                        t = futures[future]
                        persona_summary[t.team_id] = f'error: {e}'
        except Exception:
            persona_summary = {'error': 'persona engine skipped'}

    return {
        'completed_round': round_number,
        'next_round': round_number + 1 if next_round else None,
        'team_results': team_results,
        'r_and_d_completed': [p.program_name for p in r_and_d_newly_ready],
        'events': event_summary,
        'challenges': challenge_summary,
        'bcorp': bcorp_summary,
        'ethics': ethics_summary,
        'gamification': gamification_summary,
        'persona_reactions': persona_summary,
    }
