"""
CC-22 / rework W5: real multi-round outcome-verification E2E.

The original CC-22 test (`test_cc22_e2e.py`) is a smoke-and-persistence check:
it proves ONE round advances without crashing and that decisions persist. This
test closes the gap its own spec §2 advertises — "10 rounds with automated
decisions + event injection + expected-outcome verification" — now that CC-19
produces real SC outputs.

It drives the REAL SC engine functions across 10 real Round rows for TWO teams
with contrasting supply-chain postures, injects a disruption (the seeded
"Taiwan Earthquake" SC event forced to fire once), and asserts the OUTCOMES the
mechanic is supposed to produce — not merely no-crash:

  1. Baseline: before the disruption both teams run undisrupted
     (capacity_factor == 1, lost_revenue == 0).
  2. Resilience trend: the diversified/hedged team out-scores the fragile
     single-source team EVERY round.
  3. Lost sales on disruption: on the shock round the fragile team's production
     capacity drops and it books lost revenue; the resilient team (dual-source +
     contingency reroute) loses materially less.
  4. Recovery: capacity and lost-sales return to baseline after the event's
     recovery window (real recovery carry-forward in run_sc_state across rounds).
  5. Determinism: an identical parallel game reproduces the same resilience-score
     and capacity-factor trajectories exactly.

Scope note (honest): this harness runs the SC engine steps in their real
pipeline order (run_sc_state -> calculate_revenue Channel-1 ->
calculate_sc_disruption_costs Channel-2 -> score_sc_resilience) against real DB
state, so multi-round recovery carry-forward is genuinely exercised. It does not
also run the full adoption/financials pipeline (adoption is seeded), because W5
is about SC *outcomes*, not re-testing the whole engine — that path is covered
by the CC-22 advance-round smoke test.
"""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models.core import Game, Team, Round
from core.models.scenario import (
    Scenario, MarketDefinition, SegmentDefinition, FirmStarterProfile,
    PlatformGenerationDefinition, EventTemplateDefinition,
)
from core.models.sc_models import Supplier, ShippingLane
from core.models.sc_decisions import (
    SourcingDecision, SourcingAllocation, LogisticsDecision,
    InventoryDecision, ContingencyPlan,
)
from core.models.sc_state import ResilienceScoreHistory
from core.models.team_state import TeamPlatform, TeamProduct
from core.models.decisions import DecisionSubmission, DecisionMarketing
from core.models.results import RoundResultAdoption
from core.engine.sc_engine import (
    run_sc_state, calculate_sc_disruption_costs, score_sc_resilience,
)
from core.engine.revenue import calculate_revenue


NUM_ROUNDS = 10
DISRUPT_ROUND = 5
EVENT_RECOVERY_ROUNDS = 3       # sc_effects.recovery_rounds on the seeded event
DEMAND_PER_ROUND = 1000
RETAIL_PRICE = D('500')
UNIT_COST = D('300')


class _Ctx:
    """Minimal RoundContext stand-in accepted by the SC steps + calculate_revenue
    (mirrors the one in test_cc19_sc_engine)."""
    def __init__(self, game, round_number, teams, scenario):
        self.game = game
        self.round_number = round_number
        self.teams = teams
        self.scenario = scenario
        self.markets = {}
        self.log = []


def _mode_available(lane, mode):
    e = (lane.modes or {}).get(mode)
    return bool(e) and e.get('available', True) is not False


class CC22MultiRoundE2ETest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('load_scenario', file='scenarios/consumer_electronics_2026.yaml')
        cls.scenario = Scenario.objects.get(name='Consumer Electronics 2026')

        # Silence random SC events; we inject one deterministically below.
        EventTemplateDefinition.objects.filter(
            scenario=cls.scenario, category='supply_chain').update(probability_per_round=0)

        cls.creator = get_user_model().objects.create_user('cc22mr', password='x')
        cls.market = MarketDefinition.objects.filter(scenario=cls.scenario, code='NA').first()
        cls.segment = SegmentDefinition.objects.filter(
            scenario=cls.scenario, segment_type='customer').first()
        cls.tsmc = Supplier.objects.get(scenario=cls.scenario, supplier_id='tsmc_taiwan')      # TW, disrupted
        cls.samsung = Supplier.objects.get(scenario=cls.scenario, supplier_id='samsung_foundry_korea')  # KR, healthy
        cls.lane = next(l for l in ShippingLane.objects.filter(scenario=cls.scenario)
                        if _mode_available(l, 'sea'))

    # -- game construction ----------------------------------------------
    def _make_game(self, name):
        profile = FirmStarterProfile.objects.filter(scenario=self.scenario).first()
        gen = PlatformGenerationDefinition.objects.filter(
            scenario=self.scenario).order_by('generation_order').first()
        game = Game.objects.create(scenario=self.scenario, name=name,
                                   created_by=self.creator, status='active')
        teams = {}
        for key, tname in (('fragile', 'Fragile Single-Source'), ('resilient', 'Resilient Diversified')):
            team = Team.objects.create(
                game=game, name=tname, firm_starter_profile=profile,
                performance_index=D('100'), cash_on_hand=D('50000000'), total_equity=D('50000000'))
            platform = TeamPlatform.objects.create(team=team, platform_generation=gen, status='active')
            product = TeamProduct.objects.create(
                team=team, team_platform=platform, name=f'{tname} Phone',
                positioning='premium', created_round=1)
            teams[key] = (team, product)
        return game, teams

    def _seed_round(self, game, teams, rnd, r):
        """Seed both teams' SC decisions + a locked marketing decision + adoption
        for round r. Fragile = 100% tsmc, no contingency, thin buffer. Resilient =
        50/50 tsmc/samsung across TW+KR, deep buffer, reroute-to-samsung rule."""
        for key, (team, product) in teams.items():
            # Sourcing
            SourcingDecision.objects.update_or_create(
                team=team, round=rnd, defaults=dict(
                    multi_sourcing_strategy='single_source' if key == 'fragile' else 'dual_source',
                    tier_2_3_visibility_investment='none' if key == 'fragile' else 'comprehensive'))
            SourcingAllocation.objects.filter(team=team, round=rnd).delete()
            if key == 'fragile':
                SourcingAllocation.objects.create(
                    team=team, round=rnd, critical_input_category='semiconductor',
                    supplier=self.tsmc, allocation_pct=100, payment_terms='', volume_commitment_units=0)
            else:
                SourcingAllocation.objects.create(
                    team=team, round=rnd, critical_input_category='semiconductor',
                    supplier=self.tsmc, allocation_pct=50, payment_terms='', volume_commitment_units=0)
                SourcingAllocation.objects.create(
                    team=team, round=rnd, critical_input_category='semiconductor',
                    supplier=self.samsung, allocation_pct=50, payment_terms='', volume_commitment_units=0)

            # Logistics (sea, one lane)
            LogisticsDecision.objects.update_or_create(
                team=team, round=rnd, lane=self.lane, defaults=dict(
                    mode_sea_pct=100, mode_air_pct=0, mode_rail_pct=0, mode_road_pct=0))

            # Inventory buffer: thin for fragile, deep for resilient
            InventoryDecision.objects.update_or_create(
                team=team, round=rnd, product=product, market=self.market, defaults=dict(
                    buffer_days=10 if key == 'fragile' else 60,
                    safety_stock_trigger_pct=D('15') if key == 'fragile' else D('40')))

            # Contingency: resilient reroutes disrupted semiconductor volume to Samsung
            if key == 'resilient':
                ContingencyPlan.objects.update_or_create(
                    team=team, round=rnd, defaults=dict(
                        disruption_response_playbook='reroute to KR on TW shock',
                        alt_supplier_activation_rules=[{
                            'input_category': 'semiconductor', 'trigger': 'disruption',
                            'backup_supplier_id': self.samsung.id, 'shift_pct': 50}],
                        mode_switch_triggers=[]))

            # Locked submission + marketing + adoption so revenue produces real units
            sub, _ = DecisionSubmission.objects.update_or_create(
                team=team, round=rnd, defaults={'status': 'locked'})
            DecisionMarketing.objects.update_or_create(
                submission=sub, team_product=product, market=self.market, defaults=dict(
                    retail_price=RETAIL_PRICE, promotion_budget=D('0'), campaign_focus_feature_ids=[],
                    channel_digital_pct=D('1'), channel_traditional_pct=D('0'), channel_trade_pct=D('0'),
                    distribution_strategy='hybrid', distribution_investment=D('0'),
                    demand_estimate=DEMAND_PER_ROUND, production_volume=DEMAND_PER_ROUND,
                    production_source_market=self.market))
            RoundResultAdoption.objects.update_or_create(
                game=game, round_number=r, team=team, market=self.market, best_product=product,
                segment=self.segment, defaults=dict(
                    fit_score=D('0.5'), adjusted_fit_score=D('0.5'), market_readiness_pct=D('1'),
                    adoption_pool=D(str(DEMAND_PER_ROUND)), team_attractiveness=D('1'),
                    team_share_pct=D('1'), new_adopters=D(str(DEMAND_PER_ROUND)),
                    cumulative_adopters=D(str(DEMAND_PER_ROUND))))

    def _run_sc_round(self, game, teams, r):
        """Run the real SC engine steps in pipeline order for one round; return
        the per-team context outputs plus the persisted resilience rows."""
        rnd = Round.objects.create(game=game, round_number=r, status='open')
        self._seed_round(game, teams, rnd, r)
        team_objs = [teams['fragile'][0], teams['resilient'][0]]
        ctx = _Ctx(game, r, team_objs, self.scenario)

        run_sc_state(ctx)                        # fires event @ DISRUPT_ROUND, carries recovery fwd
        calculate_revenue(ctx)                   # Channel-1 lost sales
        ctx.cogs = {                             # real COGS for Channel-2 mitigation pricing
            k: {'total_cogs': D(str(v.get('units_produced') or 0)) * UNIT_COST}
            for k, v in ctx.revenue.items()}
        calculate_sc_disruption_costs(ctx)       # Channel-2 real costs
        score_sc_resilience(ctx)                 # persists ResilienceScoreHistory

        out = {}
        for key, (team, _p) in teams.items():
            rs = ResilienceScoreHistory.objects.get(team=team, round=rnd)
            out[key] = {
                'capacity_factor': float(ctx.sc_capacity_factor.get(team.id, 1)),
                'lost_revenue': float(getattr(ctx, 'sc_lost_revenue', {}).get(team.id, 0) or 0),
                'disruption_cost': float(ctx.sc_disruption_costs.get(team.id, 0) or 0),
                'score': float(rs.score),
                'impact': rs.disruption_impact,
            }
        return out

    def _inject_taiwan_earthquake(self):
        """Force the seeded 'Taiwan Earthquake' SC event to fire exactly once,
        at DISRUPT_ROUND (real event-firing path in run_sc_state)."""
        quake = EventTemplateDefinition.objects.get(
            scenario=self.scenario, name='Taiwan Earthquake — Semiconductor Capacity Shock')
        quake.probability_per_round = D('1')
        quake.earliest_round = DISRUPT_ROUND
        quake.max_occurrences = 1
        quake.save()
        return quake

    def _play_game(self, name):
        game, teams = self._make_game(name)
        return game, teams, [self._run_sc_round(game, teams, r) for r in range(1, NUM_ROUNDS + 1)]

    # -- the test --------------------------------------------------------
    def test_ten_round_disruption_and_recovery(self):
        self._inject_taiwan_earthquake()
        _game, _teams, trace = self._play_game('W5 E2E')

        d = DISRUPT_ROUND - 1  # 0-based index of the shock round in `trace`

        if __import__('os').environ.get('W5_TRACE'):
            print('\n round | fragile cf/lost/score        | resilient cf/lost/score')
            for r in range(NUM_ROUNDS):
                f, rz = trace[r]['fragile'], trace[r]['resilient']
                mark = '  <-- SHOCK' if r == d else ''
                print(f'  R{r + 1:<4} | cf={f["capacity_factor"]:.2f} lost=${f["lost_revenue"]:>10,.0f} '
                      f'score={f["score"]:6.2f} | cf={rz["capacity_factor"]:.2f} '
                      f'lost=${rz["lost_revenue"]:>10,.0f} score={rz["score"]:6.2f}{mark}')

        # (1) Baseline — every round before the shock is undisrupted for both teams.
        for r in range(d):
            for key in ('fragile', 'resilient'):
                self.assertEqual(trace[r][key]['capacity_factor'], 1.0,
                                 f'{key} disrupted pre-shock at round {r + 1}')
                self.assertEqual(trace[r][key]['lost_revenue'], 0.0,
                                 f'{key} lost revenue pre-shock at round {r + 1}')

        # (2) Resilience trend — resilient out-scores fragile EVERY round.
        for r in range(NUM_ROUNDS):
            self.assertGreater(
                trace[r]['resilient']['score'], trace[r]['fragile']['score'],
                f'resilient !> fragile at round {r + 1}: {trace[r]}')

        # (3) Lost sales on the shock round.
        shock = trace[d]
        self.assertLess(shock['fragile']['capacity_factor'], 1.0)      # production throttled
        self.assertGreater(shock['fragile']['lost_revenue'], 0.0)      # real lost sales
        # Resilient loses materially less: higher capacity, lower lost revenue.
        self.assertGreater(shock['resilient']['capacity_factor'], shock['fragile']['capacity_factor'])
        self.assertLess(shock['resilient']['lost_revenue'], shock['fragile']['lost_revenue'])

        # (4) Recovery — the disruption persists through its recovery window, then
        # capacity and lost-sales return to baseline (real carry-forward).
        during = [trace[d + k] for k in range(EVENT_RECOVERY_ROUNDS + 1)]  # shock + recovery rounds
        for step in during:
            self.assertLess(step['fragile']['capacity_factor'], 1.0)
        recovered_idx = d + EVENT_RECOVERY_ROUNDS + 1
        self.assertLess(recovered_idx, NUM_ROUNDS, 'need a post-recovery round to assert on')
        rec = trace[recovered_idx]
        self.assertEqual(rec['fragile']['capacity_factor'], 1.0, 'fragile did not recover')
        self.assertEqual(rec['fragile']['lost_revenue'], 0.0, 'fragile still losing sales post-recovery')

        # (5) Determinism — an identical parallel game reproduces the trajectory.
        _g2, _t2, trace2 = self._play_game('W5 E2E (repro)')
        for r in range(NUM_ROUNDS):
            for key in ('fragile', 'resilient'):
                self.assertEqual(trace[r][key]['score'], trace2[r][key]['score'],
                                 f'non-deterministic score at round {r + 1} for {key}')
                self.assertEqual(trace[r][key]['capacity_factor'], trace2[r][key]['capacity_factor'],
                                 f'non-deterministic capacity at round {r + 1} for {key}')
