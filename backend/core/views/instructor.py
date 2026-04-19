from rest_framework import viewsets

from core.views.mixins import InstanceScopedMixin
from core.models.instructor import (
    InstructorAction, InstructorEvaluation, InstructorNote,
    InstructorFeedbackTemplate, InstructorScenarioCustomization,
    )
from core.serializers.instructor import (
    InstructorActionSerializer, InstructorEvaluationSerializer,
    InstructorNoteSerializer, InstructorFeedbackTemplateSerializer,
    InstructorScenarioCustomizationSerializer,
    )
from core.permissions import IsInstructor


class InstructorActionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInstructor]
    queryset = InstructorAction.objects.all()
    serializer_class = InstructorActionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        user_id = self.request.query_params.get('user_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs


class InstructorEvaluationViewSet(InstanceScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsInstructor]
    queryset = InstructorEvaluation.objects.all()
    serializer_class = InstructorEvaluationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        return qs


class InstructorNoteViewSet(InstanceScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsInstructor]
    queryset = InstructorNote.objects.all()
    serializer_class = InstructorNoteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        return qs


class InstructorFeedbackTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInstructor]
    queryset = InstructorFeedbackTemplate.objects.all()
    serializer_class = InstructorFeedbackTemplateSerializer


class InstructorScenarioCustomizationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInstructor]
    queryset = InstructorScenarioCustomization.objects.all()
    serializer_class = InstructorScenarioCustomizationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        instructor_id = self.request.query_params.get('instructor_id')
        if instructor_id:
            qs = qs.filter(instructor_id=instructor_id)
        return qs
