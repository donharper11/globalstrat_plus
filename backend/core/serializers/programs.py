from rest_framework import serializers
from core.models import (
    ProgramType, Program, ProgramPortfolio, ProgramFeature,
    Decision,
)
from core.models.core import Round


def _get_round_map(context):
    """Cache round_id -> round_number map on serializer context."""
    if '_round_map' not in context:
        context['_round_map'] = dict(
            Round.objects.values_list('round_id', 'round_number')
        )
    return context['_round_map']


# ---------------------------------------------------------------------------
# Core program tables
# ---------------------------------------------------------------------------

class ProgramTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramType
        fields = '__all__'


class ProgramSerializer(serializers.ModelSerializer):
    round_number = serializers.SerializerMethodField()

    class Meta:
        model = Program
        fields = ['program_id', 'program_name', 'program_type_id',
                  'round_launched', 'round_number', 'status', 'description',
                  'team_id', 'created_at', 'modified_at',
                  'development_status', 'development_rounds_total',
                  'development_rounds_remaining', 'r_and_d_investment',
                  'development_started_round']

    def get_round_number(self, obj):
        rid = getattr(obj, 'round_launched', None)
        if rid is None:
            return None
        return _get_round_map(self.context).get(rid, rid)


class ProgramPortfolioSerializer(serializers.ModelSerializer):
    round_number = serializers.SerializerMethodField()

    class Meta:
        model = ProgramPortfolio
        fields = '__all__'

    def get_round_number(self, obj):
        rid = getattr(obj, 'round_launched', None)
        if rid is None:
            return None
        return _get_round_map(self.context).get(rid, rid)


class ProgramFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgramFeature
        fields = '__all__'


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

class DecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Decision
        fields = '__all__'
