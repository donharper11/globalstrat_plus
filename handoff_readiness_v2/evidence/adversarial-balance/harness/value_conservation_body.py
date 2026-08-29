"""Value conservation for FX, trade finance, sourcing and inventory.

Inventory first, then one multi-round counterfactual per mechanism against an
unchanged control. Complete cash and value ledgers are compared, not the index:
a loop that creates cash while the composite ignores it is still a loop.

Every arm proves its mutation reached the persisted row. An arm whose mechanism
the scenario cannot express is recorded as unexercisable with the reason, never
as a pass -- the trade-finance instrument catalogue is empty in this scenario,
which the progressive-disclosure probe established first.
"""
import time

from decimal import Decimal as D
from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

import counterfactual as CF
import fixture as F
import search_body as S

SEED = 'crv2-06-value-conservation'
ROUNDS = 3

LEDGER = ('cash_closing', 'total_revenue', 'net_income', 'operating_income',
          'strategy_expense')


def run(verbose=True):
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('value-cons', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    call_command('setup_test_game', verbosity=0)

    from core.models import (DecisionSubmission, Game, Round, Team,
                             TradeFinanceInstrument)
    from core.models.decisions import DecisionMarketing
    from core.models.results_financials import RoundResultFinancials
    from core.models.sc_decisions import (FXHedgeDecision, InventoryDecision,
                                          SourcingAllocation,
                                          TradeFinanceDecision)
    from core.models.sc_models import Supplier
    from core.models.scenario import MarketDefinition
    from core.models.team_state import TeamProduct

    game = Game.objects.order_by('-id').first()
    F.apply(game, SEED)
    game.refresh_from_db()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    subject = teams[0]

    # ---- inventory of legal fields and their engine cash/value effects ----
    inventory_of_fields = {
        'fx': {
            'model': 'FXHedgeDecision',
            'fields': ['currency_pair', 'hedge_ratio', 'tenor_days'],
            'engine_effect': (
                'fx_engine.process_fx_hedges opens a short position sized '
                'exposure x hedge_ratio/100, charges a premium of '
                'fx_hedge_premium_bps on the notional immediately, marks to '
                'market each round and books realised P&L at maturity into '
                'context.sc_fx_hedge_pnl, which financials adds to pre-tax '
                'income. A hedge is skipped entirely when exposure <= 0.'),
        },
        'trade_finance': {
            'model': 'TradeFinanceDecision / SinosureEnrollment',
            'fields': ['buyer_payment_instrument', 'lc_doc_prep_investment',
                       'coverage_pct'],
            'engine_effect': (
                'buyer_payment_instrument is validated against the scenario '
                'TradeFinanceInstrument catalogue.'),
        },
        'sourcing': {
            'model': 'SourcingAllocation',
            'fields': ['critical_input_category', 'supplier', 'allocation_pct',
                       'volume_commitment_units', 'payment_terms'],
            'engine_effect': (
                'sc_engine consumes allocations for disruption exposure and '
                'books disruption/mitigation cost into '
                'context.sc_disruption_costs, an operating expense.'),
        },
        'inventory': {
            'model': 'InventoryDecision',
            'fields': ['buffer_days', 'safety_stock_trigger_pct'],
            'engine_effect': (
                'costs.calculate_inventory_costs values unsold units at '
                'unit_cost and charges holding cost at '
                'inventory_holding_cost_pct; financials carries '
                'inventory_value on the balance sheet and treats the change '
                'as a working-capital movement in operating cash flow.'),
        },
    }

    # Which currencies does the subject actually earn in? A hedge is skipped
    # entirely when exposure <= 0, so hedging a currency the team never sells
    # in measures the skip, not the hedge. The first run of this probe did
    # exactly that -- production was pinned at zero, so there was no exposure
    # in any currency and both FX arms reported a flat zero that proved
    # nothing about double-hedging.
    from core.models.team_state import TeamProductMarket
    sold_markets = list(MarketDefinition.objects.filter(
        id__in=TeamProductMarket.objects.filter(
            team_product__team=subject, is_active=True
        ).values_list('market_id', flat=True)))
    subject_currencies = sorted({m.currency_code for m in sold_markets})
    home_currency = (subject.home_market.currency_code
                     if subject.home_market else None)
    foreign_currencies = [c for c in subject_currencies if c != home_currency]

    instruments = list(TradeFinanceInstrument.objects.filter(
        scenario=game.scenario).values_list('instrument_id', flat=True))
    suppliers = list(Supplier.objects.filter(scenario=game.scenario)[:2])
    market = MarketDefinition.objects.filter(
        scenario=game.scenario).order_by('id').first()
    product = TeamProduct.objects.filter(
        team=subject, status='active').order_by('id').first()

    report = {
        'seed': SEED,
        'identity': F.identity_for(SEED),
        'subject_team': subject.name,
        'rounds': ROUNDS,
        'field_inventory': inventory_of_fields,
        'scenario_supports': {
            'trade_finance_instruments': len(instruments),
            'suppliers': len(suppliers),
            'subject_currencies': subject_currencies,
            'home_currency': home_currency,
            'foreign_currencies': foreign_currencies,
        },
        'arms': {},
        'evaluations': 0,
    }

    def ledger_capture(into):
        rows = {}
        for rnd_no in range(1, game.current_round + 1):
            fin = RoundResultFinancials.objects.filter(
                game=game, team=subject, round_number=rnd_no).first()
            if fin is None:
                continue
            rows[rnd_no] = {f: str(getattr(fin, f)) for f in LEDGER}
            rows[rnd_no]['inventory_value'] = str(fin.inventory_value)
            rows[rnd_no]['cash_plus_inventory'] = str(
                D(str(fin.cash_closing)) + D(str(fin.inventory_value)))
        into['ledger'] = rows

    def evaluate(label, mutate, prove, production_volume=None):
        """One multi-round arm, rolled back, with a proof it landed."""
        from core.engine.advance_round import _run_phase_1, advance_to_next_round
        proof = {}
        game.refresh_from_db()
        start = game.current_round
        first = Round.objects.get(game=game, round_number=start)
        before = CF.fingerprint(game, first)
        captured = {}
        try:
            with transaction.atomic():
                for step in range(ROUNDS):
                    game.refresh_from_db()
                    rnd = Round.objects.get(game=game,
                                            round_number=game.current_round)
                    for team in teams:
                        submission, _ = DecisionSubmission.objects.get_or_create(
                            team=team, round=rnd, defaults={'status': 'draft'})
                        S.write_candidate(submission, team, None)
                        if production_volume is not None:
                            DecisionMarketing.objects.filter(
                                submission=submission).update(
                                    production_volume=production_volume,
                                    demand_estimate=0)
                        if team.id == subject.id and mutate is not None:
                            mutate(rnd, submission, team)
                        submission.status = 'locked'
                        submission.locked_at = timezone.now()
                        submission.save(update_fields=['status', 'locked_at'])
                    if mutate is not None and step == 0:
                        proof.update(prove(rnd) or {})
                    _run_phase_1(game.id)
                    if step < ROUNDS - 1:
                        advance_to_next_round(game.id)
                ledger_capture(captured)
                raise CF._Rollback()
        except CF._Rollback:
            pass
        game.refresh_from_db()
        after = CF.fingerprint(game, first)
        if after != before:
            raise AssertionError(
                f'{label}: the database did not return to the checkpoint')
        report['evaluations'] += 1
        return {'ledger': captured.get('ledger', {}), 'proof': proof}

    started = time.time()

    # ---- control: production and sales pinned at zero --------------------
    control = evaluate('control', None, None, production_volume=0)
    report['control'] = control

    def arm(label, mutate, prove, production_volume=0, why=''):
        result = evaluate(label, mutate, prove,
                          production_volume=production_volume)
        deltas = {}
        for rnd_no, row in result['ledger'].items():
            base = control['ledger'].get(rnd_no, {})
            deltas[rnd_no] = {
                k: str(D(row[k]) - D(base[k])) if k in base else None
                for k in row}
        result['delta_vs_control'] = deltas
        result['why'] = why
        # Value creation: cash plus inventory rising against the control with
        # no external inflow is the thing every one of these arms is looking
        # for.
        result['creates_value'] = any(
            d.get('cash_plus_inventory') is not None
            and D(d['cash_plus_inventory']) > 0
            for d in deltas.values())
        report['arms'][label] = result
        if verbose:
            last = max(deltas) if deltas else None
            print(f"  {label:<34} creates_value={result['creates_value']} "
                  f"cash+inv delta="
                  f"{deltas.get(last, {}).get('cash_plus_inventory')}",
                  flush=True)
        return result

    # ---- FX arms, only where the subject has real exposure --------------
    from core.models.sc_state import HedgePosition

    def hedge_engagement(rnd):
        return HedgePosition.objects.filter(
            team=subject, opened_round=rnd).count()

    if foreign_currencies:
        hedged = foreign_currencies[0]
        pair_a = f'{hedged}_{home_currency}'
        second_market = next(
            (m for m in sold_markets
             if m.currency_code == hedged), None)

        def fx_no_exposure(rnd, submission, team):
            # A currency the team demonstrably does not trade in.
            FXHedgeDecision.objects.update_or_create(
                team=team, round=rnd, currency_pair='ZZZ_USD',
                defaults={'hedge_ratio': 100, 'tenor_days': 90})

        def fx_prove(rnd):
            row = FXHedgeDecision.objects.filter(
                team=subject, round=rnd, currency_pair='ZZZ_USD').first()
            return {'reached_row': row is not None,
                    'hedge_ratio': getattr(row, 'hedge_ratio', None),
                    'positions_opened': hedge_engagement(rnd),
                    'mechanism_engaged': False}

        arm('fx_no_exposure_max_hedge', fx_no_exposure, fx_prove,
            production_volume=20000,
            why='largest legal hedge on a currency the team does not trade '
                'in, with sales running so exposure exists elsewhere; the '
                'engine must skip it and it must not create cash from nothing')

        def fx_double(rnd, submission, team):
            for pair in (pair_a, f'{hedged}_XXX'):
                FXHedgeDecision.objects.update_or_create(
                    team=team, round=rnd, currency_pair=pair,
                    defaults={'hedge_ratio': 100, 'tenor_days': 90})

        def fx_double_prove(rnd):
            rows = list(FXHedgeDecision.objects.filter(
                team=subject, round=rnd,
                currency_pair__in=(pair_a, f'{hedged}_XXX')))
            opened = hedge_engagement(rnd)
            return {'reached_row': len(rows) == 2,
                    'pairs': sorted(r.currency_pair for r in rows),
                    'positions_opened': opened,
                    'mechanism_engaged': opened > 0,
                    'double_hedged': opened >= 2}

        arm('fx_two_pairs_one_exposure', fx_double, fx_double_prove,
            production_volume=20000,
            why=f'two pairs both naming {hedged} as the foreign currency. '
                f'Positions are keyed per currency pair while exposure is '
                f'looked up per foreign currency, so each opens a '
                f'full-notional hedge against the same underlying exposure')
    else:
        for name in ('fx_no_exposure_max_hedge', 'fx_two_pairs_one_exposure'):
            report['arms'][name] = {
                'unexercisable': (
                    'the subject sells only in its home currency '
                    f'({home_currency}), so it has no foreign exposure and '
                    'every hedge is skipped by design. The FX mechanism '
                    'cannot be exercised for this team in this fixture and is '
                    'not claimed as passing.'),
            }

    # ---- Sourcing: allocation varied with production and sales at zero ---
    if suppliers:
        def sourcing(rnd, submission, team):
            SourcingAllocation.objects.update_or_create(
                team=team, round=rnd,
                critical_input_category='cells', supplier=suppliers[0],
                defaults={'allocation_pct': 100,
                          'volume_commitment_units': 500000,
                          'payment_terms': 'net_30'})

        def sourcing_prove(rnd):
            row = SourcingAllocation.objects.filter(
                team=subject, round=rnd, supplier=suppliers[0]).first()
            return {'reached_row': row is not None,
                    'allocation_pct': getattr(row, 'allocation_pct', None),
                    'volume_commitment_units': getattr(
                        row, 'volume_commitment_units', None)}

        arm('sourcing_commitment_zero_production', sourcing, sourcing_prove,
            why='supplier allocation and volume commitment with production '
                'and sales at zero; must not create inventory, revenue or a '
                'negative expense')
    else:
        report['arms']['sourcing_commitment_zero_production'] = {
            'unexercisable': 'the scenario declares no suppliers'}

    # ---- Inventory: build and carry with sales at zero -------------------
    def inventory_build(rnd, submission, team):
        InventoryDecision.objects.update_or_create(
            team=team, round=rnd, product=product, market=market,
            defaults={'buffer_days': 180, 'safety_stock_trigger_pct': 90})

    def inventory_prove(rnd):
        row = InventoryDecision.objects.filter(
            team=subject, round=rnd, product=product, market=market).first()
        return {'reached_row': row is not None,
                'buffer_days': getattr(row, 'buffer_days', None)}

    arm('inventory_build_carry_no_sales', inventory_build, inventory_prove,
        production_volume=20000,
        why='build and carry stock across rounds with sales at zero; closing '
            'cash plus inventory value must not rise without an external '
            'inflow, and the same stock must not be monetised twice')

    # ---- Trade finance: unexercisable if the catalogue is empty ----------
    if instruments:
        def trade_finance(rnd, submission, team):
            from core.models.scenario import SegmentDefinition
            segment = SegmentDefinition.objects.filter(
                scenario=game.scenario,
                segment_type='customer').order_by('id').first()
            instrument = instruments[rnd.round_number % len(instruments)]
            TradeFinanceDecision.objects.update_or_create(
                team=team, round=rnd, segment=segment, market=market,
                defaults={'buyer_payment_instrument': instrument,
                          'lc_doc_prep_investment': 'diligent'})

        def tf_prove(rnd):
            row = TradeFinanceDecision.objects.filter(
                team=subject, round=rnd).first()
            return {'reached_row': row is not None,
                    'instrument': getattr(row, 'buyer_payment_instrument', None)}

        arm('trade_finance_instrument_cycled', trade_finance, tf_prove,
            why='cycle the legal instrument while the trade is held constant; '
                'fees, coverage and settlement must not duplicate proceeds or '
                'turn a cost into income')
    else:
        report['arms']['trade_finance_instrument_cycled'] = {
            'unexercisable': (
                'the scenario declares no TradeFinanceInstrument rows, so '
                'buyer_payment_instrument has no legal value: the write '
                'serializer validates against that catalogue. The mechanism '
                'cannot be exercised in this scenario and is not claimed as '
                'passing.'),
        }

    # An arm whose mechanism never engaged has not tested it. Recorded so a
    # skipped hedge cannot be read as a hedge that behaved.
    report['inconclusive_arms'] = [
        name for name, a in report['arms'].items()
        if 'proof' in a and a['proof'].get('mechanism_engaged') is False
        and name != 'fx_no_exposure_max_hedge']
    report['arms_creating_value'] = [
        name for name, arm_result in report['arms'].items()
        if arm_result.get('creates_value')]
    report['unexercisable_arms'] = [
        name for name, arm_result in report['arms'].items()
        if arm_result.get('unexercisable')]
    report['all_mutations_reached_their_row'] = all(
        arm_result['proof'].get('reached_row')
        for arm_result in report['arms'].values()
        if 'proof' in arm_result and arm_result['proof'])
    report['elapsed_seconds'] = round(time.time() - started, 1)
    return report
