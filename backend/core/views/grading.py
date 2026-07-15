"""
Grading views — rubric management, grade calculation, overrides, CSV export.
"""
import csv
import io

from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsInstructor
from core.views.mixins import InstanceScopedMixin
from core.models.grading import (
    GradingRubric, GradingRubricCategory,
    GradingComponentMapping, TeamGrade, StudentGradeAdjustment,
)
from core.serializers.grading import (
    GradingRubricSerializer, GradingRubricCategorySerializer,
    GradingComponentMappingSerializer, TeamGradeSerializer,
    StudentGradeAdjustmentSerializer,
)
from core.services.grading import (
    calculate_team_grades, override_team_category_score,
    clear_override, seed_default_rubric, get_student_grades,
    COMPONENT_LABELS,
)


class GradingRubricViewSet(viewsets.ModelViewSet):
    """CRUD for grading rubrics.  Instructor-only."""
    permission_classes = [IsInstructor]
    queryset = GradingRubric.objects.all()
    serializer_class = GradingRubricSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        course_id = self.request.query_params.get('course_id')
        if course_id:
            qs = qs.filter(course_id=course_id)
        return qs


class GradingRubricCategoryViewSet(viewsets.ModelViewSet):
    """CRUD for rubric categories."""
    permission_classes = [IsInstructor]
    queryset = GradingRubricCategory.objects.all()
    serializer_class = GradingRubricCategorySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        rubric_id = self.request.query_params.get('rubric_id')
        if rubric_id:
            qs = qs.filter(rubric_id=rubric_id)
        return qs.order_by('sort_order')


class GradingComponentMappingViewSet(viewsets.ModelViewSet):
    """CRUD for component mappings within a category."""
    permission_classes = [IsInstructor]
    queryset = GradingComponentMapping.objects.all()
    serializer_class = GradingComponentMappingSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        category_id = self.request.query_params.get('category_id')
        if category_id:
            qs = qs.filter(category_id=category_id)
        return qs


class TeamGradeViewSet(InstanceScopedMixin, viewsets.ModelViewSet):
    """Read/write team grades."""
    permission_classes = [IsInstructor]
    queryset = TeamGrade.objects.all()
    serializer_class = TeamGradeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        return qs


class StudentGradeAdjustmentViewSet(InstanceScopedMixin, viewsets.ModelViewSet):
    """CRUD for individual student grade adjustments."""
    permission_classes = [IsInstructor]
    queryset = StudentGradeAdjustment.objects.all()
    serializer_class = StudentGradeAdjustmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        user_id = self.request.query_params.get('user_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs


class SeedRubricView(APIView):
    """POST — seed default rubric for a course."""
    permission_classes = [IsInstructor]

    def post(self, request):
        course_id = request.data.get('course_id')
        if not course_id:
            return Response(
                {'error': 'course_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user_id = request.data.get('user_id')
        rubric = seed_default_rubric(
            int(course_id),
            created_by=int(user_id) if user_id else None,
        )
        return Response(GradingRubricSerializer(rubric).data)


class CalculateGradesView(APIView):
    """POST — trigger grade calculation for all teams in an instance."""
    permission_classes = [IsInstructor]

    def post(self, request):
        instance_id = request.data.get('instance_id')
        course_id = request.data.get('course_id')
        if not instance_id or not course_id:
            return Response(
                {'error': 'instance_id and course_id are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user_id = request.data.get('user_id')
        results = calculate_team_grades(
            int(instance_id), int(course_id),
            graded_by=int(user_id) if user_id else None,
        )
        return Response(results)


class OverrideGradeView(APIView):
    """POST — instructor overrides a team's category score."""
    permission_classes = [IsInstructor]

    def post(self, request):
        instance_id = request.data.get('instance_id')
        team_id = request.data.get('team_id')
        category_id = request.data.get('category_id')
        override_score = request.data.get('override_score')
        comments = request.data.get('comments', '')
        user_id = request.data.get('user_id')

        if not all([instance_id, team_id, override_score is not None]):
            return Response(
                {'error': 'instance_id, team_id, and override_score are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        grade = override_team_category_score(
            int(instance_id), int(team_id),
            int(category_id) if category_id else None,
            override_score, comments,
            graded_by=int(user_id) if user_id else None,
        )
        return Response(TeamGradeSerializer(grade).data)

    def delete(self, request):
        """Remove an override, reverting to computed score."""
        instance_id = request.data.get('instance_id')
        team_id = request.data.get('team_id')
        category_id = request.data.get('category_id')

        if not all([instance_id, team_id]):
            return Response(
                {'error': 'instance_id and team_id are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        grade = clear_override(
            int(instance_id), int(team_id),
            int(category_id) if category_id else None,
        )
        if grade:
            return Response(TeamGradeSerializer(grade).data)
        return Response(
            {'error': 'Grade not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )


class StudentGradesView(APIView):
    """GET — individual student grades with adjustments."""
    permission_classes = [IsInstructor]

    def get(self, request):
        instance_id = request.query_params.get('instance_id')
        team_id = request.query_params.get('team_id')
        if not instance_id:
            return Response(
                {'error': 'instance_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        results = get_student_grades(
            int(instance_id),
            team_id=int(team_id) if team_id else None,
        )
        return Response(results)


class ComponentLabelsView(APIView):
    """GET — list available component keys and their labels."""

    def get(self, request):
        return Response([
            {'key': k, 'label': v}
            for k, v in COMPONENT_LABELS.items()
        ])


def _rubric_for_instance(instance_id):
    """
    The active rubric for the course behind a simulation instance.

    instance -> section -> course -> rubric, matching how
    core/services/grading.py resolves it (course_id + is_active).
    """
    from core.models.course import SimulationInstance, Section

    instance = SimulationInstance.objects.filter(
        instance_id=instance_id,
    ).first()
    if not instance:
        return None
    section = Section.objects.filter(section_id=instance.section_id).first()
    if not section:
        return None
    return GradingRubric.objects.filter(
        course_id=section.course_id, is_active=True,
    ).first()


class ExportTeamGradesCsvView(APIView):
    """GET — download team grades as CSV."""
    permission_classes = [IsInstructor]

    def get(self, request):
        params = getattr(request, 'query_params', request.GET)
        instance_id = params.get('instance_id')
        if not instance_id:
            return Response(
                {'error': 'instance_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance_id = int(instance_id)

        from core.models import Team

        # Scope the columns to THIS instance's course rubric. This filtered
        # only on rubric__is_active, so it pulled categories from every course
        # in the system: with two courses seeded, the CSV grew a duplicate
        # "Performance Index" column. Worse, the per-team lookup below is keyed
        # by category NAME, so identically-named categories from another
        # course's rubric collide and repeat the same score, and differently-
        # named ones would render as 0.0 — a team appearing to score zero on a
        # category belonging to a different course entirely.
        rubric = _rubric_for_instance(instance_id)
        if rubric is None:
            categories = GradingRubricCategory.objects.none()
        else:
            categories = GradingRubricCategory.objects.filter(
                rubric_id=rubric.rubric_id,
            ).order_by('sort_order')
        cat_names = [c.category_name for c in categories]

        grades = TeamGrade.objects.filter(instance_id=instance_id)
        team_data = {}
        for g in grades:
            tid = g.team_id
            if tid not in team_data:
                team_data[tid] = {}
            if g.category_id is None:
                team_data[tid]['overall'] = float(g.final_score or 0)
            else:
                for cat in categories:
                    if cat.category_id == g.category_id:
                        team_data[tid][cat.category_name] = float(g.final_score or 0)

        team_map = {t.team_id: t.team_name for t in Team.objects.all()}

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="team_grades.csv"'

        writer = csv.writer(response)
        writer.writerow(['Team ID', 'Team Name'] + cat_names + ['Overall'])
        for tid in sorted(team_data.keys()):
            row = [tid, team_map.get(tid, '')]
            for cn in cat_names:
                row.append(f'{team_data[tid].get(cn, 0):.1f}')
            row.append(f'{team_data[tid].get("overall", 0):.1f}')
            writer.writerow(row)

        return response


class ExportStudentGradesCsvView(APIView):
    """GET — download individual student grades as CSV."""
    permission_classes = [IsInstructor]

    def get(self, request):
        params = getattr(request, 'query_params', request.GET)
        instance_id = params.get('instance_id')
        if not instance_id:
            return Response(
                {'error': 'instance_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from core.models import Team

        students = get_student_grades(int(instance_id))
        team_map = {t.team_id: t.team_name for t in Team.objects.all()}

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="student_grades.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Student ID', 'Display Name', 'Team ID', 'Team Name',
            'Team Grade', 'Adjustment', 'Final Grade',
        ])
        for s in students:
            writer.writerow([
                s.get('student_id', ''),
                s.get('display_name', ''),
                s['team_id'],
                team_map.get(s['team_id'], ''),
                f'{s["team_grade"]:.1f}',
                f'{s["adjustment"]:.1f}',
                f'{s["final_grade"]:.1f}',
            ])

        return response
