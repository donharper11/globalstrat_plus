from rest_framework import serializers
from core.models import (
    Score, ScoreType, LeaderboardScore, LeaderboardMetric,
    TeamPerformance,
)


class ScoreTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScoreType
        fields = '__all__'


class ScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Score
        fields = '__all__'


class LeaderboardMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaderboardMetric
        fields = '__all__'


class LeaderboardScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaderboardScore
        fields = '__all__'


class TeamPerformanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamPerformance
        fields = '__all__'
