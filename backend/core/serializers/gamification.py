from rest_framework import serializers
from core.models.gamification import (
    Achievement, GamificationBadge, PlayerProgress,
    TeamAchievement, TeamBadge,
)


class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = '__all__'


class GamificationBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GamificationBadge
        fields = '__all__'


class PlayerProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerProgress
        fields = '__all__'


class TeamAchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamAchievement
        fields = '__all__'


class TeamBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamBadge
        fields = '__all__'
