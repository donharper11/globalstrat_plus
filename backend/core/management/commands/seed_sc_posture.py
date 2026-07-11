"""
Seed a starting supply-chain posture for every team in a game (UX #8).

Students take over an ongoing operation, not a blank startup — so a fresh game
should open with a sensible SC posture already in place rather than empty pages.
This seeds, per team, at the target round (default: the game's open round):

  - Sourcing: single-source each critical input to a default supplier (100%).
  - Logistics: ship 100% by sea on a couple of the team's key lanes.
  - Inventory: a 30-day buffer / 20% reorder trigger for each active product+market.
  - Trade finance: Letter of Credit for the first customer segment in the home market.

Seeding is done directly via the ORM (it represents inherited state, so it is not
subject to the per-round progressive-disclosure gates that apply to student edits).
Idempotent: existing SC decisions for the team+round are replaced.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models.core import Game, Team, Round
from core.models.sc_models import Supplier, ShippingLane, TradeFinanceInstrument
from core.models.scenario import MarketDefinition, SegmentDefinition
from core.models.sc_decisions import (
    SourcingDecision, SourcingAllocation, LogisticsDecision,
    TradeFinanceDecision, InventoryDecision,
)
from core.models.team_state import TeamProduct


def _mode_available(lane, mode):
    e = (lane.modes or {}).get(mode)
    return bool(e) and e.get('available', True) is not False


class Command(BaseCommand):
    help = 'Seed a starting supply-chain posture for all teams in a game.'

    def add_arguments(self, parser):
        parser.add_argument('--game', type=int, required=True, help='Game id')
        parser.add_argument('--round', type=int, default=None,
                            help='Round number (default: the open round)')

    @transaction.atomic
    def handle(self, *args, **opts):
        game = Game.objects.filter(id=opts['game']).first()
        if not game:
            raise CommandError(f"Game {opts['game']} not found.")
        scenario = game.scenario

        if opts['round']:
            rnd = Round.objects.filter(game=game, round_number=opts['round']).first()
        else:
            rnd = Round.objects.filter(game=game, status='open').order_by('round_number').first()
        if not rnd:
            raise CommandError('No target round found (specify --round).')

        suppliers = list(Supplier.objects.filter(scenario=scenario))
        # default supplier per specialization = lowest unit price
        by_spec = {}
        for s in suppliers:
            for sp in (s.specialization or []):
                by_spec.setdefault(sp, []).append(s)
        for sp in by_spec:
            by_spec[sp].sort(key=lambda x: x.base_unit_price_usd)

        lanes = list(ShippingLane.objects.filter(scenario=scenario))
        sea_lanes = [l for l in lanes if _mode_available(l, 'sea')][:2]
        home_market = MarketDefinition.objects.filter(scenario=scenario, code='NA').first() \
            or MarketDefinition.objects.filter(scenario=scenario).order_by('display_order').first()
        segment = SegmentDefinition.objects.filter(scenario=scenario, segment_type='customer').first()
        has_lc = TradeFinanceInstrument.objects.filter(scenario=scenario, instrument_id='letter_of_credit').exists()

        teams = Team.objects.filter(game=game)
        for team in teams:
            # wipe any existing SC decisions for this team+round (idempotent)
            SourcingAllocation.objects.filter(team=team, round=rnd).delete()
            SourcingDecision.objects.filter(team=team, round=rnd).delete()
            LogisticsDecision.objects.filter(team=team, round=rnd).delete()
            TradeFinanceDecision.objects.filter(team=team, round=rnd).delete()
            InventoryDecision.objects.filter(team=team, round=rnd).delete()

            # Sourcing — single-source each critical input to the cheapest supplier.
            SourcingDecision.objects.create(team=team, round=rnd,
                                            multi_sourcing_strategy='single_source',
                                            tier_2_3_visibility_investment='none')
            for sp, sups in by_spec.items():
                SourcingAllocation.objects.create(
                    team=team, round=rnd, critical_input_category=sp,
                    supplier=sups[0], allocation_pct=100,
                    volume_commitment_units=0, payment_terms='')

            # Logistics — 100% sea on a couple of key lanes.
            for lane in sea_lanes:
                LogisticsDecision.objects.create(
                    team=team, round=rnd, lane=lane,
                    mode_sea_pct=100, mode_air_pct=0, mode_rail_pct=0, mode_road_pct=0)

            # Inventory — a starting buffer for each active product in the home market.
            if home_market:
                for prod in TeamProduct.objects.filter(team=team, status='active'):
                    InventoryDecision.objects.create(
                        team=team, round=rnd, product=prod, market=home_market,
                        buffer_days=30, safety_stock_trigger_pct=20)

            # Trade finance — Letter of Credit for the first customer segment.
            if has_lc and segment and home_market:
                TradeFinanceDecision.objects.create(
                    team=team, round=rnd, segment=segment, market=home_market,
                    buyer_payment_instrument='letter_of_credit', lc_doc_prep_investment='standard')

        self.stdout.write(self.style.SUCCESS(
            f"Seeded starting SC posture for {teams.count()} team(s) in "
            f'"{game.name}" at round {rnd.round_number}.'))
