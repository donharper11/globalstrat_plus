from rest_framework import serializers
from core.models.grading import (
    GradingRubric, GradingRubricCategory,
    GradingComponentMapping, TeamGrade, StudentGradeAdjustment,
)


class GradingComponentMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradingComponentMapping
        fields = '__all__'


class GradingRubricCategorySerializer(serializers.ModelSerializer):
    components = GradingComponentMappingSerializer(many=True, read_only=True)

    class Meta:
        model = GradingRubricCategory
        fields = '__all__'


class GradingRubricSerializer(serializers.ModelSerializer):
    categories = GradingRubricCategorySerializer(many=True, read_only=True)

    class Meta:
        model = GradingRubric
        fields = '__all__'


class TeamGradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeamGrade
        fields = '__all__'


class StudentGradeAdjustmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentGradeAdjustment
        fields = '__all__'
