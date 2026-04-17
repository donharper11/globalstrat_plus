"""
Budget Service: Program budget calculation, loan processing, and validation.
"""
from decimal import Decimal

from core.models import (
    SimulationParameters, SimulationState, Program, ProgramType,
    ProgramFeature,
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # Removed: Feature
    TeamIncomeStatement, TeamBalanceSheet,
)

ZERO = Decimal('0')


def _get_param(name, default='0'):
    """Read a simulation parameter by name, return as Decimal."""
    p = SimulationParameters.objects.filter(parameter_name=name).first()
    if p and p.parameter_value:
        try:
            return Decimal(str(p.parameter_value))
        except Exception:
            pass
    return Decimal(str(default))


def calculate_program_budget(team_id, round_id=None):
    """
    Program budget for a team in the current/given round.
    Round 1 (no prior income): seed budget.
    Otherwise: pct of previous round's net_profit, with a minimum floor.
    """
    pct = _get_param('program_budget_pct', '0.20')
    seed = _get_param('program_seed_budget', '200000')
    floor = _get_param('program_min_budget', '50000')

    # Find previous round's income statement
    qs = TeamIncomeStatement.objects.filter(team_id=team_id).order_by('-round_id')
    if round_id:
        qs = qs.filter(round_id__lt=round_id)

    prev = qs.first()
    if not prev or prev.net_profit is None:
        return seed

    budget = prev.net_profit * pct
    return max(budget, floor)


def get_total_program_cost(team_id):
    """
    Sum estimated per-round costs for all active programs belonging to the team.
    Matches the logic in round_engine._calculate_program_costs.
    """
    active = Program.objects.filter(team_id=team_id, status='Active')
    total = ZERO

    # Build cost_factor lookup
    # TODO: GlobalStrat — update to use new scenario models (CC-3)
    # Feature model removed — cost_factor lookup disabled
    cost_map = {}

    for prog in active:
        # Base cost from program type
        pt = ProgramType.objects.filter(program_type_id=prog.program_type_id).first()
        if pt and pt.base_cost:
            total += pt.base_cost

        # Feature costs
        for pf in ProgramFeature.objects.filter(program_id=prog.program_id):
            cf = cost_map.get(pf.feature_id, ZERO)
            if cf and pf.feature_value:
                total += pf.feature_value * cf

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Media budgets (ProgramMedia model deleted)
        # for mc in ProgramMedia.objects.filter(program_id=prog.program_id).values_list('budget_allocated', flat=True):
        #     if mc:
        #         total += mc

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Resource values (ProgramResource model deleted)
        # for rc in ProgramResource.objects.filter(program_id=prog.program_id).values_list('resource_value', flat=True):
        #     if rc:
        #         total += rc

    return total


def get_budget_status(team_id, round_id=None):
    """Return a dict with full budget/loan status for the API."""
    budget = calculate_program_budget(team_id, round_id)
    committed = get_total_program_cost(team_id)
    remaining = budget - committed

    active_count = Program.objects.filter(team_id=team_id, status='Active').count()
    max_programs = int(_get_param('max_active_programs', '6'))

    # Latest loan balance
    bs = TeamBalanceSheet.objects.filter(team_id=team_id).order_by('-balance_id').first()
    loan = bs.loan_balance if bs and bs.loan_balance else ZERO

    interest_rate = _get_param('loan_interest_rate', '0.08')

    return {
        'program_budget': float(budget),
        'total_committed': float(committed),
        'remaining': float(remaining),
        'active_programs': active_count,
        'max_programs': max_programs,
        'loan_balance': float(loan),
        'interest_rate': float(interest_rate),
        'is_over_budget': committed > budget,
        'overage': float(max(committed - budget, ZERO)),
    }


def validate_program_activation(team_id, round_id=None, additional_cost=None):
    """
    Check whether a team can activate another program.
    Returns (ok, warnings, errors).
    - Program cap is a hard block (error).
    - Budget overage is allowed but produces a warning (auto-loan).
    """
    errors = []
    warnings = []

    active_count = Program.objects.filter(team_id=team_id, status='Active').count()
    max_programs = int(_get_param('max_active_programs', '6'))

    if active_count >= max_programs:
        errors.append(f'Program cap reached ({active_count}/{max_programs}). '
                      f'Deactivate a program before adding another.')

    if additional_cost is not None:
        budget = calculate_program_budget(team_id, round_id)
        committed = get_total_program_cost(team_id)
        new_total = committed + Decimal(str(additional_cost))
        if new_total > budget:
            overage = new_total - budget
            rate = _get_param('loan_interest_rate', '0.08')
            warnings.append(
                f'This will exceed your Program budget by ${float(overage):,.0f}. '
                f'The overage will be financed as a loan at {float(rate)*100:.0f}% interest per round.'
            )

    ok = len(errors) == 0
    return ok, warnings, errors


def process_loans(team_id, round_id, program_budget, actual_program_expenses):
    """
    Called during advance_round to handle loan mechanics.
    Returns (new_loan_balance, interest_payment, overage, repayment).
    """
    rate = _get_param('loan_interest_rate', '0.08')

    # Previous loan balance
    prev_bs = TeamBalanceSheet.objects.filter(team_id=team_id).order_by('-balance_id').first()
    old_loan = prev_bs.loan_balance if prev_bs and prev_bs.loan_balance else ZERO

    # Interest accrues on the old balance
    interest = old_loan * rate

    # Overage or surplus
    overage = ZERO
    repayment = ZERO
    if actual_program_expenses > program_budget:
        overage = actual_program_expenses - program_budget
    elif old_loan > ZERO:
        surplus = program_budget - actual_program_expenses
        repayment = min(surplus, old_loan)

    new_loan = old_loan + overage - repayment + interest

    return new_loan, interest, overage, repayment
