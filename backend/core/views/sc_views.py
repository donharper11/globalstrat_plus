"""
Supply Chain API views (CC-04 §7).

Decision submission: POST to create/update, GET to retrieve.
Scenario content: GET-only for teams.
State retrieval: GET-only.
"""
from django.db import models, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team, Round
from core.models.scenario import Scenario
from core.models.sc_models import (
    Supplier, ShippingLane, TradeFinanceInstrument, ComplianceRegime,
)
from core.models.sc_decisions import (
    SourcingAllocation, SourcingDecision, LogisticsDecision,
    IncotermsDecision, CustomsClassificationDecision,
    TradeFinanceDecision, SinosureEnrollment, FXHedgeDecision,
    InventoryDecision, ContingencyPlan,
)
from core.models.sc_state import (
    SCEventInstance, HedgePosition, ResilienceScoreHistory,
)
from core.serializers.sc_serializers import (
    SupplierSerializer, ShippingLaneSerializer,
    TradeFinanceInstrumentSerializer, ComplianceRegimeSerializer,
    SourcingAllocationReadSerializer, SourcingDecisionReadSerializer,
    SourcingDecisionWriteSerializer,
    LogisticsDecisionReadSerializer, LogisticsDecisionWriteSerializer,
    IncotermsDecisionReadSerializer, IncotermsDecisionWriteSerializer,
    CustomsClassificationDecisionReadSerializer,
    CustomsClassificationDecisionWriteSerializer,
    TradeFinanceDecisionReadSerializer, TradeFinanceDecisionWriteSerializer,
    SinosureEnrollmentReadSerializer, SinosureEnrollmentWriteSerializer,
    FXHedgeDecisionReadSerializer, FXHedgeDecisionWriteSerializer,
    InventoryDecisionReadSerializer, InventoryDecisionWriteSerializer,
    ContingencyPlanReadSerializer, ContingencyPlanWriteSerializer,
    SCEventInstanceSerializer, HedgePositionSerializer,
    ResilienceScoreHistorySerializer,
)
from core.views.decisions import IsTeamMember, IsRoundOpen


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_team_round(kwargs):
    """Extract team and round from URL kwargs."""
    game_id = kwargs['game_id']
    team_id = kwargs['team_id']
    round_number = kwargs['round_number']
    team = get_object_or_404(Team, pk=team_id, game_id=game_id)
    rnd = get_object_or_404(Round, game_id=game_id, round_number=round_number)
    return team, rnd


def _get_scenario_from_game(game_id):
    """Get the scenario for a game."""
    game = get_object_or_404(Game, pk=game_id)
    return game.scenario


# ---------------------------------------------------------------------------
# Decision submission endpoints (§7.1)
# ---------------------------------------------------------------------------

class SourcingView(APIView):
    permission_classes = [IsTeamMember, IsRoundOpen]

    def get(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        decision = SourcingDecision.objects.filter(team=team, round=rnd).first()
        allocations = SourcingAllocation.objects.filter(team=team, round=rnd)
        return Response({
            'decision': SourcingDecisionReadSerializer(decision).data if decision else None,
            'allocations': SourcingAllocationReadSerializer(allocations, many=True).data,
        })

    @transaction.atomic
    def post(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        data = request.data.copy()
        data['team'] = team.pk
        data['round'] = rnd.pk

        # Upsert page-level decision
        decision, _ = SourcingDecision.objects.update_or_create(
            team=team, round=rnd,
            defaults={
                'tier_2_3_visibility_investment': data.get('tier_2_3_visibility_investment', 'none'),
                'multi_sourcing_strategy': data.get('multi_sourcing_strategy', 'single_source'),
            },
        )

        # Replace allocation rows
        SourcingAllocation.objects.filter(team=team, round=rnd).delete()
        allocations = data.get('allocations', [])
        for alloc in allocations:
            alloc['team'] = team.pk
            alloc['round'] = rnd.pk
            ser = SourcingAllocationReadSerializer(data=alloc) if False else None
            SourcingAllocation.objects.create(
                team=team, round=rnd,
                critical_input_category=alloc['critical_input_category'],
                supplier_id=alloc['supplier'],
                allocation_pct=alloc.get('allocation_pct', 0),
                volume_commitment_units=alloc.get('volume_commitment_units', 0),
                payment_terms=alloc.get('payment_terms', ''),
            )

        return Response(
            SourcingDecisionReadSerializer(decision).data,
            status=status.HTTP_201_CREATED,
        )


class LogisticsView(APIView):
    permission_classes = [IsTeamMember, IsRoundOpen]

    def get(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        logistics = LogisticsDecision.objects.filter(team=team, round=rnd)
        incoterms = IncotermsDecision.objects.filter(team=team, round=rnd)
        customs = CustomsClassificationDecision.objects.filter(team=team, round=rnd)
        return Response({
            'logistics': LogisticsDecisionReadSerializer(logistics, many=True).data,
            'incoterms': IncotermsDecisionReadSerializer(incoterms, many=True).data,
            'customs': CustomsClassificationDecisionReadSerializer(customs, many=True).data,
        })

    @transaction.atomic
    def post(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        data = request.data
        created = []

        for item in data.get('logistics', []):
            item['team'] = team.pk
            item['round'] = rnd.pk
            ser = LogisticsDecisionWriteSerializer(data=item)
            ser.is_valid(raise_exception=True)
            obj, _ = LogisticsDecision.objects.update_or_create(
                team=team, round=rnd, lane_id=item['lane'],
                defaults={k: v for k, v in ser.validated_data.items()
                          if k not in ('team', 'round', 'lane')},
            )
            created.append(obj)

        for item in data.get('incoterms', []):
            IncotermsDecision.objects.update_or_create(
                team=team, round=rnd, destination_market_id=item['destination_market'],
                defaults={
                    'incoterms': item.get('incoterms', 'CIF'),
                    'insurance_coverage_pct': item.get('insurance_coverage_pct', 110),
                },
            )

        for item in data.get('customs', []):
            CustomsClassificationDecision.objects.update_or_create(
                team=team, round=rnd, destination_market_id=item['destination_market'],
                defaults={
                    'classification': item.get('classification', 'general_trade'),
                    'reverse_logistics_capacity_pct': item.get('reverse_logistics_capacity_pct', 0),
                    'reverse_logistics_hub_market_id': item.get('reverse_logistics_hub_market'),
                },
            )

        return Response({'status': 'ok'}, status=status.HTTP_201_CREATED)


class TradeFinanceView(APIView):
    permission_classes = [IsTeamMember, IsRoundOpen]

    def get(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        tf = TradeFinanceDecision.objects.filter(team=team, round=rnd)
        sinosure = SinosureEnrollment.objects.filter(team=team, round=rnd)
        fx = FXHedgeDecision.objects.filter(team=team, round=rnd)
        return Response({
            'trade_finance': TradeFinanceDecisionReadSerializer(tf, many=True).data,
            'sinosure': SinosureEnrollmentReadSerializer(sinosure, many=True).data,
            'fx_hedges': FXHedgeDecisionReadSerializer(fx, many=True).data,
        })

    @transaction.atomic
    def post(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        data = request.data

        for item in data.get('trade_finance', []):
            TradeFinanceDecision.objects.update_or_create(
                team=team, round=rnd,
                segment_id=item['segment'], market_id=item['market'],
                defaults={
                    'buyer_payment_instrument': item.get('buyer_payment_instrument', ''),
                    'lc_doc_prep_investment': item.get('lc_doc_prep_investment', 'standard'),
                },
            )

        for item in data.get('sinosure', []):
            SinosureEnrollment.objects.update_or_create(
                team=team, round=rnd, market_id=item['market'],
                defaults={'coverage_pct': item.get('coverage_pct', 0)},
            )

        for item in data.get('fx_hedges', []):
            FXHedgeDecision.objects.update_or_create(
                team=team, round=rnd, currency_pair=item['currency_pair'],
                defaults={
                    'hedge_ratio': item.get('hedge_ratio', 0),
                    'tenor_days': item.get('tenor_days', 90),
                },
            )

        return Response({'status': 'ok'}, status=status.HTTP_201_CREATED)


class InventoryView(APIView):
    permission_classes = [IsTeamMember, IsRoundOpen]

    def get(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        inventory = InventoryDecision.objects.filter(team=team, round=rnd)
        contingency = ContingencyPlan.objects.filter(team=team, round=rnd).first()
        return Response({
            'inventory': InventoryDecisionReadSerializer(inventory, many=True).data,
            'contingency': ContingencyPlanReadSerializer(contingency).data if contingency else None,
        })

    @transaction.atomic
    def post(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        data = request.data

        for item in data.get('inventory', []):
            InventoryDecision.objects.update_or_create(
                team=team, round=rnd,
                product_id=item['product'], market_id=item['market'],
                defaults={
                    'buffer_days': item.get('buffer_days', 30),
                    'safety_stock_trigger_pct': item.get('safety_stock_trigger_pct', 20),
                },
            )

        cp_data = data.get('contingency')
        if cp_data:
            ContingencyPlan.objects.update_or_create(
                team=team, round=rnd,
                defaults={
                    'disruption_response_playbook': cp_data.get('disruption_response_playbook', ''),
                    'alt_supplier_activation_rules': cp_data.get('alt_supplier_activation_rules', []),
                    'mode_switch_triggers': cp_data.get('mode_switch_triggers', []),
                },
            )

        return Response({'status': 'ok'}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Scenario-content retrieval endpoints (§7.2)
# ---------------------------------------------------------------------------

class ScenarioSuppliersView(APIView):
    def get(self, request, scenario_id):
        suppliers = Supplier.objects.filter(scenario_id=scenario_id)
        spec_filter = request.query_params.get('specialization')
        if spec_filter:
            suppliers = suppliers.filter(specialization__contains=[spec_filter])
        return Response(SupplierSerializer(suppliers, many=True).data)


class ScenarioLanesView(APIView):
    def get(self, request, scenario_id):
        lanes = ShippingLane.objects.filter(scenario_id=scenario_id)
        return Response(ShippingLaneSerializer(lanes, many=True).data)


class ScenarioTradeFinanceInstrumentsView(APIView):
    def get(self, request, scenario_id):
        instruments = TradeFinanceInstrument.objects.filter(scenario_id=scenario_id)
        return Response(TradeFinanceInstrumentSerializer(instruments, many=True).data)


class ScenarioComplianceRegimesView(APIView):
    def get(self, request, scenario_id):
        regimes = ComplianceRegime.objects.filter(scenario_id=scenario_id)
        return Response(ComplianceRegimeSerializer(regimes, many=True).data)


# ---------------------------------------------------------------------------
# State retrieval endpoints (§7.3)
# ---------------------------------------------------------------------------

class ResilienceScoreView(APIView):
    permission_classes = [IsTeamMember]

    def get(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        history = ResilienceScoreHistory.objects.filter(team=team, round=rnd).first()
        if not history:
            return Response({'score': None, 'components': {}, 'weights_used': {}})
        return Response(ResilienceScoreHistorySerializer(history).data)


class HedgePositionsView(APIView):
    permission_classes = [IsTeamMember]

    def get(self, request, game_id, team_id):
        team = get_object_or_404(Team, pk=team_id, game_id=game_id)
        positions = HedgePosition.objects.filter(team=team).order_by('-opened_round__round_number')
        return Response(HedgePositionSerializer(positions, many=True).data)


class SCEventsView(APIView):
    permission_classes = [IsTeamMember]

    def get(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        events = SCEventInstance.objects.filter(round=rnd).filter(
            models.Q(affects_all_teams=True) | models.Q(affected_teams=team)
        )
        return Response(SCEventInstanceSerializer(events, many=True).data)
