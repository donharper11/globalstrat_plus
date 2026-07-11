"""
Starting supply-chain posture (UX #8).

Students take over an ongoing operation, not a blank startup — so a game should
open with a sensible SC posture already in place rather than empty pages. This is
seeded at game start (see ``SimulationInstanceActionView._start``) and can also be
run manually via ``manage.py seed_sc_posture``.

Seeding is done directly via the ORM: it represents inherited state, so it is not
subject to the per-round progressive-disclosure gates that apply to student edits.
Idempotent: existing SC decisions for a team+round are replaced.
"""
from core.models.sc_models import Supplier, ShippingLane, TradeFinanceInstrument
from core.models.scenario import MarketDefinition, SegmentDefinition
from core.models.sc_decisions import (
    SourcingDecision, SourcingAllocation, LogisticsDecision,
    TradeFinanceDecision, InventoryDecision,
)
from core.models.team_state import TeamProduct
from core.models.core import Team


def _mode_available(lane, mode):
    e = (lane.modes or {}).get(mode)
    return bool(e) and e.get('available', True) is not False


def seed_starting_posture(game, rnd):
    """
    Seed a starting SC posture for every team in ``game`` at round ``rnd``.
    Returns the number of teams seeded. Safe to call repeatedly.
    """
    scenario = game.scenario

    suppliers = list(Supplier.objects.filter(scenario=scenario))
    if not suppliers:
        return 0  # scenario has no SC content — nothing to seed

    by_spec = {}
    for s in suppliers:
        for sp in (s.specialization or []):
            by_spec.setdefault(sp, []).append(s)
    for sp in by_spec:
        by_spec[sp].sort(key=lambda x: x.base_unit_price_usd)  # cheapest default

    lanes = list(ShippingLane.objects.filter(scenario=scenario))
    sea_lanes = [l for l in lanes if _mode_available(l, 'sea')][:2]
    home_market = (MarketDefinition.objects.filter(scenario=scenario, code='NA').first()
                   or MarketDefinition.objects.filter(scenario=scenario).order_by('display_order').first())
    segment = SegmentDefinition.objects.filter(scenario=scenario, segment_type='customer').first()
    has_lc = TradeFinanceInstrument.objects.filter(scenario=scenario, instrument_id='letter_of_credit').exists()

    teams = Team.objects.filter(game=game)
    for team in teams:
        # Idempotent: replace any existing SC decisions for this team+round.
        SourcingAllocation.objects.filter(team=team, round=rnd).delete()
        SourcingDecision.objects.filter(team=team, round=rnd).delete()
        LogisticsDecision.objects.filter(team=team, round=rnd).delete()
        TradeFinanceDecision.objects.filter(team=team, round=rnd).delete()
        InventoryDecision.objects.filter(team=team, round=rnd).delete()

        SourcingDecision.objects.create(team=team, round=rnd,
                                        multi_sourcing_strategy='single_source',
                                        tier_2_3_visibility_investment='none')
        for sp, sups in by_spec.items():
            SourcingAllocation.objects.create(
                team=team, round=rnd, critical_input_category=sp,
                supplier=sups[0], allocation_pct=100, volume_commitment_units=0, payment_terms='')

        for lane in sea_lanes:
            LogisticsDecision.objects.create(
                team=team, round=rnd, lane=lane,
                mode_sea_pct=100, mode_air_pct=0, mode_rail_pct=0, mode_road_pct=0)

        if home_market:
            for prod in TeamProduct.objects.filter(team=team, status='active'):
                InventoryDecision.objects.create(
                    team=team, round=rnd, product=prod, market=home_market,
                    buffer_days=30, safety_stock_trigger_pct=20)

        if has_lc and segment and home_market:
            TradeFinanceDecision.objects.create(
                team=team, round=rnd, segment=segment, market=home_market,
                buyer_payment_instrument='letter_of_credit', lc_doc_prep_investment='standard')

    return teams.count()
