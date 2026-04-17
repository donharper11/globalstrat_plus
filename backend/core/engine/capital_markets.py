"""
CC-26: AI Capital Markets Engine.

Process AI investor fund trading and calculate sentiment-driven share prices.
Called in the engine pipeline after financials (Step 12.8).
"""
from decimal import Decimal

from core.engine.utils import gaussian_fit
from core.models.cc26_models import (
    AIInvestorFund, AIInvestorHolding, SharePriceHistory,
)
from core.models.results_financials import RoundResultFinancials
from core.engine.investor_features import calculate_investor_features


def process_capital_markets(context):
    """
    Process AI investor trading for all teams.
    For each team: calculate features, evaluate each fund's satisfaction,
    execute trades, and calculate new share price.
    """
    funds = AIInvestorFund.objects.filter(scenario=context.scenario)
    if not funds.exists():
        context.log.append('CC-26: No AI investor funds configured — skipping')
        return

    # CC-32C: Load tax structure modifiers for investor satisfaction
    from core.models.cc32c_models import TeamTaxStructure
    team_tax_modifiers = {}  # team_id → {fund_code: modifier}
    for tts in TeamTaxStructure.objects.filter(
        game=context.game,
    ).select_related('current_structure'):
        structure = tts.current_structure
        if structure:
            team_tax_modifiers[tts.team_id] = {
                'granite': float(structure.value_investor_modifier),
                'greenhorizon': float(structure.esg_investor_modifier),
            }

    for team in context.teams:
        features = calculate_investor_features(
            team, context.game, context.round_number,
        )

        fund_results = []
        tax_mods = team_tax_modifiers.get(team.id, {})

        for fund in funds:
            prev_holding = AIInvestorHolding.objects.filter(
                game=context.game, fund=fund, team=team,
                round_number=context.round_number - 1,
            ).first()

            if not prev_holding:
                prev_shares = int(float(fund.initial_holding_pct) * team.shares_outstanding)
                prev_pct = fund.initial_holding_pct
            else:
                prev_shares = prev_holding.shares_held
                prev_pct = prev_holding.holding_pct

            # Calculate fund's satisfaction (CC-32C: with tax structure modifier)
            tax_mod = tax_mods.get(fund.code, 0.0)
            satisfaction = _calculate_fund_satisfaction(fund, features, tax_modifier=tax_mod)

            # Determine target holding
            target_pct = _calculate_target_holding(fund, satisfaction)

            # Gradual trade toward target
            current_pct = Decimal(str(float(prev_pct)))
            target_pct_dec = Decimal(str(target_pct))
            pct_change = (target_pct_dec - current_pct) * fund.trade_aggressiveness
            new_pct = current_pct + pct_change

            # Enforce min/max
            new_pct = max(fund.min_holding_pct, min(fund.max_holding_pct, new_pct))

            new_shares = int(float(new_pct) * team.shares_outstanding)
            shares_traded = new_shares - prev_shares

            if shares_traded > 0:
                action = 'buy'
            elif shares_traded < 0:
                action = 'sell'
            else:
                action = 'hold'

            trade_reason = _generate_trade_reason(fund, satisfaction, features, action)

            AIInvestorHolding.objects.update_or_create(
                game=context.game, fund=fund, team=team,
                round_number=context.round_number,
                defaults={
                    'shares_held': new_shares,
                    'holding_pct': new_pct,
                    'satisfaction_score': Decimal(str(round(satisfaction, 4))),
                    'action': action,
                    'shares_traded': shares_traded,
                    'trade_reason': trade_reason,
                },
            )

            fund_results.append({
                'fund': fund,
                'satisfaction': satisfaction,
                'holding_pct': float(new_pct),
                'action': action,
            })

        # Calculate new share price
        new_price = _calculate_share_price(team, fund_results, context)

        # Update financials
        financials = RoundResultFinancials.objects.filter(
            game=context.game, team=team, round_number=context.round_number,
        ).first()
        if financials:
            financials.share_price = new_price
            financials.save(update_fields=['share_price'])

        # Update team
        team.share_price = new_price
        team.save(update_fields=['share_price'])

        # Record price history
        book_value = Decimal('0')
        if financials and team.shares_outstanding > 0:
            book_value = Decimal(str(round(
                float(financials.total_equity) / team.shares_outstanding, 2,
            )))

        sentiment_mult = Decimal('1')
        if book_value > 0:
            sentiment_mult = Decimal(str(round(
                float(new_price) / float(book_value), 4,
            )))

        def _fund_sat(code):
            return Decimal(str(round(
                next((r['satisfaction'] for r in fund_results
                      if r['fund'].code == code), 0.5), 4,
            )))

        SharePriceHistory.objects.update_or_create(
            game=context.game, team=team,
            round_number=context.round_number,
            defaults={
                'book_value_per_share': book_value,
                'sentiment_multiplier': sentiment_mult,
                'share_price': new_price,
                'total_shares_outstanding': team.shares_outstanding,
                'market_cap': new_price * team.shares_outstanding,
                'velocity_satisfaction': _fund_sat('velocity'),
                'granite_satisfaction': _fund_sat('granite'),
                'greenhorizon_satisfaction': _fund_sat('greenhorizon'),
                'aggregate_demand': Decimal(str(round(
                    sum(r['satisfaction'] * r['holding_pct']
                        for r in fund_results), 4,
                ))),
            },
        )

        context.log.append(
            f'CC-26: {team.name} share price ${new_price} '
            f'(sentiment {float(sentiment_mult):.2f}x book)'
        )


def _calculate_fund_satisfaction(fund, features, tax_modifier=0.0):
    """Calculate fund satisfaction using Gaussian preference matching.
    CC-32C: tax_modifier adjusts satisfaction based on tax structure choice.
    """
    total_weighted = 0.0
    total_weight = 0.0

    for pref in fund.preferences.all():
        actual = features.get(pref.feature_code, 3.0)
        ideal = float(pref.ideal_value)
        weight = float(pref.weight)
        tolerance = float(pref.tolerance)

        if weight > 0:
            fit = gaussian_fit(actual, ideal, tolerance)
            total_weighted += fit * weight
            total_weight += weight

    base = total_weighted / total_weight if total_weight > 0 else 0.5
    # CC-32C: Apply tax structure modifier (clamped to 0-1)
    return max(0.0, min(1.0, base + tax_modifier))


def _calculate_target_holding(fund, satisfaction):
    """Determine target holding % based on satisfaction."""
    min_pct = float(fund.min_holding_pct)
    max_pct = float(fund.max_holding_pct)
    initial = float(fund.initial_holding_pct)

    if satisfaction >= 0.7:
        return max_pct
    elif satisfaction >= 0.5:
        t = (satisfaction - 0.5) / 0.2
        return initial + (max_pct - initial) * t
    elif satisfaction >= 0.3:
        t = (satisfaction - 0.3) / 0.2
        return min_pct + (initial - min_pct) * t
    else:
        return min_pct


def _calculate_share_price(team, fund_results, context):
    """Calculate share price from book value adjusted by investor sentiment."""
    financials = RoundResultFinancials.objects.filter(
        game=context.game, team=team, round_number=context.round_number,
    ).first()

    if not financials or team.shares_outstanding <= 0:
        return Decimal('1.00')

    book_value = float(financials.total_equity) / team.shares_outstanding
    if book_value <= 0:
        book_value = 0.01

    # Weighted satisfaction
    total_active_pct = sum(r['holding_pct'] for r in fund_results)
    if total_active_pct > 0:
        weighted_satisfaction = sum(
            r['satisfaction'] * (r['holding_pct'] / total_active_pct)
            for r in fund_results
        )
    else:
        weighted_satisfaction = 0.5

    # Sentiment: 0.0 sat → 0.70x, 0.5 sat → 1.00x, 1.0 sat → 1.30x
    sentiment = 0.70 + (weighted_satisfaction * 0.60)

    raw_price = book_value * sentiment

    # Price floor: 70% of book value
    raw_price = max(raw_price, book_value * 0.70)

    # Smooth: cap change at ±20% per round
    prev_history = SharePriceHistory.objects.filter(
        game=context.game, team=team,
        round_number=context.round_number - 1,
    ).first()

    if prev_history:
        prev_price = float(prev_history.share_price)
        max_change = prev_price * 0.20
        if raw_price > prev_price + max_change:
            raw_price = prev_price + max_change
        elif raw_price < prev_price - max_change:
            raw_price = prev_price - max_change

    return Decimal(str(round(max(raw_price, 0.01), 2)))


def _generate_trade_reason(fund, satisfaction, features, action):
    """Generate human-readable reason for trade decision."""
    best_feature = None
    best_fit = 0
    worst_feature = None
    worst_fit = 1

    for pref in fund.preferences.all():
        actual = features.get(pref.feature_code, 3.0)
        fit = gaussian_fit(actual, float(pref.ideal_value), float(pref.tolerance))
        weighted = fit * float(pref.weight)

        if weighted > best_fit:
            best_fit = weighted
            best_feature = pref.feature_label
        if weighted < worst_fit:
            worst_fit = weighted
            worst_feature = pref.feature_label

    reasons = []
    if action == 'buy':
        reasons.append(f"Increased position — impressed by {best_feature}")
        if satisfaction > 0.7:
            reasons.append(
                f"Strong overall alignment with {fund.name}'s investment thesis"
            )
    elif action == 'sell':
        reasons.append(f"Reduced position — concerned about {worst_feature}")
        if satisfaction < 0.3:
            reasons.append(
                f"Significant misalignment with {fund.name}'s criteria"
            )
    else:
        reasons.append("Maintaining position — mixed signals")

    return '. '.join(reasons)
