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
from core.models.scenario import Scenario, MarketDefinition, SegmentDefinition
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

    @staticmethod
    def _body(team, rnd):
        decision = SourcingDecision.objects.filter(team=team, round=rnd).first()
        allocations = SourcingAllocation.objects.filter(team=team, round=rnd)
        return {
            'decision': SourcingDecisionReadSerializer(decision).data if decision else None,
            'allocations': SourcingAllocationReadSerializer(allocations, many=True).data,
        }

    def get(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        return Response(self._body(team, rnd))

    @transaction.atomic
    def post(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        incoming = request.data

        # Inject the team/round identity server-side; forward only the keys the
        # client actually supplied so progressive-disclosure locks aren't tripped
        # by server-side defaults.
        payload = {'team': team.pk, 'round': rnd.pk}
        for key in ('tier_2_3_visibility_investment', 'multi_sourcing_strategy'):
            if key in incoming:
                payload[key] = incoming[key]
        payload['allocations'] = [
            {**alloc, 'team': team.pk, 'round': rnd.pk}
            for alloc in incoming.get('allocations', [])
        ]

        ser = SourcingDecisionWriteSerializer(data=payload)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        alloc_vd = vd.pop('allocations', [])

        decision, _ = SourcingDecision.objects.update_or_create(
            team=team, round=rnd,
            defaults={k: v for k, v in vd.items() if k not in ('team', 'round')},
        )

        # Replace allocation rows atomically from validated data.
        SourcingAllocation.objects.filter(team=team, round=rnd).delete()
        for alloc in alloc_vd:
            SourcingAllocation.objects.create(
                team=team, round=rnd,
                critical_input_category=alloc['critical_input_category'],
                supplier=alloc['supplier'],
                allocation_pct=alloc['allocation_pct'],
                volume_commitment_units=alloc.get('volume_commitment_units', 0),
                payment_terms=alloc.get('payment_terms', ''),
            )

        return Response(self._body(team, rnd), status=status.HTTP_201_CREATED)


class LogisticsView(APIView):
    permission_classes = [IsTeamMember, IsRoundOpen]

    @staticmethod
    def _body(team, rnd):
        logistics = LogisticsDecision.objects.filter(team=team, round=rnd)
        incoterms = IncotermsDecision.objects.filter(team=team, round=rnd)
        customs = CustomsClassificationDecision.objects.filter(team=team, round=rnd)
        return {
            'logistics': LogisticsDecisionReadSerializer(logistics, many=True).data,
            'incoterms': IncotermsDecisionReadSerializer(incoterms, many=True).data,
            'customs': CustomsClassificationDecisionReadSerializer(customs, many=True).data,
        }

    def get(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        return Response(self._body(team, rnd))

    @transaction.atomic
    def post(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        data = request.data

        # Validate every sub-collection through its write serializer BEFORE any
        # write, so an invalid item in any group rejects the whole submission.
        logistics_valid = []
        for item in data.get('logistics', []):
            ser = LogisticsDecisionWriteSerializer(
                data={**item, 'team': team.pk, 'round': rnd.pk})
            ser.is_valid(raise_exception=True)
            logistics_valid.append(ser.validated_data)

        incoterms_valid = []
        for item in data.get('incoterms', []):
            ser = IncotermsDecisionWriteSerializer(
                data={**item, 'team': team.pk, 'round': rnd.pk})
            ser.is_valid(raise_exception=True)
            incoterms_valid.append(ser.validated_data)

        customs_valid = []
        for item in data.get('customs', []):
            ser = CustomsClassificationDecisionWriteSerializer(
                data={**item, 'team': team.pk, 'round': rnd.pk})
            ser.is_valid(raise_exception=True)
            customs_valid.append(ser.validated_data)

        for vd in logistics_valid:
            LogisticsDecision.objects.update_or_create(
                team=team, round=rnd, lane=vd['lane'],
                defaults={k: v for k, v in vd.items()
                          if k not in ('team', 'round', 'lane')},
            )

        for vd in incoterms_valid:
            IncotermsDecision.objects.update_or_create(
                team=team, round=rnd, destination_market=vd['destination_market'],
                defaults={k: v for k, v in vd.items()
                          if k not in ('team', 'round', 'destination_market')},
            )

        for vd in customs_valid:
            CustomsClassificationDecision.objects.update_or_create(
                team=team, round=rnd, destination_market=vd['destination_market'],
                defaults={k: v for k, v in vd.items()
                          if k not in ('team', 'round', 'destination_market')},
            )

        return Response(self._body(team, rnd), status=status.HTTP_201_CREATED)


class TradeFinanceView(APIView):
    permission_classes = [IsTeamMember, IsRoundOpen]

    @staticmethod
    def _body(team, rnd):
        tf = TradeFinanceDecision.objects.filter(team=team, round=rnd)
        sinosure = SinosureEnrollment.objects.filter(team=team, round=rnd)
        fx = FXHedgeDecision.objects.filter(team=team, round=rnd)
        return {
            'trade_finance': TradeFinanceDecisionReadSerializer(tf, many=True).data,
            'sinosure': SinosureEnrollmentReadSerializer(sinosure, many=True).data,
            'fx_hedges': FXHedgeDecisionReadSerializer(fx, many=True).data,
        }

    def get(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        return Response(self._body(team, rnd))

    @transaction.atomic
    def post(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        data = request.data

        tf_valid, sino_valid, fx_valid = [], [], []
        for item in data.get('trade_finance', []):
            ser = TradeFinanceDecisionWriteSerializer(
                data={**item, 'team': team.pk, 'round': rnd.pk})
            ser.is_valid(raise_exception=True)
            tf_valid.append(ser.validated_data)
        for item in data.get('sinosure', []):
            ser = SinosureEnrollmentWriteSerializer(
                data={**item, 'team': team.pk, 'round': rnd.pk})
            ser.is_valid(raise_exception=True)
            sino_valid.append(ser.validated_data)
        for item in data.get('fx_hedges', []):
            ser = FXHedgeDecisionWriteSerializer(
                data={**item, 'team': team.pk, 'round': rnd.pk})
            ser.is_valid(raise_exception=True)
            fx_valid.append(ser.validated_data)

        for vd in tf_valid:
            TradeFinanceDecision.objects.update_or_create(
                team=team, round=rnd, segment=vd['segment'], market=vd['market'],
                defaults={k: v for k, v in vd.items()
                          if k not in ('team', 'round', 'segment', 'market')},
            )
        for vd in sino_valid:
            SinosureEnrollment.objects.update_or_create(
                team=team, round=rnd, market=vd['market'],
                defaults={k: v for k, v in vd.items()
                          if k not in ('team', 'round', 'market')},
            )
        for vd in fx_valid:
            FXHedgeDecision.objects.update_or_create(
                team=team, round=rnd, currency_pair=vd['currency_pair'],
                defaults={k: v for k, v in vd.items()
                          if k not in ('team', 'round', 'currency_pair')},
            )

        return Response(self._body(team, rnd), status=status.HTTP_201_CREATED)


class InventoryView(APIView):
    permission_classes = [IsTeamMember, IsRoundOpen]

    @staticmethod
    def _body(team, rnd):
        inventory = InventoryDecision.objects.filter(team=team, round=rnd)
        contingency = ContingencyPlan.objects.filter(team=team, round=rnd).first()
        return {
            'inventory': InventoryDecisionReadSerializer(inventory, many=True).data,
            'contingency': ContingencyPlanReadSerializer(contingency).data if contingency else None,
        }

    def get(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        return Response(self._body(team, rnd))

    @transaction.atomic
    def post(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        data = request.data

        inv_valid = []
        for item in data.get('inventory', []):
            ser = InventoryDecisionWriteSerializer(
                data={**item, 'team': team.pk, 'round': rnd.pk})
            ser.is_valid(raise_exception=True)
            inv_valid.append(ser.validated_data)

        cp_valid = None
        cp_data = data.get('contingency')
        if cp_data:
            ser = ContingencyPlanWriteSerializer(
                data={**cp_data, 'team': team.pk, 'round': rnd.pk})
            ser.is_valid(raise_exception=True)
            cp_valid = ser.validated_data

        for vd in inv_valid:
            InventoryDecision.objects.update_or_create(
                team=team, round=rnd, product=vd['product'], market=vd['market'],
                defaults={k: v for k, v in vd.items()
                          if k not in ('team', 'round', 'product', 'market')},
            )

        if cp_valid is not None:
            ContingencyPlan.objects.update_or_create(
                team=team, round=rnd,
                defaults={k: v for k, v in cp_valid.items()
                          if k not in ('team', 'round')},
            )

        return Response(self._body(team, rnd), status=status.HTTP_201_CREATED)


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


class ScenarioMarketsView(APIView):
    """CC-12/14 enablement: lightweight market list (id/code/name) so the SC
    decision pages can populate destination-market selectors."""
    def get(self, request, scenario_id):
        markets = MarketDefinition.objects.filter(
            scenario_id=scenario_id).order_by('display_order')
        return Response([
            {'id': m.id, 'code': m.code, 'name': m.name,
             'currency_code': m.currency_code}
            for m in markets
        ])


class ScenarioSegmentsView(APIView):
    """CC-13 enablement: lightweight segment list for the trade-finance page's
    segment/market buyer-instrument selectors. Optional ?segment_type= filter."""
    def get(self, request, scenario_id):
        segments = SegmentDefinition.objects.filter(scenario_id=scenario_id)
        seg_type = request.query_params.get('segment_type')
        if seg_type:
            segments = segments.filter(segment_type=seg_type)
        return Response([
            {'id': s.id, 'name': s.name, 'segment_type': s.segment_type,
             'market_id': s.market_id}
            for s in segments.order_by('display_order')
        ])


# ---------------------------------------------------------------------------
# State retrieval endpoints (§7.3)
# ---------------------------------------------------------------------------

class ResilienceScoreView(APIView):
    permission_classes = [IsTeamMember]

    def get(self, request, game_id, team_id, round_number):
        team, rnd = _get_team_round(self.kwargs)
        history = ResilienceScoreHistory.objects.filter(team=team, round=rnd).first()
        if not history:
            return Response({'score': None, 'components': {}, 'weights_used': {}, 'disruption_impact': {}})
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
