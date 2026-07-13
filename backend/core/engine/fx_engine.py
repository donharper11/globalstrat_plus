"""
CC-20 — FX hedge lifecycle.

Before this, an `FXHedgeDecision` persisted but was inert in the engine (no
`HedgePosition` was ever created, no mark-to-market, no P&L). This module closes
the lifecycle:

  open  — a team's FX hedge decision opens a `HedgePosition` that locks the
          current exchange rate on a notional = hedge_ratio% of the team's
          foreign-currency receivables in that currency this round;
  mark  — every round, each open position is marked to market against the
          round's effective rate;
  settle— at maturity the position realizes its P&L and books it into the round
          P&L (non-operating), via `context.sc_fx_hedge_pnl` read by
          `generate_financial_statements`.

Model: an exporter with foreign-currency receivables is naturally LONG the
foreign currency, so a hedge SHORTS it forward — it gains when the foreign
currency weakens (current rate < locked rate), offsetting the lower spot revenue
booked in `calculate_revenue`. Rates come from the round's market state
(`context.markets[*].effective_exchange_rate`, home-currency per unit foreign).
Runs after revenue, before financials.
"""
from decimal import Decimal as D, ROUND_HALF_UP

from core.engine.utils import get_config

DEFAULT_DAYS_PER_ROUND = 90  # one quarter per round


def _q(x):
    return D(str(x)).quantize(D('0.01'), rounding=ROUND_HALF_UP)


def _currency_rates(context):
    """currency_code -> current effective rate (home per unit foreign) for this
    round, averaged when several markets share a currency."""
    buckets = {}
    for state in context.markets.values():
        cur = state.market_def.currency_code
        buckets.setdefault(cur, []).append(float(state.effective_exchange_rate))
    return {c: sum(v) / len(v) for c, v in buckets.items()}


def _foreign_exposure(context, team_id, currency):
    """The team's local (foreign-currency) revenue in `currency` this round."""
    total = D('0')
    for (tid, _mid), rev in getattr(context, 'market_revenue', {}).items():
        if tid == team_id and rev['market'].currency_code == currency:
            total += rev.get('local_revenue', D('0'))
    return total


def process_fx_hedges(context):
    """Open new hedges from this round's FX decisions, mark every open position
    to market, settle matured positions, and stash realized P&L for financials."""
    from core.models.core import Round
    from core.models.sc_decisions import FXHedgeDecision
    from core.models.sc_state import HedgePosition

    context.sc_fx_hedge_pnl = {}
    rnd = Round.objects.filter(game=context.game, round_number=context.round_number).first()
    if rnd is None:
        return

    rates = _currency_rates(context)
    num_rounds = context.scenario.num_rounds
    days_per_round = get_config(context.scenario, 'fx_days_per_round',
                                default=DEFAULT_DAYS_PER_ROUND)

    # 1. Open positions from this round's FX hedge decisions.
    for dec in FXHedgeDecision.objects.filter(round=rnd, hedge_ratio__gt=0):
        foreign = (dec.currency_pair.split('_')[0] or '').upper()
        rate = rates.get(foreign)
        if rate is None:
            context.log.append(
                f'FX: no market trades {foreign}; {dec.currency_pair} hedge has no basis, skipped.')
            continue
        if HedgePosition.objects.filter(team_id=dec.team_id, currency_pair=dec.currency_pair,
                                        opened_round=rnd).exists():
            continue  # already opened this round (idempotent re-advance)
        exposure = _foreign_exposure(context, dec.team_id, foreign)
        if exposure <= 0:
            continue  # nothing to hedge
        notional = _q(exposure * D(dec.hedge_ratio) / D('100'))
        tenor_rounds = max(1, round((dec.tenor_days or DEFAULT_DAYS_PER_ROUND) / days_per_round))
        maturity_num = min(context.round_number + tenor_rounds, num_rounds)
        maturity, _ = Round.objects.get_or_create(
            game=context.game, round_number=maturity_num,
            defaults={'status': 'pending'})
        HedgePosition.objects.create(
            team_id=dec.team_id, currency_pair=dec.currency_pair, notional=notional,
            locked_rate=D(str(round(rate, 5))), opened_round=rnd, maturity_round=maturity,
            direction='short', status='open', mtm_current=D('0.00'))

    # 2. Mark-to-market every open position; settle those at/after maturity.
    settled = 0
    for pos in (HedgePosition.objects
                .filter(team__game=context.game, status='open')
                .select_related('maturity_round')):
        foreign = (pos.currency_pair.split('_')[0] or '').upper()
        rate = rates.get(foreign)
        if rate is None:
            continue
        # Short foreign receivables hedge: P&L = notional × (locked − current).
        pnl = _q(pos.notional * (pos.locked_rate - D(str(round(rate, 5)))))
        pos.mtm_current = pnl
        if pos.maturity_round.round_number <= context.round_number:
            pos.status = 'matured'
            pos.realized_pnl = pnl
            context.sc_fx_hedge_pnl[pos.team_id] = (
                context.sc_fx_hedge_pnl.get(pos.team_id, D('0')) + pnl)
            pos.save(update_fields=['mtm_current', 'status', 'realized_pnl'])
            settled += 1
        else:
            pos.save(update_fields=['mtm_current'])

    context.log.append(
        f'FX hedges processed; {settled} settled, realized P&L for '
        f'{len(context.sc_fx_hedge_pnl)} team(s).')
