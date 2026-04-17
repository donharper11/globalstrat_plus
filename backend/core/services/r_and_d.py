"""
R&D Development Time Service

Platforms created on the CSR Workbench take time to develop before
programs can be created from them.  Development time scales with
platform ambition (feature values) and economy (Arkanis takes longer).
"""
import logging
from decimal import Decimal

from django.db.models import Avg

from core.models import (
    Program, ProgramType, ProgramFeature, ProgramPortfolio,
    SimulationParameters, SimulationState,
)

logger = logging.getLogger(__name__)

ZERO = Decimal('0')


# ── helpers ────────────────────────────────────────────────────────

def _get_param(name, default='0'):
    """Read a simulation parameter by name."""
    p = SimulationParameters.objects.filter(parameter_name=name).first()
    if p and p.parameter_value:
        return str(p.parameter_value).strip()
    return str(default)


def _is_r_and_d_enabled():
    return _get_param('r_and_d_enabled', 'true').lower() in ('true', '1', 'yes')


def _current_round_number():
    state = SimulationState.objects.filter(status='active').first()
    if not state:
        return 1
    from core.models import Round
    rnd = Round.objects.filter(round_id=state.current_round_id).first()
    return rnd.round_number if rnd else 1


# ── core functions ────────────────────────────────────────────────

def calculate_development_time(platform):
    """
    Calculate how many rounds a platform needs to develop.
    Returns 0 if R&D is disabled (instant development).
    """
    if not _is_r_and_d_enabled():
        return 0

    base = int(_get_param('r_and_d_base_rounds', '1'))

    # Arkanis platforms take longer
    arkanis_bonus = 0
    if platform.program_type_id:
        ptype = ProgramType.objects.filter(
            program_type_id=platform.program_type_id,
        ).first()
        if ptype and getattr(ptype, 'economy_id', None) == 2:
            arkanis_bonus = int(_get_param('r_and_d_arkanis_bonus_rounds', '1'))

    # Complex platforms (high avg feature value) take longer
    complexity_bonus = 0
    portfolios = ProgramPortfolio.objects.filter(program_id=platform.program_id)
    portfolio_ids = list(portfolios.values_list('program_portfolio_id', flat=True))
    if portfolio_ids:
        avg_val = ProgramFeature.objects.filter(
            program_portfolio_id__in=portfolio_ids,
        ).aggregate(avg=Avg('feature_value'))['avg']
        threshold = float(_get_param('r_and_d_complexity_threshold', '50'))
        if avg_val and float(avg_val) > threshold:
            complexity_bonus = 1

    total = base + arkanis_bonus + complexity_bonus
    max_rounds = int(_get_param('r_and_d_max_rounds', '3'))
    return min(total, max_rounds)


def apply_development_time(platform):
    """
    After a platform is created/saved, calculate and apply R&D time.
    Modifies platform in place and saves.
    Returns the dev_rounds value.
    """
    dev_rounds = calculate_development_time(platform)

    if dev_rounds > 0:
        platform.development_status = 'developing'
        platform.development_rounds_total = dev_rounds
        platform.development_rounds_remaining = dev_rounds
        platform.development_started_round = _current_round_number()
        platform.status = 'developing'
    else:
        platform.development_status = 'ready'
        platform.development_rounds_total = 0
        platform.development_rounds_remaining = 0
        platform.status = 'active'

    platform.save()
    return dev_rounds


def process_r_and_d_development(instance_id, round_number):
    """
    Called at start of advance_round: decrement development_rounds_remaining
    for all developing platforms.  Platforms that finish become 'ready'/'active'.
    Returns list of newly-ready Program objects.
    """
    qs = Program.objects.filter(development_status='developing')
    if instance_id is not None:
        qs = qs.filter(instance_id=instance_id)

    newly_ready = []
    for platform in qs:
        if platform.development_rounds_remaining is None:
            continue
        platform.development_rounds_remaining -= 1
        if platform.development_rounds_remaining <= 0:
            platform.development_rounds_remaining = 0
            platform.development_status = 'ready'
            platform.status = 'active'
            newly_ready.append(platform)
        platform.save()

    return newly_ready


def accelerate_development(platform, team_id):
    """
    Spend R&D budget to reduce development time by 1 round.
    Returns dict with result or error.
    """
    if platform.development_status != 'developing':
        return {'error': 'Platform is not in development.'}
    if (platform.development_rounds_remaining or 0) <= 0:
        return {'error': 'Platform is already ready.'}

    cost = Decimal(_get_param('r_and_d_acceleration_cost', '30000'))

    # Check budget
    from core.services.budget import get_budget_status
    state = SimulationState.objects.filter(status='active').first()
    round_id = state.current_round_id if state else None
    budget_info = get_budget_status(int(team_id), round_id)
    remaining = Decimal(str(budget_info.get('remaining', 0)))

    if remaining < cost:
        return {
            'error': f'Insufficient budget. Need ${cost:,.0f}, '
                     f'have ${remaining:,.0f}.',
        }

    # Apply acceleration
    platform.development_rounds_remaining -= 1
    platform.r_and_d_investment = (platform.r_and_d_investment or ZERO) + cost

    if platform.development_rounds_remaining <= 0:
        platform.development_rounds_remaining = 0
        platform.development_status = 'ready'
        platform.status = 'active'

    platform.save()

    # Record as R&D expense in financial_expenses
    _record_r_and_d_expense(int(team_id), platform.program_id, cost)

    return {
        'success': True,
        'rounds_remaining': platform.development_rounds_remaining,
        'cost': float(cost),
        'status': platform.development_status,
    }


def _record_r_and_d_expense(team_id, program_id, cost):
    """Record R&D acceleration cost as a financial expense."""
    from core.models import FinancialExpense
    state = SimulationState.objects.filter(status='active').first()
    round_id = state.current_round_id if state else None
    if round_id:
        FinancialExpense.objects.create(
            round_id=round_id,
            team_id=team_id,
            program_id=program_id,
            expense_type='R&D Acceleration',
            cost_amount=cost,
        )


def create_system_message(team_id, instance_id, message, round_number):
    """Create a system notification for R&D completion."""
    try:
        from core.models.messaging import TeamNotification
        TeamNotification.objects.create(
            team_id=team_id,
            instance_id=instance_id,
            notification_text=message,
            round_number=round_number,
            is_read=False,
        )
    except Exception as exc:
        logger.warning("Failed to create R&D notification: %s", exc)
