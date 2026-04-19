from rest_framework import serializers
from core.models import (
    TeamIncomeStatement, TeamBalanceSheet, TeamCashFlow,
    TeamResources, FinancialRevenue, FinancialExpense,
    NewSalesByRound,
)
from core.models.core import Round


class _RoundNumberMixin(serializers.Serializer):
    """Add round_number (from rounds table) so the UI shows 0, 1, 2… not round_id."""
    round_number = serializers.SerializerMethodField()

    def get_round_number(self, obj):
        rid = getattr(obj, 'round_id', None)
        if rid is None:
            return None
        # Cache the lookup map on the serializer context
        ctx = self.context
        if '_round_map' not in ctx:
            ctx['_round_map'] = dict(
                Round.objects.values_list('round_id', 'round_number')
            )
        return ctx['_round_map'].get(rid, rid)


class TeamIncomeStatementSerializer(_RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = TeamIncomeStatement
        fields = '__all__'


class TeamBalanceSheetSerializer(_RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = TeamBalanceSheet
        fields = '__all__'


class TeamCashFlowSerializer(_RoundNumberMixin, serializers.ModelSerializer):
    class Meta:
        model = TeamCashFlow
        fields = '__all__'


class TeamResourcesSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamResources
        fields = '__all__'


class FinancialRevenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialRevenue
        fields = '__all__'


class FinancialExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialExpense
        fields = '__all__'


class NewSalesByRoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewSalesByRound
        fields = '__all__'
