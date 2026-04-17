from rest_framework import viewsets
from core.models import (
    TeamIncomeStatement, TeamBalanceSheet, TeamCashFlow,
    TeamResources, FinancialRevenue, FinancialExpense,
    CumulativeSales, NewSalesByRound,
)
from core.serializers import (
    TeamIncomeStatementSerializer, TeamBalanceSheetSerializer,
    TeamCashFlowSerializer, TeamResourcesSerializer,
    FinancialRevenueSerializer, FinancialExpenseSerializer,
    CumulativeSalesSerializer, NewSalesByRoundSerializer,
)
from core.views.mixins import InstanceScopedMixin


class IncomeStatementViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TeamIncomeStatement.objects.all()
    serializer_class = TeamIncomeStatementSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        return qs


class BalanceSheetViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TeamBalanceSheet.objects.all()
    serializer_class = TeamBalanceSheetSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        return qs


class CashFlowViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TeamCashFlow.objects.all()
    serializer_class = TeamCashFlowSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        return qs


class TeamResourcesViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = TeamResources.objects.all()
    serializer_class = TeamResourcesSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        return qs


class FinancialRevenueViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FinancialRevenue.objects.all()
    serializer_class = FinancialRevenueSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        program_id = self.request.query_params.get('program_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        if program_id:
            qs = qs.filter(program_id=program_id)
        return qs


class FinancialExpenseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FinancialExpense.objects.all()
    serializer_class = FinancialExpenseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        program_id = self.request.query_params.get('program_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        if program_id:
            qs = qs.filter(program_id=program_id)
        return qs


class CumulativeSalesViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = CumulativeSales.objects.all()
    serializer_class = CumulativeSalesSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        customer_id = self.request.query_params.get('customer_id')
        round_id = self.request.query_params.get('round_id')
        program_id = self.request.query_params.get('program_id')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        if program_id:
            qs = qs.filter(program_id=program_id)
        return qs


class NewSalesByRoundViewSet(InstanceScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = NewSalesByRound.objects.all()
    serializer_class = NewSalesByRoundSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        customer_id = self.request.query_params.get('customer_id')
        round_id = self.request.query_params.get('round_id')
        program_id = self.request.query_params.get('program_id')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        if program_id:
            qs = qs.filter(program_id=program_id)
        return qs
