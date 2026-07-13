"""
CC-16 — Instructor Supply-Chain Panel views.

The instructor facilitation surface for an SC-enabled game:
  - per-team SC decision viewing + resilience audit (InstructorSCPanelView)
  - supply-chain event catalog (InstructorSCEventCatalogView)
  - event injection that actually disrupts the next round (InstructorInjectSCEventView)

Resilience-weight and progressive-disclosure overrides reuse the CC-04 A1
endpoints in `core/views/overrides.py`; compliance regimes are surfaced via the
existing scenario endpoint. All views are instructor-only.
"""
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team, Round
from core.models.scenario import EventTemplateDefinition
from core.models.sc_models import Supplier, ShippingLane
from core.models.sc_decisions import (
    SourcingAllocation, SourcingDecision, LogisticsDecision,
    InventoryDecision, ContingencyPlan,
)
from core.models.sc_state import (
    SupplierState, LaneState, SCEventInstance, ResilienceScoreHistory,
)
from core.permissions import IsInstructor


def _current_open_round(game):
    """The round that will be processed on the next advance (status='open'),
    falling back to the highest round number that exists."""
    rnd = Round.objects.filter(game=game, status='open').order_by('round_number').first()
    if rnd is None:
        rnd = Round.objects.filter(game=game).order_by('-round_number').first()
    return rnd


def _event_effect_summary(tmpl):
    """Plain-language summary of an SC template's sc_effects for the catalog."""
    eff = tmpl.sc_effects or {}
    parts = []
    if eff.get('capacity_reduction_pct'):
        parts.append(f"−{eff['capacity_reduction_pct']}% capacity")
    if eff.get('affected_suppliers'):
        parts.append(f"suppliers: {', '.join(eff['affected_suppliers'])}")
    if eff.get('affected_lanes'):
        parts.append(f"lanes: {', '.join(eff['affected_lanes'])}")
    for key in ('global_rate_multiplier', 'mode_rate_multiplier'):
        m = eff.get(key)
        if isinstance(m, dict):
            parts.append("freight rate " + ", ".join(f"{k}×{v}" for k, v in m.items()))
    rec = eff.get('recovery_rounds', eff.get('duration_rounds'))
    if rec:
        parts.append(f"recovers in {rec} round(s)")
    return "; ".join(parts) or "no modelled supply-chain effect"


class InstructorSCPanelView(APIView):
    """GET /api/games/{game_id}/instructor/sc-panel/[?round=N]

    Per-team SC snapshot for the round: sourcing (with single-source flags),
    inventory/contingency posture, resilience audit, and the disruptions active
    this round."""
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)
        scenario = game.scenario

        round_q = request.query_params.get('round')
        if round_q:
            rnd = get_object_or_404(Round, game=game, round_number=int(round_q))
        else:
            rnd = _current_open_round(game)

        sup_by_pk = {s.id: s for s in Supplier.objects.filter(scenario=scenario)}
        lane_by_pk = {l.id: l for l in ShippingLane.objects.filter(scenario=scenario)}

        # Disruptions active this round (systemic — hit every team sourcing them).
        disrupted_sup = {}
        active_disruptions = []
        if rnd is not None:
            for st in SupplierState.objects.filter(round=rnd):
                if float(st.capacity_multiplier) < 1 or st.additional_lead_time_days:
                    disrupted_sup[st.supplier_id] = st
                    sup = sup_by_pk.get(st.supplier_id)
                    active_disruptions.append({
                        'type': 'supplier', 'name': sup.name if sup else '?',
                        'country': sup.country if sup else None,
                        'capacity_multiplier': float(st.capacity_multiplier),
                        'recovery_rounds_remaining': st.recovery_rounds_remaining,
                    })
            for ls in LaneState.objects.filter(round=rnd).exclude(active_disruption__isnull=True):
                lane = lane_by_pk.get(ls.lane_id)
                active_disruptions.append({
                    'type': 'lane', 'name': lane.lane_id if lane else '?',
                    'disruption': ls.active_disruption,
                    'rate_modifier': float(ls.current_rate_modifier),
                })

        teams_out = []
        weights_used = {}
        for team in Team.objects.filter(game=game).order_by('id'):
            allocs = list(SourcingAllocation.objects.filter(team=team, round=rnd)) if rnd else []
            by_cat = {}
            for a in allocs:
                by_cat.setdefault(a.critical_input_category, []).append(a)
            sourcing = [{
                'category': a.critical_input_category,
                'supplier': sup_by_pk[a.supplier_id].name if a.supplier_id in sup_by_pk else '?',
                'country': sup_by_pk[a.supplier_id].country if a.supplier_id in sup_by_pk else None,
                'allocation_pct': a.allocation_pct,
                'disrupted': a.supplier_id in disrupted_sup,
            } for a in allocs]
            single_source_flags = [cat for cat, items in by_cat.items() if len(items) == 1]

            sdec = SourcingDecision.objects.filter(team=team, round=rnd).first() if rnd else None
            invs = list(InventoryDecision.objects.filter(team=team, round=rnd)) if rnd else []
            buffer_avg = round(sum(i.buffer_days or 0 for i in invs) / len(invs), 1) if invs else None
            has_contingency = ContingencyPlan.objects.filter(team=team, round=rnd).exists() if rnd else False

            # Resilience audit — latest scored row at or before this round.
            rs = (ResilienceScoreHistory.objects
                  .filter(team=team, round__round_number__lte=(rnd.round_number if rnd else 0))
                  .order_by('-round__round_number').first())
            resilience = None
            if rs:
                weights_used = rs.weights_used or weights_used
                resilience = {
                    'round_number': rs.round.round_number,
                    'score': float(rs.score),
                    'components': rs.components,
                    'weights_used': rs.weights_used,
                    'disruption_impact': rs.disruption_impact,
                }

            teams_out.append({
                'team_id': team.id,
                'team_name': team.name,
                'multi_sourcing_strategy': sdec.multi_sourcing_strategy if sdec else None,
                'tier_2_3_visibility_investment': sdec.tier_2_3_visibility_investment if sdec else None,
                'sourcing': sourcing,
                'single_source_flags': single_source_flags,
                'buffer_days_avg': buffer_avg,
                'has_contingency': has_contingency,
                'resilience': resilience,
            })

        return Response({
            'game_id': game.id,
            'scenario_id': scenario.id,
            'round_number': rnd.round_number if rnd else None,
            'effective_resilience_weights': weights_used,
            'active_disruptions': active_disruptions,
            'teams': teams_out,
        })


class InstructorSCEventCatalogView(APIView):
    """GET /api/games/{game_id}/instructor/sc-event-catalog/ — injectable
    supply-chain event templates with a plain-language effect summary."""
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)
        templates = EventTemplateDefinition.objects.filter(
            scenario=game.scenario, category='supply_chain').order_by('severity', 'name')
        return Response({'events': [{
            'id': t.id,
            'name': t.name,
            'severity': t.severity,
            'effect_summary': _event_effect_summary(t),
        } for t in templates]})


class InstructorInjectSCEventView(APIView):
    """POST /api/games/{game_id}/instructor/inject-sc-event/  {event_template_id}

    Pre-stages an instructor-forced SC event onto the current open round; it
    fires (creating real SupplierState/LaneState) on the next round advance."""
    permission_classes = [IsInstructor]

    def post(self, request, game_id):
        game = get_object_or_404(Game, id=game_id)
        template_id = request.data.get('event_template_id')
        template = get_object_or_404(
            EventTemplateDefinition, id=template_id,
            scenario=game.scenario, category='supply_chain')

        rnd = _current_open_round(game)
        if rnd is None or rnd.status != 'open':
            return Response(
                {'detail': 'No open round to inject into; start/advance the game first.'},
                status=status.HTTP_400_BAD_REQUEST)

        inst = SCEventInstance.objects.create(
            round=rnd, event_template=template, affects_all_teams=True,
            fired_by_instructor=True,
            resolution_data={'pending': True},
        )
        return Response({
            'message': f'"{template.name}" queued — fires when round {rnd.round_number} is advanced.',
            'sc_event_instance_id': inst.id,
            'round_number': rnd.round_number,
            'effect_summary': _event_effect_summary(template),
        }, status=status.HTTP_201_CREATED)
