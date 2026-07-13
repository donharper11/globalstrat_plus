"""
Engine Step 12: Financial Statement Assembly.
From 03-engine-logic.md Section 11.
"""
from decimal import Decimal, ROUND_HALF_UP

from core.models.decisions import DecisionFinancing, DecisionSubmission
from core.models.results_financials import (
    RoundResultProductMarket, RoundResultFinancials, RoundResultMarketRevenue,
)

D = Decimal


def _calculate_subscription_rate(team, game, round_number):
    """Calculate equity subscription rate based on investor sentiment."""
    from core.models.cc26_models import AIInvestorHolding
    from django.db.models import Avg

    latest_holdings = AIInvestorHolding.objects.filter(
        game=game, team=team,
        round_number=round_number - 1,
    )
    avg_satisfaction = 0.5
    if latest_holdings.exists():
        result = latest_holdings.aggregate(avg=Avg('satisfaction_score'))
        avg_satisfaction = float(result['avg'] or 0.5)

    if avg_satisfaction >= 0.7:
        return 1.0
    elif avg_satisfaction >= 0.5:
        return 0.80 + (avg_satisfaction - 0.5) * 1.0
    elif avg_satisfaction >= 0.3:
        return 0.60 + (avg_satisfaction - 0.3) * 1.0
    else:
        return 0.50


def _clamp_ratio(value, limit=D('99999')):
    """Clamp a ratio to prevent DB overflow, quantize to 4 decimal places."""
    clamped = max(-limit, min(limit, value))
    return clamped.quantize(D('0.0001'), rounding=ROUND_HALF_UP)


def generate_financial_statements(context):
    """
    For each team, assemble income statement, balance sheet, cash flow,
    key ratios. Write to RoundResultFinancials, RoundResultProductMarket,
    RoundResultMarketRevenue.
    """
    game = context.game
    current_round = context.round_number

    for team in context.teams:
        opex = context.opex.get(team.id, {})
        interest = context.interest.get(team.id, D('0'))
        tax = context.tax.get(team.id, D('0'))

        # ── Income Statement ──
        # Channel margin: sum across all product-markets for this team
        total_channel_margin = D('0')
        gross_revenue = D('0')
        for (t, m_id), mr in context.market_revenue.items():
            if t == team.id:
                total_channel_margin += mr.get('channel_margin_home', D('0'))
                gross_revenue += mr['home_revenue'] + mr.get('channel_margin_home', D('0'))

        total_revenue = opex.get('total_revenue', D('0'))

        total_cogs = D('0')
        for (t, p, m), c in context.cogs.items():
            if t == team.id:
                total_cogs += c['total_cogs']

        gross_profit = total_revenue - total_cogs

        rd_expense = opex.get('rd_expense', D('0'))
        marketing_expense = opex.get('marketing_expense', D('0'))
        strategy_expense = opex.get('strategy_expense', D('0'))
        research_expense = opex.get('research_expense', D('0'))
        admin_overhead = opex.get('admin_overhead', D('0'))

        total_opex = rd_expense + marketing_expense + strategy_expense + research_expense + admin_overhead

        logistics_tariff = D('0')
        for (t, p, m), l in context.logistics.items():
            if t == team.id:
                logistics_tariff += l['logistics_cost'] + l['tariff_cost']

        inventory_expense = D('0')
        for (t, p, m), inv in context.inventory_costs.items():
            if t == team.id:
                inventory_expense += inv['inventory_cost']

        # Retirement costs (write-off / liquidation)
        retirement_expense = getattr(context, 'retirement_costs', {}).get(team.id, D('0'))
        retirement_liquidation_rev = getattr(context, 'retirement_revenue', {}).get(team.id, D('0'))
        # Liquidation revenue offsets COGS line; retirement expense is an operating cost
        total_revenue += retirement_liquidation_rev

        # ── Balance Sheet (compute depreciation early for P&L) ──
        cash_opening = team.cash_on_hand
        capex = opex.get('capex', D('0'))

        prev_financials = RoundResultFinancials.objects.filter(
            game=game, team=team, round_number=current_round - 1,
        ).first()
        prev_plant_value = prev_financials.plant_book_value if prev_financials else D('0')

        depreciation_rate = D('0.10')
        new_plant_investment = capex
        depreciation = ((prev_plant_value + new_plant_investment) * depreciation_rate).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )
        plant_book_value = prev_plant_value + new_plant_investment - depreciation

        # CC-32C: Tax structure maintenance cost (treated as opex)
        tax_structure_maintenance = getattr(context, 'tax_structure_maintenance', {}).get(team.id, D('0'))
        # CC-32C: Audit penalties (one-off cost)
        tax_audit_penalty = getattr(context, 'tax_audit_penalties', {}).get(team.id, D('0'))
        # CC-19B Channel 2: supply-chain disruption costs (freight surcharge +
        # backup/expedite mitigation premiums) — a real operating expenditure.
        sc_disruption_cost = getattr(context, 'sc_disruption_costs', {}).get(team.id, D('0'))
        # CC-18: compliance remediation/penalty costs (detentions this round) — a
        # real operating expenditure booked by compliance_engine.enforce_compliance.
        compliance_cost = getattr(context, 'compliance_costs', {}).get(team.id, D('0'))

        # Include depreciation and retirement costs in operating income
        operating_income = (gross_profit - total_opex - logistics_tariff
                            - inventory_expense - depreciation - retirement_expense
                            - tax_structure_maintenance - sc_disruption_cost
                            - compliance_cost)
        # CC-20: realized FX hedge P&L — a non-operating financial item settled by
        # fx_engine.process_fx_hedges this round (gain > 0 lifts pre-tax income).
        fx_hedge_pnl = getattr(context, 'sc_fx_hedge_pnl', {}).get(team.id, D('0'))
        pre_tax_income = operating_income - interest + fx_hedge_pnl
        net_income = pre_tax_income - tax - tax_audit_penalty

        # Get financing decisions
        submission = DecisionSubmission.objects.filter(
            team=team, round__round_number=current_round, round__game=game,
        ).first()

        new_debt = D('0')
        debt_repayment = D('0')
        new_equity = D('0')
        dividend_per_share = D('0')

        if submission:
            try:
                fin = submission.financing
                if fin:
                    new_debt = fin.new_debt
                    debt_repayment = fin.debt_repayment
                    new_equity = fin.new_equity
                    dividend_per_share = fin.dividend_per_share
            except Exception:
                pass

        # CC-26: Apply investor sentiment subscription rate to equity issuance
        if new_equity > 0:
            subscription_rate = _calculate_subscription_rate(team, game, current_round)
            actual_equity_raised = (new_equity * D(str(subscription_rate))).quantize(
                D('0.01'), rounding=ROUND_HALF_UP,
            )
            share_price_est = total_equity / max(D(str(team.shares_outstanding)), D('1')) if team.shares_outstanding > 0 else D('1')
            new_shares = int(actual_equity_raised / max(share_price_est, D('1')))
            team.shares_outstanding += new_shares
            new_equity = actual_equity_raised

        dividends = (dividend_per_share * D(str(team.shares_outstanding))).quantize(
            D('0.01'), rounding=ROUND_HALF_UP,
        )

        # Cap dividends at available cash (cannot pay more than we have)
        # Compute pre-dividend cash to determine max payable
        # Use conservative cap: dividends cannot exceed cash_opening
        if dividends > cash_opening and cash_opening > 0:
            context.log.append(
                f'Dividend capped for {team.name}: requested ${dividends:,.0f}, '
                f'capped to ${cash_opening:,.0f} (available cash)'
            )
            dividends = cash_opening
        elif dividends > 0 and cash_opening <= 0:
            context.log.append(
                f'Dividend blocked for {team.name}: no cash available'
            )
            dividends = D('0')

        # Inventory value
        inventory_value = D('0')
        for (t, p, m), inv in context.inventory_costs.items():
            if t == team.id:
                inventory_value += inv['inventory_value']

        # Cash flow (indirect method: add back depreciation, adjust for working capital)
        prev_inventory_value = prev_financials.inventory_value if prev_financials else D('0')
        inventory_change = inventory_value - prev_inventory_value
        operating_cf = net_income + depreciation - inventory_change
        investing_cf = -capex
        financing_cf = new_debt - debt_repayment + new_equity - dividends

        cash_closing = cash_opening + operating_cf + investing_cf + financing_cf

        # Balance sheet totals
        total_debt = team.total_debt + new_debt - debt_repayment
        total_debt = max(total_debt, D('0'))

        retained_earnings_change = net_income - dividends
        total_equity = team.total_equity + new_equity + retained_earnings_change

        total_assets = cash_closing + plant_book_value + inventory_value

        # Balance check
        bs_diff = abs(total_assets - (total_debt + total_equity))
        if bs_diff > D('1'):
            context.log.append(
                f'WARNING: Balance sheet off by ${bs_diff} for {team.name}'
            )

        # ── Key Ratios ──
        avg_equity = (team.total_equity + total_equity) / 2
        revenue_for_ratio = max(total_revenue, D('1'))
        equity_for_ratio = max(avg_equity, D('1'))
        equity_closing_for_ratio = max(total_equity, D('1'))

        roe = _clamp_ratio(net_income / equity_for_ratio)
        debt_to_equity = _clamp_ratio(total_debt / equity_closing_for_ratio)
        gross_margin_pct = _clamp_ratio(gross_profit / revenue_for_ratio)
        net_margin_pct = _clamp_ratio(net_income / revenue_for_ratio)

        raw_share_price = _clamp_ratio(
            total_equity / max(D(str(team.shares_outstanding)), D('1')),
            limit=D('999999'),
        )

        # Distress share price floor: 0.7x book value per share
        book_value_per_share = _clamp_ratio(
            max(total_equity, D('0')) / max(D(str(team.shares_outstanding)), D('1')),
            limit=D('999999'),
        )
        share_price_floor = (book_value_per_share * D('0.7')).quantize(
            D('0.0001'), rounding=ROUND_HALF_UP,
        )
        if cash_closing < 0:
            share_price = max(raw_share_price, share_price_floor)
        else:
            share_price = raw_share_price

        # Cumulative shareholder return
        initial_share_price = (team.game.scenario.starting_cash / D('1000000')).quantize(
            D('0.0001'), rounding=ROUND_HALF_UP,
        )
        cumulative_dividends = _get_cumulative_dividends(game, team, current_round, dividends)
        if initial_share_price > 0:
            shareholder_return = _clamp_ratio(
                (share_price + cumulative_dividends - initial_share_price) / initial_share_price,
            )
        else:
            shareholder_return = D('0')

        # ── Write RoundResultFinancials ──
        RoundResultFinancials.objects.update_or_create(
            game=game, round_number=current_round, team=team,
            defaults={
                'gross_revenue': gross_revenue,
                'total_channel_margin': total_channel_margin,
                'total_revenue': total_revenue,
                'total_cogs': total_cogs,
                'gross_profit': gross_profit,
                'rd_expense': rd_expense,
                'marketing_expense': marketing_expense,
                'strategy_expense': strategy_expense,
                'research_expense': research_expense,
                'admin_overhead': admin_overhead,
                'logistics_tariff_expense': logistics_tariff,
                'inventory_expense': inventory_expense,
                'operating_income': operating_income,
                'interest_expense': interest,
                'pre_tax_income': pre_tax_income,
                'tax_expense': tax,
                'net_income': net_income,
                'cash_opening': cash_opening,
                'cash_closing': cash_closing,
                'total_assets': total_assets,
                'total_debt': total_debt,
                'total_equity': total_equity,
                'plant_book_value': plant_book_value,
                'inventory_value': inventory_value,
                'operating_cash_flow': operating_cf,
                'investing_cash_flow': investing_cf,
                'financing_cash_flow': financing_cf,
                'dividends_paid': dividends,
                'share_price': share_price,
                'roe': roe,
                'debt_to_equity': debt_to_equity,
                'gross_margin_pct': gross_margin_pct,
                'net_margin_pct': net_margin_pct,
                'shareholder_return_cumulative': shareholder_return,
            },
        )

        # ── Write RoundResultProductMarket ──
        for (t, p, m), rev in context.revenue.items():
            if t != team.id:
                continue
            cogs_data = context.cogs.get((t, p, m), {})
            log_data = context.logistics.get((t, p, m), {})
            inv_data = context.inventory_costs.get((t, p, m), {})

            RoundResultProductMarket.objects.update_or_create(
                game=game, round_number=current_round, team=team,
                team_product_id=p, market_id=m,
                defaults={
                    'units_produced': int(rev['units_produced']),
                    'units_sold': rev['units_sold'],
                    'units_unsold': rev['units_unsold'],
                    'retail_price': rev['retail_price'],
                    'distribution_strategy': rev.get('distribution_strategy', ''),
                    'channel_margin_rate': rev.get('channel_margin_rate', D('0')),
                    'channel_margin_amount': rev.get('channel_margin_home', D('0')),
                    'gross_local_revenue': rev.get('gross_local_revenue', D('0')),
                    'local_revenue': rev['local_revenue'],
                    'home_revenue': rev['home_revenue'],
                    'unit_cost': cogs_data.get('unit_cost', D('0')),
                    'total_cogs': cogs_data.get('total_cogs', D('0')),
                    'logistics_cost': log_data.get('logistics_cost', D('0')),
                    'tariff_cost': log_data.get('tariff_cost', D('0')),
                    'inventory_holding_cost': inv_data.get('inventory_cost', D('0')),
                },
            )

        # ── Write RoundResultMarketRevenue ──
        for (t, m_id), mr in context.market_revenue.items():
            if t != team.id:
                continue
            market = mr['market']
            market_profit = context.market_profit.get((team.id, m_id), D('0'))

            # Market share: team units / total units in market
            team_units = D('0')
            total_units = D('0')
            for (rt, rp, rm), rev in context.revenue.items():
                if rm == m_id:
                    total_units += rev['units_sold']
                    if rt == team.id:
                        team_units += rev['units_sold']

            market_share = (team_units / max(total_units, D('1'))).quantize(
                D('0.0001'), rounding=ROUND_HALF_UP,
            )

            RoundResultMarketRevenue.objects.update_or_create(
                game=game, round_number=current_round, team=team, market=market,
                defaults={
                    'local_revenue': mr['local_revenue'],
                    'home_revenue': mr['home_revenue'],
                    'market_profit': market_profit,
                    'market_share_pct': market_share,
                },
            )

        # ── Update Team State ──
        team.cash_on_hand = cash_closing
        team.total_debt = total_debt
        team.total_equity = total_equity

        # Distress: enter when cash < 0, recover when cash > 0 AND net_income > 0
        was_in_distress = team.is_in_distress
        if cash_closing < 0:
            team.is_in_distress = True
        elif was_in_distress and cash_closing > 0 and net_income > 0:
            team.is_in_distress = False
        # If was_in_distress but cash > 0 and net_income <= 0, stay in distress
        team.save()

        # Generate instructor alert on distress entry
        if team.is_in_distress and not was_in_distress:
            try:
                from core.models.cc21_models import InstructorAlert
                InstructorAlert.objects.create(
                    game=game,
                    team=team,
                    round_number=current_round,
                    alert_type='distress',
                    severity='critical',
                    title=f'{team.name} has entered financial distress',
                    detail=(
                        f'Cash closing: ${cash_closing:,.0f}. '
                        f'Net income: ${net_income:,.0f}. '
                        f'Total debt: ${total_debt:,.0f}. '
                        f'Consequences: +10% talent turnover, share price floor at 0.7x book value, '
                        f'cannot take new debt or make acquisitions.'
                    ),
                    teaching_note=(
                        'This team is in financial distress. Use this as a teaching moment about '
                        'cash management, debt sustainability, and the downward spiral that can '
                        'result from over-leveraging or under-pricing.'
                    ),
                )
            except Exception:
                pass  # Alert generation is non-critical

        # Store for performance/leaderboard steps
        if not hasattr(context, 'financials'):
            context.financials = {}
        context.financials[team.id] = {
            'total_revenue': total_revenue,
            'net_income': net_income,
            'share_price': share_price,
            'shareholder_return': shareholder_return,
            'debt_to_equity': debt_to_equity,
        }

    context.log.append('Financial statements generated')


def _get_cumulative_dividends(game, team, current_round, this_round_dividends):
    """Sum all dividends paid across all rounds."""
    from django.db.models import Sum
    prev = RoundResultFinancials.objects.filter(
        game=game, team=team, round_number__lt=current_round,
    ).aggregate(total=Sum('dividends_paid'))
    return (prev['total'] or D('0')) + this_round_dividends
