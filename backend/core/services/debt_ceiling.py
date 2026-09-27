"""One debt-ceiling calculation for validation and participant context.

W-CE4-10 exposed an asymmetry in the old lock rule. It skipped the ceiling
while equity was non-positive, so more borrowing was legal, then started
enforcing the ceiling as soon as an equity raise made the ratio finite. A
team could therefore borrow its way out of the blocker but could not repair
its balance sheet.

The ceiling governs *additional borrowing*. It does not require a company
whose opening balance sheet is already above the ceiling to repair the whole
position in one round: equity raises and debt repayments must remain legal.
"""
from decimal import Decimal as D


DEFAULT_MAX_DEBT_TO_EQUITY = D('2.0')


def configured_max_ratio(scenario):
    from core.models.scenario import ScenarioConfig

    row = ScenarioConfig.objects.filter(
        scenario=scenario,
        config_key='max_debt_to_equity_ratio',
    ).first()
    return D(str(row.config_value)) if row else DEFAULT_MAX_DEBT_TO_EQUITY


def assess(team, financing=None, *, max_ratio=None):
    """Return the current and decision-projected leverage position.

    ``financing`` may be a ``DecisionFinancing`` row or a mapping returned by
    ``funding_need.financing_decided``. A breach exists only when the draft
    increases debt and the projected balance sheet cannot support that debt.
    """
    maximum = (D(str(max_ratio)) if max_ratio is not None
               else configured_max_ratio(team.game.scenario))

    def value(name):
        if financing is None:
            return D('0')
        if isinstance(financing, dict):
            raw = financing.get(name, 0)
        else:
            raw = getattr(financing, name, 0)
        return D(str(raw or 0))

    opening_debt = D(str(team.total_debt or 0))
    opening_equity = D(str(team.total_equity or 0))
    requested_new_debt = value('new_debt')
    requested_repayment = value('debt_repayment')
    requested_equity = value('new_equity')

    projected_debt = max(
        opening_debt + requested_new_debt - requested_repayment, D('0'))
    projected_equity = opening_equity + requested_equity
    current_ratio = (opening_debt / opening_equity
                     if opening_equity > 0 else None)
    projected_ratio = (projected_debt / projected_equity
                       if projected_equity > 0 else None)
    debt_increases = projected_debt > opening_debt
    nonpositive_equity = projected_equity <= 0
    exceeds_ratio = bool(
        projected_ratio is not None and projected_ratio > maximum)
    blocks_new_debt = bool(
        debt_increases and (nonpositive_equity or exceeds_ratio))

    max_total_debt = max(opening_equity, D('0')) * maximum
    available_credit = max(max_total_debt - opening_debt, D('0'))

    return {
        'max_ratio': maximum,
        'opening_debt': opening_debt,
        'opening_equity': opening_equity,
        'current_ratio': current_ratio,
        'requested_new_debt': requested_new_debt,
        'requested_repayment': requested_repayment,
        'requested_equity': requested_equity,
        'projected_debt': projected_debt,
        'projected_equity': projected_equity,
        'projected_ratio': projected_ratio,
        'debt_increases': debt_increases,
        'nonpositive_equity': nonpositive_equity,
        'exceeds_ratio': exceeds_ratio,
        'blocks_new_debt': blocks_new_debt,
        'max_total_debt': max_total_debt,
        'available_credit': available_credit,
    }
