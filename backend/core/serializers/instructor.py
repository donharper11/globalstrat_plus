from rest_framework import serializers
from core.models.instructor import (
    InstructorAction, InstructorEvaluation, InstructorNote,
    InstructorFeedbackTemplate, InstructorScenarioCustomization,
    AdminAction,
)


class InstructorActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstructorAction
        fields = '__all__'


class InstructorEvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstructorEvaluation
        fields = '__all__'


class InstructorNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstructorNote
        fields = '__all__'


class InstructorFeedbackTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstructorFeedbackTemplate
        fields = '__all__'


class InstructorScenarioCustomizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstructorScenarioCustomization
        fields = '__all__'


class AdminActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminAction
        fields = '__all__'
