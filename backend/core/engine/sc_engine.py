"""
CC-19 / CC-19B: Supply Chain engine — event effects, structured contingency,
and a two-channel disruption model that flows through the P&L.

Pipeline placement (see advance_round._run_phase_1):
    run_sc_state(context)        # BEFORE revenue: fire events, carry recovery
                                 #  forward, compute per-team capacity_factor
    calculate_revenue(...)       # Channel 1 (lost sales): throttles units by cf
    calculate_sc_disruption_costs(context)   # Channel 2 (real costs)
    generate_financial_statements(...)       # subtracts sc_disruption_costs
    score_sc_resilience(context) # AFTER financials: resilience score (read-only)

Two channels, both landing in net income (not a direct cash poke):
  1. Lost sales — a supplier-capacity shortfall (Liebig weakest-link across the
     team's critical inputs, net of contingency rerouting to healthy backups)
     caps units sold/built. Revenue and COGS both fall; net income drops by the
     lost contribution margin. Disruption-only: with no disruption cf == 1 and
     nothing changes.
  2. Real costs — freight-rate surcharge on disrupted lanes + backup-supplier /
     expedite mitigation premiums. True expenditures booked as an operating cost
     line, so they flow operating_income -> net_income -> cash.

Determinism: all stochastic draws use a per-(game, round, scenario) seed.
"""
import hashlib
import random
from collections import defaultdict
from decimal import Decimal

SEVERITY_MULT = {'low': 0.5, 'medium': 1.0, 'high': 1.5, 'critical': 2.0}
TV_LEVEL = {'none': 0.0, 'basic': 0.5, 'comprehensive': 1.0}

# Channel-2 dollar anchors (CC-19B §5) — tunable, documented, kept modest vs
# ~$50M starting cash. These price a real expenditure (freight that got dearer,
# premiums paid to reroute), not a lost sale.
FREIGHT_SURCHARGE_BASE = 200000.0     # per unit of (sea_share x rate_uplift)
MITIGATION_PREMIUM_BASE = 150000.0    # per unit of (shifted_share) rerouted


def _seed(game_id, round_number, scenario_id):
    h = hashlib.sha256(f'{game_id}-{round_number}-{scenario_id}'.encode()).hexdigest()
    return int(h, 16) % (2 ** 32)


def _D(x):
    return Decimal(str(round(float(x), 3)))


def _round_state(context):
    """Resolve (round, scenario) for the context; None round if absent."""
    from core.models.core import Round
    game = context.game
    rnd = Round.objects.filter(game=game, round_number=context.round_number).first()
    return rnd, game.scenario


# --------------------------------------------------------------------------- #
#  Contingency helpers                                                         #
# --------------------------------------------------------------------------- #
def _contingency(team, rnd):
    from core.models.sc_decisions import ContingencyPlan
    cp = ContingencyPlan.objects.filter(team=team, round=rnd).first()
    alt_rules = (cp.alt_supplier_activation_rules if cp else None) or []
    mode_rules = (cp.mode_switch_triggers if cp else None) or []
    return alt_rules, mode_rules


def _reroute_shift(cat, alt_rules, disrupted_sup):
    """Fraction of a disrupted category's allocation an alt-supplier rule reroutes
    to a *healthy* backup (0 if none applies)."""
    shifted = 0.0
    for r in alt_rules:
        if r.get('input_category') == cat and r.get('backup_supplier_id'):
            b = disrupted_sup.get(r['backup_supplier_id'])
            if b is None or float(b.capacity_multiplier) >= 1:  # backup healthy
                shifted = max(shifted, min(float(r.get('shift_pct', 0)) / 100.0, 1.0))
    return shifted


def _capacity_factor(team, rnd, disrupted_sup):
    """Liebig weakest-link production capacity factor in [0, 1], net of
    contingency rerouting. 1.0 when nothing the team sources is disrupted."""
    from core.models.sc_decisions import SourcingAllocation
    alt_rules, _ = _contingency(team, rnd)
    by_cat = defaultdict(list)
    for a in SourcingAllocation.objects.filter(team=team, round=rnd):
        by_cat[a.critical_input_category].append(a)

    cf = 1.0
    detail = {}
    for cat, items in by_cat.items():
        total_share = sum((a.allocation_pct or 0) / 100.0 for a in items)
        if total_share <= 0:
            continue
        avail = 0.0
        for a in items:
            share = (a.allocation_pct or 0) / 100.0
            st = disrupted_sup.get(a.supplier_id)
            cap = float(st.capacity_multiplier) if st else 1.0
            if st and cap < 1:
                shifted = _reroute_shift(cat, alt_rules, disrupted_sup)
                cap = shifted * 1.0 + (1 - shifted) * cap  # rerouted share is healthy
            avail += share * cap
        avail = avail / total_share
        detail[cat] = round(avail, 3)
        cf = min(cf, avail)
    return max(min(cf, 1.0), 0.0), detail


# --------------------------------------------------------------------------- #
#  Step 1 (early): disruption state + capacity factor                         #
# --------------------------------------------------------------------------- #
def run_sc_state(context):
    """Fire SC events, carry recovery forward, and compute each team's
    production capacity factor. Runs BEFORE calculate_revenue."""
    from core.models.core import Round
    from core.models.scenario import EventTemplateDefinition
    from core.models.sc_models import Supplier, ShippingLane
    from core.models.sc_state import SCEventInstance, SupplierState, LaneState

    rnd, scenario = _round_state(context)
    if rnd is None:
        return
    game = context.game
    round_number = context.round_number
    rng = random.Random(_seed(game.id, round_number, scenario.id))

    suppliers_by_code = {s.supplier_id: s for s in Supplier.objects.filter(scenario=scenario)}
    lanes_by_code = {l.lane_id: l for l in ShippingLane.objects.filter(scenario=scenario)}

    # 1. Carry recovering supplier disruptions forward from the prior round.
    prev = Round.objects.filter(game=game, round_number=round_number - 1).first()
    if prev:
        for st in SupplierState.objects.filter(round=prev, recovery_rounds_remaining__gt=0):
            SupplierState.objects.update_or_create(
                round=rnd, supplier=st.supplier, defaults=dict(
                    capacity_multiplier=st.capacity_multiplier, quality_modifier=st.quality_modifier,
                    reliability_modifier=st.reliability_modifier, additional_lead_time_days=st.additional_lead_time_days,
                    disruption_cost_multiplier=st.disruption_cost_multiplier,
                    recovery_rounds_remaining=max(st.recovery_rounds_remaining - 1, 0),
                    active_disruption_event=None))

    # 2. Fire SC events (seeded) and apply their effects to state.
    fired = []
    for tmpl in EventTemplateDefinition.objects.filter(scenario=scenario, category='supply_chain').order_by('id'):
        if round_number < (tmpl.earliest_round or 1):
            continue
        if SCEventInstance.objects.filter(event_template=tmpl, round__game=game).count() >= (tmpl.max_occurrences or 1):
            continue
        if rng.random() >= float(tmpl.probability_per_round or 0):
            continue
        inst = SCEventInstance.objects.create(round=rnd, event_template=tmpl, affects_all_teams=True, resolution_data={})
        fired.append(inst)
        eff = tmpl.sc_effects or {}
        sev = SEVERITY_MULT.get(tmpl.severity, 1.0)
        cap_red = float(eff.get('capacity_reduction_pct', 0) or 0)
        for sid in (eff.get('affected_suppliers') or []):
            sup = suppliers_by_code.get(sid)
            if not sup:
                continue
            SupplierState.objects.update_or_create(round=rnd, supplier=sup, defaults=dict(
                capacity_multiplier=_D(max(1 - cap_red / 100.0, 0)),
                quality_modifier=_D(-(eff.get('quality_rating_degradation', 0) or 0)),
                reliability_modifier=_D(0),
                additional_lead_time_days=int(eff.get('additional_lead_time_days', 0) or 0),
                disruption_cost_multiplier=_D(sev),
                recovery_rounds_remaining=int(eff.get('recovery_rounds', eff.get('duration_rounds', 1)) or 1),
                active_disruption_event=None))
        rate = 1.0
        for key in ('mode_rate_multiplier', 'global_rate_multiplier'):
            m = eff.get(key)
            if isinstance(m, dict):
                rate = max(rate, float(m.get('sea', m.get('air', 1.0)) or 1.0))
        for lid in (eff.get('affected_lanes') or []):
            lane = lanes_by_code.get(lid)
            if not lane:
                continue
            LaneState.objects.update_or_create(round=rnd, lane=lane, defaults=dict(
                active_disruption=tmpl.name, current_rate_modifier=_D(min(rate, 99.999))))

    # 3. Per-team production capacity factor (Liebig, net of contingency).
    disrupted_sup = {st.supplier_id: st for st in SupplierState.objects.filter(round=rnd)}
    context.sc_fired = fired
    context.sc_capacity_factor = {}
    context.sc_capacity_detail = {}
    for team in context.teams:
        cf, detail = _capacity_factor(team, rnd, disrupted_sup)
        context.sc_capacity_factor[team.id] = Decimal(str(round(cf, 4)))
        context.sc_capacity_detail[team.id] = detail

    context.log.append(
        f'SC state: fired {len(fired)} SC event(s); capacity factor computed for {len(context.teams)} team(s).')


# --------------------------------------------------------------------------- #
#  Step 2 (cost phase): Channel-2 real costs                                   #
# --------------------------------------------------------------------------- #
def calculate_sc_disruption_costs(context):
    """Freight-rate surcharge on disrupted lanes + backup/expedite mitigation
    premiums, as a team-level operating cost. Booked in operating_income."""
    from core.models.sc_state import SupplierState, LaneState
    from core.models.sc_decisions import SourcingAllocation, LogisticsDecision

    rnd, _ = _round_state(context)
    context.sc_disruption_costs = {}
    context.sc_freight_costs = {}
    context.sc_mitigation_costs = {}
    if rnd is None:
        return

    disrupted_sup = {st.supplier_id: st for st in SupplierState.objects.filter(round=rnd)}
    disrupted_lane = {ls.lane_id: ls for ls in
                      LaneState.objects.filter(round=rnd).exclude(active_disruption__isnull=True)}

    for team in context.teams:
        alt_rules, mode_rules = _contingency(team, rnd)
        logs = list(LogisticsDecision.objects.filter(team=team, round=rnd))
        allocs = list(SourcingAllocation.objects.filter(team=team, round=rnd))

        freight = 0.0
        for l in logs:
            ls = disrupted_lane.get(l.lane_id)
            if not ls:
                continue
            uplift = float(ls.current_rate_modifier or 1) - 1
            if uplift > 0:
                freight += (l.mode_sea_pct or 0) / 100.0 * uplift * FREIGHT_SURCHARGE_BASE

        mitigation = 0.0
        for a in allocs:
            st = disrupted_sup.get(a.supplier_id)
            if not st or float(st.capacity_multiplier) >= 1:
                continue
            shifted = _reroute_shift(a.critical_input_category, alt_rules, disrupted_sup)
            if shifted > 0:
                mitigation += shifted * (a.allocation_pct or 0) / 100.0 * MITIGATION_PREMIUM_BASE
        for l in logs:
            if not disrupted_lane.get(l.lane_id):
                continue
            for r in mode_rules:
                if r.get('lane_id') == l.lane_id and r.get('from_mode') == 'sea':
                    shifted = min(float(r.get('shift_pct', 0)) / 100.0, 1.0)
                    mitigation += shifted * (l.mode_sea_pct or 0) / 100.0 * MITIGATION_PREMIUM_BASE

        context.sc_freight_costs[team.id] = Decimal(str(round(freight, 2)))
        context.sc_mitigation_costs[team.id] = Decimal(str(round(mitigation, 2)))
        context.sc_disruption_costs[team.id] = Decimal(str(round(freight + mitigation, 2)))


# --------------------------------------------------------------------------- #
#  Step 3 (after financials): resilience score + per-team impact record        #
# --------------------------------------------------------------------------- #
def score_sc_resilience(context):
    """Score resilience per team and record per-team disruption impact (split by
    channel) on the fired SC event instances. Read-only over financial state."""
    from core.models.sc_models import Supplier, ResilienceParameters
    from core.models.sc_state import SupplierState, ResilienceScoreHistory
    from core.models.sc_decisions import (
        SourcingAllocation, SourcingDecision, LogisticsDecision, InventoryDecision,
    )
    from core.models.overrides import ClassResilienceWeightOverride

    rnd, scenario = _round_state(context)
    if rnd is None:
        return
    game = context.game
    sup_by_pk = {s.id: s for s in Supplier.objects.filter(scenario=scenario)}
    disrupted_sup = {st.supplier_id: st for st in SupplierState.objects.filter(round=rnd)}

    rp = ResilienceParameters.objects.filter(scenario=scenario).first()
    weights = dict((rp.resilience_score_weights if rp else {}) or {})
    for ov in ClassResilienceWeightOverride.objects.filter(game=game):
        weights[ov.weight_name] = float(ov.override_value)
    rec_buffer = float(rp.critical_component_buffer_days_recommended) if rp else 45.0

    fired = getattr(context, 'sc_fired', [])
    lost_rev = getattr(context, 'sc_lost_revenue', {})
    disr_cost = getattr(context, 'sc_disruption_costs', {})
    cf_map = getattr(context, 'sc_capacity_factor', {})

    for team in context.teams:
        allocs = list(SourcingAllocation.objects.filter(team=team, round=rnd))
        sdec = SourcingDecision.objects.filter(team=team, round=rnd).first()
        logs = list(LogisticsDecision.objects.filter(team=team, round=rnd))
        invs = list(InventoryDecision.objects.filter(team=team, round=rnd))

        for inst in fired:
            inst.resolution_data = inst.resolution_data or {}
            inst.resolution_data.setdefault('team_impact', {})[str(team.id)] = {
                'lost_revenue': float(lost_rev.get(team.id, 0) or 0),
                'disruption_cost': float(disr_cost.get(team.id, 0) or 0),
                'capacity_factor': float(cf_map.get(team.id, 1) or 1),
            }
            inst.save(update_fields=['resolution_data'])

        comp = _resilience_components(allocs, sdec, logs, invs, sup_by_pk, disrupted_sup, rec_buffer)
        score = min(sum(float(weights.get(k, 0)) * comp[k] for k in comp) * 100.0, 99.999)
        ResilienceScoreHistory.objects.update_or_create(
            team=team, round=rnd, defaults=dict(
                score=Decimal(str(round(score, 3))),
                components={k: round(v, 3) for k, v in comp.items()},
                weights_used={k: float(v) for k, v in weights.items()}))

    context.log.append(f'SC resilience scored for {len(context.teams)} team(s).')


def _resilience_components(allocs, sdec, logs, invs, sup_by_pk, disrupted, rec_buffer):
    by_cat = defaultdict(list)
    for a in allocs:
        by_cat[a.critical_input_category].append(a)
    cats = list(by_cat.keys())
    multi = (sum(1 for c in cats if len(by_cat[c]) >= 2) / len(cats)) if cats else 0.0

    country_wt = defaultdict(float)
    total = 0.0
    for a in allocs:
        s = sup_by_pk.get(a.supplier_id)
        country_wt[s.country if s else '??'] += (a.allocation_pct or 0)
        total += (a.allocation_pct or 0)
    geo = (1 - max(country_wt.values()) / total) if total > 0 else 0.0

    buf = (sum(min((i.buffer_days or 0) / rec_buffer, 1.0) for i in invs) / len(invs)) if invs else 0.0

    def n_modes(l):
        return sum(1 for m in ('sea', 'air', 'rail', 'road') if getattr(l, f'mode_{m}_pct', 0) > 0)
    used = [l for l in logs if n_modes(l) > 0]
    modal = (sum(1 for l in used if n_modes(l) > 1) / len(used)) if used else 0.0

    tv = TV_LEVEL.get(getattr(sdec, 'tier_2_3_visibility_investment', 'none') if sdec else 'none', 0.0)

    rels = [float(sup_by_pk[a.supplier_id].reliability_rating or 0) for a in allocs if a.supplier_id in sup_by_pk]
    health = (sum(rels) / len(rels)) if rels else 0.0
    if allocs:
        dis_frac = sum(1 for a in allocs if a.supplier_id in disrupted) / len(allocs)
        health = max(health - 0.5 * dis_frac, 0.0)

    return {'multi_sourcing': multi, 'geographic_diversity': geo, 'buffer_inventory_adequacy': buf,
            'modal_flexibility': modal, 'tier_2_visibility': tv, 'supplier_financial_health': health}
