"""Scenario-agnostic feedback policy used by calibration replays only.

The policy consumes only prior observed results and the decision form's
baseline values.  It deliberately has no scenario names, starter-profile
names, or scenario-specific constants.
"""
from __future__ import annotations

import math


REQUIRED_PARAMETERS = (
    'initial_production_factor',
    'base_buffer',
    'stockout_buffer',
    'inventory_buffer',
    'stockout_sell_through',
    'inventory_sell_through',
    'max_growth_factor',
    'price_up_factor',
    'price_down_factor',
    'staff_step',
    'max_staff_factor',
    'cash_guard_buffer',
    'leverage_guard',
)


def normalize_policy(raw):
    """Validate and normalize one frozen feedback-policy parameter set."""
    if not isinstance(raw, dict):
        raise ValueError('adaptive policy must be a JSON object')
    missing = [key for key in REQUIRED_PARAMETERS if key not in raw]
    unknown = sorted(set(raw) - set(REQUIRED_PARAMETERS))
    if missing:
        raise ValueError('missing adaptive policy fields: ' + ', '.join(missing))
    if unknown:
        raise ValueError('unknown adaptive policy fields: ' + ', '.join(unknown))
    result = {}
    for key in REQUIRED_PARAMETERS:
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'{key} must be numeric')
        result[key] = float(value)
    if not 0 < result['inventory_sell_through'] < result['stockout_sell_through'] <= 1:
        raise ValueError('sell-through thresholds must satisfy 0 < inventory < stockout <= 1')
    for key in ('initial_production_factor', 'base_buffer', 'stockout_buffer',
                'inventory_buffer', 'max_growth_factor', 'price_up_factor',
                'price_down_factor', 'max_staff_factor', 'cash_guard_buffer'):
        if result[key] <= 0:
            raise ValueError(f'{key} must be positive')
    if result['staff_step'] < 0:
        raise ValueError('staff_step must be non-negative')
    if result['leverage_guard'] <= 0:
        raise ValueError('leverage_guard must be positive')
    return result


def decide(*, baseline_volume, baseline_price, baseline_staff, prior,
           finances, parameters):
    """Return the next product-market decision and its observable rationale.

    ``prior`` is ``None`` in round one.  Otherwise it contains produced, sold,
    unsold, and lost-demand quantities from the immediately preceding round.
    ``finances`` contains prior closing cash and debt-to-equity.
    """
    p = normalize_policy(parameters)
    if prior is None:
        return {
            'production_volume': max(
                1, math.ceil(float(baseline_volume)
                             * p['initial_production_factor'])),
            'price_factor': 1.0,
            'sales_staff': int(baseline_staff),
            'signal': 'initial',
            'sell_through': None,
            'lost_demand': None,
            'buffer': p['initial_production_factor'],
            'financial_guard': False,
        }

    produced = max(float(prior['produced']), 1.0)
    sold = max(float(prior['sold']), 0.0)
    lost_demand = max(float(prior.get('lost_demand', 0.0)), 0.0)
    sell_through = min(max(sold / produced, 0.0), 1.0)
    if (sell_through >= p['stockout_sell_through']
            and lost_demand > 0):
        signal = 'stockout_with_lost_demand'
        buffer = p['stockout_buffer']
        price_factor = p['price_up_factor']
        staff = int(baseline_staff)
    elif sell_through <= p['inventory_sell_through']:
        signal = 'excess_inventory'
        buffer = p['inventory_buffer']
        price_factor = p['price_down_factor']
        staff = min(
            math.ceil(float(baseline_staff) * p['max_staff_factor']),
            int(baseline_staff + p['staff_step']),
        )
    else:
        signal = 'balanced'
        buffer = p['base_buffer']
        price_factor = 1.0
        staff = int(baseline_staff)

    cash = float(finances.get('cash', 0.0))
    leverage = float(finances.get('debt_to_equity', 0.0))
    financial_guard = cash < 0 or leverage > p['leverage_guard']
    if financial_guard:
        buffer = min(buffer, p['cash_guard_buffer'])
        staff = int(baseline_staff)

    production = max(1, math.ceil(sold * buffer))
    production = min(
        production,
        max(1, math.ceil(produced * p['max_growth_factor'])),
    )
    return {
        'production_volume': production,
        'price_factor': price_factor,
        'sales_staff': staff,
        'signal': signal,
        'sell_through': round(sell_through, 8),
        'lost_demand': round(lost_demand, 4),
        'buffer': buffer,
        'financial_guard': financial_guard,
    }
