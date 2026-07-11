"""
CC-19: Supply Chain engine — event effects, structured contingency execution,
and resilience scoring. Runs as a Phase-1 step (see advance_round._run_phase_1).

Deterministic: all stochastic draws use a per-(game, round, scenario) seed.
Self-contained: writes SupplierState / LaneState / SCEventInstance /
ResilienceScoreHistory and applies a disruption cost to team cash. It does not
yet feed COGS/net-income (a bounded follow-up); the disruption cost is applied
directly to team cash at the end of Phase 1.
"""
import hashlib
import random
from collections import defaultdict
from decimal import Decimal

# $ cost of a critical input that is 100%-allocated to a supplier and fully
# knocked out (capacity → 0) at severity 1.0. Scaled by exposure/loss/severity.
BASE_DISRUPTION_COST = 500000.0
SEVERITY_MULT = {'low': 0.5, 'medium': 1.0, 'high': 1.5, 'critical': 2.0}
TV_LEVEL = {'none': 0.0, 'basic': 0.5, 'comprehensive': 1.0}


def _seed(game_id, round_number, scenario_id):
    h = hashlib.sha256(f'{game_id}-{round_number}-{scenario_id}'.encode()).hexdigest()
    return int(h, 16) % (2 ** 32)


def _D(x):
    return Decimal(str(round(float(x), 3)))


def run_sc_engine(context):
    from core.models.core import Round
    from core.models.scenario import EventTemplateDefinition
    from core.models.sc_models import Supplier, ShippingLane, ResilienceParameters
    from core.models.sc_state import SCEventInstance, SupplierState, LaneState, ResilienceScoreHistory
    from core.models.sc_decisions import (
        SourcingAllocation, SourcingDecision, LogisticsDecision, InventoryDecision, ContingencyPlan,
    )
    from core.models.overrides import ClassResilienceWeightOverride

    game = context.game
    round_number = context.round_number
    rnd = Round.objects.filter(game=game, round_number=round_number).first()
    if rnd is None:
        return
    scenario = game.scenario
    rng = random.Random(_seed(game.id, round_number, scenario.id))

    suppliers_by_code = {s.supplier_id: s for s in Supplier.objects.filter(scenario=scenario)}
    sup_by_pk = {s.id: s for s in suppliers_by_code.values()}
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

    # 3. Per-team contingency execution + disruption cost + resilience scoring.
    disrupted_sup = {st.supplier_id: st for st in SupplierState.objects.filter(round=rnd)}
    disrupted_lane = {ls.lane_id: ls for ls in LaneState.objects.filter(round=rnd).exclude(active_disruption__isnull=True)}

    rp = ResilienceParameters.objects.filter(scenario=scenario).first()
    weights = dict((rp.resilience_score_weights if rp else {}) or {})
    for ov in ClassResilienceWeightOverride.objects.filter(game=game):
        weights[ov.weight_name] = float(ov.override_value)
    rec_buffer = float(rp.critical_component_buffer_days_recommended) if rp else 45.0

    for team in context.teams:
        allocs = list(SourcingAllocation.objects.filter(team=team, round=rnd))
        sdec = SourcingDecision.objects.filter(team=team, round=rnd).first()
        logs = list(LogisticsDecision.objects.filter(team=team, round=rnd))
        invs = list(InventoryDecision.objects.filter(team=team, round=rnd))
        cp = ContingencyPlan.objects.filter(team=team, round=rnd).first()
        alt_rules = (cp.alt_supplier_activation_rules if cp else None) or []
        mode_rules = (cp.mode_switch_triggers if cp else None) or []

        base_impact = 0.0
        eff_impact = 0.0
        applied = []
        for a in allocs:
            st = disrupted_sup.get(a.supplier_id)
            if not st or float(st.capacity_multiplier) >= 1:
                continue
            raw = ((a.allocation_pct or 0) / 100.0) * (1 - float(st.capacity_multiplier)) \
                * float(st.disruption_cost_multiplier or 1) * BASE_DISRUPTION_COST
            base_impact += raw
            shifted = 0.0
            for r in alt_rules:
                if r.get('input_category') == a.critical_input_category and r.get('backup_supplier_id'):
                    b = disrupted_sup.get(r['backup_supplier_id'])
                    if b is None or float(b.capacity_multiplier) >= 1:  # backup is healthy
                        shifted = max(shifted, min(float(r.get('shift_pct', 0)) / 100.0, 1.0))
            eff_impact += raw * (1 - shifted)
            if shifted > 0:
                applied.append({'type': 'alt_supplier', 'input': a.critical_input_category, 'shift_pct': int(shifted * 100)})
        for l in logs:
            ls = disrupted_lane.get(l.lane_id)
            if not ls:
                continue
            extra = float(ls.current_rate_modifier or 1) - 1
            if extra <= 0:
                continue
            raw = ((l.mode_sea_pct or 0) / 100.0) * extra * BASE_DISRUPTION_COST * 0.3
            base_impact += raw
            shifted = 0.0
            for r in mode_rules:
                if r.get('lane_id') == l.lane_id and r.get('from_mode') == 'sea':
                    shifted = max(shifted, min(float(r.get('shift_pct', 0)) / 100.0, 1.0))
            eff_impact += raw * (1 - shifted)
            if shifted > 0:
                applied.append({'type': 'mode_switch', 'lane': l.lane_id, 'shift_pct': int(shifted * 100)})

        disruption_cost = round(eff_impact, 2)
        if disruption_cost > 0:
            team.cash_on_hand = (team.cash_on_hand or Decimal('0')) - Decimal(str(disruption_cost))
            team.save(update_fields=['cash_on_hand'])
        for inst in fired:
            inst.resolution_data = inst.resolution_data or {}
            inst.resolution_data.setdefault('team_impact', {})[str(team.id)] = {
                'base_impact': round(base_impact, 2), 'effective_impact': disruption_cost, 'applied': applied}
            inst.save(update_fields=['resolution_data'])

        comp = _resilience_components(allocs, sdec, logs, invs, sup_by_pk, disrupted_sup, rec_buffer)
        score = min(sum(float(weights.get(k, 0)) * comp[k] for k in comp) * 100.0, 99.999)
        ResilienceScoreHistory.objects.update_or_create(
            team=team, round=rnd, defaults=dict(
                score=Decimal(str(round(score, 3))),
                components={k: round(v, 3) for k, v in comp.items()},
                weights_used={k: float(v) for k, v in weights.items()}))

    context.log.append(f'SC engine: fired {len(fired)} SC event(s); scored resilience for {len(context.teams)} team(s).')


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
