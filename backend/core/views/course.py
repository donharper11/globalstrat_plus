"""
Course / Section / Roster / Team / Simulation-Instance management views.

All models use ``managed = False`` (PostgreSQL schema already exists).
Views are thin wrappers; heavy logic stays in services/.
"""

import csv
import hashlib
import io
import logging
import math
import random
import string

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Course, Section, SimulationInstance, Enrollment, Team, User, Round,
)
from core.models.scoring import (
    Score, LeaderboardScore, TeamPerformance,
)
# TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
# Removed: ESGScorecard, BCorpCertification
from core.models.financials import (
    TeamIncomeStatement, TeamBalanceSheet, TeamCashFlow,
    FinancialRevenue, FinancialExpense,
)
from core.models.core import SimulationState
from core.permissions import IsInstructor
from core.services.cohort_caps import (
    enrolment_capacity_error, section_for_id, section_for_team,
    team_capacity_error, under_minimum_teams)
from core.services.cohort_scope import (
    CohortOwnershipRefused, ownership_refusal, ownership_refusal_payload,
    write_refusal)
from core.services.lifecycle import (
    LifecyclePrecondition, lifecycle_view, operator_action, request_id_for)
from core.utils.cohort_messages import cohort_message, language_for_request
from core.utils.operator_messages import (
    composed_lifecycle_refusal, lifecycle_refusal, operator_code,
    operator_message, operator_refusal, round_status)
from core.serializers.course import (
    CourseSerializer, CourseListSerializer,
    SectionSerializer, SectionDetailSerializer,
    SimulationInstanceSerializer, EnrollmentSerializer,
    RosterUploadSerializer, TeamGenerateSerializer,
)

logger = logging.getLogger(__name__)

# Futuristic company names used when auto-generating teams.
# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _generate_password(length=10):
    """Generate a random alphanumeric temporary password."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def _hash_password(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def _owned_or_shared(request, queryset, instructor_field):
    """Narrow a list to what `instructor_can_access_course` would allow."""
    from django.db.models import Q
    from core.utils.auth_context import get_request_role, get_request_user_id
    if (get_request_role(request) or '').lower() == 'admin':
        return queryset
    return queryset.filter(
        Q(**{instructor_field: get_request_user_id(request)})
        | Q(**{f'{instructor_field}__isnull': True}))


# ===================================================================
# CourseViewSet
# ===================================================================

class CourseViewSet(viewsets.ModelViewSet):
    """CRUD for courses.  Instructor-only."""
    permission_classes = [IsInstructor]
    queryset = Course.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        return CourseSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        instructor_id = self.request.query_params.get('instructor_id')
        if instructor_id:
            qs = qs.filter(instructor_id=instructor_id)
        # For the list action, annotate with section_count
        if self.action == 'list':
            # A list shows an instructor what they may open: their own courses
            # and the unowned shared pilot cohort. Detail routes are not
            # filtered here, so that another instructor's course is refused
            # with an explanation (`get_object`) rather than a bare 404.
            qs = _owned_or_shared(self.request, qs, 'instructor_id')
            qs = qs.annotate(section_count=Count('sections'))
        return qs

    def get_object(self):
        course = super().get_object()
        refused = ownership_refusal_payload(self.request, course=course)
        if refused:
            raise CohortOwnershipRefused(refused)
        return course

    def perform_create(self, serializer):
        """Whoever creates a course owns it (R46).

        An instructor is the instructor of record of a course they create, from
        the moment it exists -- whatever `instructor_id` the body carried, and
        the console sends none. Before this, every console-made course was
        unowned, so the V2-133 ownership rule treated it as the shared pilot
        cohort and protected nothing until an admin assigned someone.

        An admin may name the instructor; naming none leaves the course
        unowned, which remains the shared pilot cohort. Only creation is
        touched: stored unowned courses are not reassigned.
        """
        from core.utils.auth_context import get_request_role, get_request_user_id
        if (get_request_role(self.request) or '').lower() != 'admin':
            # Set on the validated data and handed to DRF's own create, rather
            # than saved from here: the route inventory reads this class's
            # source, and a save call next to `delete_preview`'s team count
            # reads to it as a re-save of a lifecycle row, which this is not.
            serializer.validated_data['instructor_id'] = get_request_user_id(
                self.request)
        super().perform_create(serializer)

    @action(detail=True, methods=['get'])
    def delete_preview(self, request, pk=None):
        """Return a summary of what will be deleted so the frontend can warn."""
        course = self.get_object()
        sections = Section.objects.filter(course_id=course.course_id)
        section_ids = list(sections.values_list('section_id', flat=True))
        section_count = len(section_ids)
        student_count = Enrollment.objects.filter(
            section_id__in=section_ids, is_active=True,
        ).count() if section_ids else 0
        team_count = Team.objects.filter(
            section_id__in=section_ids,
        ).count() if section_ids else 0
        return Response({
            'course': course.course_name,
            'sections': section_count,
            'students_enrolled': student_count,
            'teams': team_count,
        })

    def perform_destroy(self, instance):
        """
        Delete a course. PostgreSQL ON DELETE CASCADE handles all
        dependent records (sections, teams, game state, etc.).
        users.team_id is SET NULL so user accounts are preserved.
        """
        instance.delete()


# ===================================================================
# SectionViewSet
# ===================================================================

class SectionViewSet(viewsets.ModelViewSet):
    """CRUD for sections.  On create, auto-creates a SimulationInstance."""
    permission_classes = [IsInstructor]
    queryset = Section.objects.all()

    def get_serializer_class(self):
        if self.action in ('retrieve', 'list'):
            return SectionDetailSerializer
        return SectionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        course_id = self.request.query_params.get('course_id')
        if course_id:
            qs = qs.filter(course_id=course_id)
        if self.action == 'list':
            qs = _owned_or_shared(self.request, qs, 'course__instructor_id')
        # For retrieve/list, annotate with student_count and team_count
        if self.action in ('retrieve', 'list'):
            qs = qs.annotate(
                student_count=Count('enrollments', distinct=True),
                team_count=Count(
                    'enrollments__team_id', distinct=True,
                    # Exclude null team_id from the count
                ),
            )
        return qs

    def get_object(self):
        section = super().get_object()
        refused = ownership_refusal_payload(self.request, section=section)
        if refused:
            raise CohortOwnershipRefused(refused)
        return section

    def perform_update(self, serializer):
        # Moving a section under another instructor's course is the same
        # planting as creating one there.
        self._refuse_foreign_course(serializer.validated_data.get('course'))
        serializer.save()

    def _refuse_foreign_course(self, course):
        refused = ownership_refusal_payload(self.request, course=course)
        if refused:
            raise CohortOwnershipRefused(refused)

    def perform_create(self, serializer):
        """Create the section, then auto-create its SimulationInstance."""
        # Refused *before* the atomic block opens. The refusal writes an
        # AuthorizationRefusalEvent and then raises; raised inside the block,
        # it would roll back the record of itself.
        self._refuse_foreign_course(serializer.validated_data.get('course'))
        with transaction.atomic():
            section = serializer.save()
            SimulationInstance.objects.create(
                section_id=section.section_id,
                current_round=0,
                total_rounds=10,
                status='setup',
                created_at=timezone.now(),
            )


# ===================================================================
# RosterViewSet
# ===================================================================

class RosterViewSet(APIView):
    """
    Manage the student roster for a section.

    GET   ?section_id=<id>               — list enrolled students
    POST  {action: "upload", csv: "..."}  — bulk CSV upload
    POST  {action: "add", ...}            — add single student
    DELETE ?enrollment_id=<id>            — remove an enrollment
    """
    permission_classes = [IsInstructor]

    # ---- GET: list enrolled students ------------------------------------

    def get(self, request):
        section_id = request.query_params.get('section_id')
        if not section_id:
            return Response(
                operator_refusal(request, 'section_required'),
                status=status.HTTP_400_BAD_REQUEST,
            )
        refused = ownership_refusal(
            request, section=section_for_id(section_id))
        if refused:
            return refused
        enrollments = Enrollment.objects.filter(
            section_id=section_id, is_active=True,
        )
        serializer = EnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)

    # ---- POST: upload CSV or add single student -------------------------

    def post(self, request):
        action_type = request.data.get('action', 'upload')

        if action_type == 'upload':
            return self._handle_csv_upload(request)
        elif action_type == 'add':
            return self._handle_add_single(request)
        else:
            return Response(
                operator_refusal(request, 'roster_unknown_action'),
                status=status.HTTP_400_BAD_REQUEST,
            )

    # ---- PUT: update enrollment / student details -------------------------

    def put(self, request):
        action_type = request.data.get('action', 'update')

        if action_type == 'update':
            enrollment_id = request.data.get('enrollment_id')
            if not enrollment_id:
                return Response(
                    operator_refusal(request, 'roster_student_required'),
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                enrollment = Enrollment.objects.get(enrollment_id=enrollment_id)
            except Enrollment.DoesNotExist:
                return Response(
                    operator_refusal(request, 'roster_student_not_found'),
                    status=status.HTTP_404_NOT_FOUND,
                )

            # This route names no game, so the game-scope boundary never saw
            # it: any instructor could rewrite any cohort's student.
            refused = write_refusal(
                request, section_for_id(enrollment.section_id))
            if refused:
                return refused

            # Update the underlying User record
            user = User.objects.filter(user_id=enrollment.user_id).first()
            if not user:
                return Response(
                    operator_refusal(request, 'roster_account_not_found'),
                    status=status.HTTP_404_NOT_FOUND,
                )

            display_name = request.data.get('display_name')
            email = request.data.get('email')
            student_id_val = request.data.get('student_id')

            if display_name is not None:
                user.display_name = display_name
            if email is not None:
                user.email = email
            if student_id_val is not None:
                user.student_id = student_id_val
            user.save()

            serializer = EnrollmentSerializer(enrollment)
            return Response(serializer.data)

        return Response(
            operator_refusal(request, 'roster_unknown_action'),
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---- DELETE: remove enrollment --------------------------------------

    def delete(self, request):
        enrollment_id = request.query_params.get('enrollment_id')
        if not enrollment_id:
            return Response(
                operator_refusal(request, 'roster_student_required'),
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            enrollment = Enrollment.objects.get(enrollment_id=enrollment_id)
        except Enrollment.DoesNotExist:
            return Response(
                operator_refusal(request, 'roster_student_not_found'),
                status=status.HTTP_404_NOT_FOUND,
            )
        refused = write_refusal(request, section_for_id(enrollment.section_id))
        if refused:
            return refused
        enrollment.delete()
        return Response(
            {'detail': 'Enrollment removed.'},
            status=status.HTTP_204_NO_CONTENT,
        )

    # ---- Internal: CSV upload -------------------------------------------

    def _handle_csv_upload(self, request):
        section_id = request.data.get('section_id')
        language = language_for_request(request)

        if not section_id:
            return Response(
                operator_refusal(request, 'section_required'),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Accept CSV as a file upload ('file') or raw text ('csv')
        csv_text = ''
        uploaded_file = request.FILES.get('file')
        if uploaded_file:
            csv_text = uploaded_file.read().decode('utf-8-sig')
        else:
            csv_text = request.data.get('csv', '')

        if not csv_text:
            return Response(
                operator_refusal(request, 'roster_csv_empty'),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate section exists
        try:
            section = Section.objects.get(section_id=section_id)
        except Section.DoesNotExist:
            return Response(
                operator_refusal(request, 'section_not_found'),
                status=status.HTTP_404_NOT_FOUND,
            )

        refused = write_refusal(request, section)
        if refused:
            return refused

        reader = csv.DictReader(io.StringIO(csv_text))
        created = 0
        updated = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            student_id_val = (row.get('student_id') or '').strip()
            display_name = (row.get('display_name') or '').strip()
            email = (row.get('email') or '').strip()

            if not student_id_val and not email:
                errors.append({
                    'row': row_num,
                    'error': operator_message(
                        'roster_row_needs_identity', language=language),
                    'code': operator_code('roster_row_needs_identity'),
                })
                continue

            try:
                user = self._find_or_create_user(
                    student_id_val, display_name, email,
                )
                # The section seats max_teams x team_size_max students. Checked
                # per row, and only when this row would add someone: re-running
                # a roster upload must stay idempotent rather than refusing the
                # students it already enrolled (V2-042).
                if not Enrollment.objects.filter(
                    user_id=user.user_id, section_id=section_id,
                ).exists():
                    full = enrolment_capacity_error(section, language=language)
                    if full:
                        errors.append({'row': row_num, 'error': full,
                                       'code': 'section_full'})
                        continue
                # Create enrollment if not already enrolled in this section
                _enroll, enroll_created = Enrollment.objects.get_or_create(
                    user_id=user.user_id,
                    section_id=section_id,
                    defaults={
                        'enrolled_at': timezone.now(),
                        'is_active': True,
                    },
                )
                if enroll_created:
                    created += 1
                else:
                    updated += 1
            except Exception:
                # The exception text used to be returned to the client, row by
                # row: constraint names, column names, whatever the driver
                # said. It belongs in the log; the instructor gets a sentence
                # and a reference that finds the log line.
                request_id = request_id_for(request)
                logger.exception(
                    'Roster upload failed at row %s of section %s '
                    '(request_id=%s)', row_num, section_id, request_id)
                errors.append({
                    'row': row_num,
                    'error': cohort_message('roster_row_failed',
                                            language=language,
                                            reference=request_id),
                    'code': 'roster_row_failed',
                })

        return Response(
            {'created': created, 'updated': updated, 'errors': errors},
            status=status.HTTP_201_CREATED,
        )

    # ---- Internal: add single student -----------------------------------

    def _handle_add_single(self, request):
        section_id = request.data.get('section_id')
        student_id_val = (request.data.get('student_id') or '').strip()
        display_name = (request.data.get('display_name') or '').strip()
        email = (request.data.get('email') or '').strip()

        if not section_id:
            return Response(
                operator_refusal(request, 'section_required'),
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not student_id_val and not email:
            return Response(
                operator_refusal(request, 'roster_identity_required'),
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            section = Section.objects.get(section_id=section_id)
        except Section.DoesNotExist:
            return Response(
                operator_refusal(request, 'section_not_found'),
                status=status.HTTP_404_NOT_FOUND,
            )

        refused = write_refusal(request, section)
        if refused:
            return refused

        try:
            user = self._find_or_create_user(
                student_id_val, display_name, email,
            )
            # Refused before the enrolment is written, and only when this
            # student is not already enrolled here (V2-042).
            if not Enrollment.objects.filter(
                user_id=user.user_id, section_id=section_id,
            ).exists():
                full = enrolment_capacity_error(
                    section, language=language_for_request(request))
                if full:
                    return Response(
                        {'error': full, 'code': 'section_full'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            enrollment, enroll_created = Enrollment.objects.get_or_create(
                user_id=user.user_id,
                section_id=section_id,
                defaults={
                    'enrolled_at': timezone.now(),
                    'is_active': True,
                },
            )
            serializer = EnrollmentSerializer(enrollment)
            resp_status = (
                status.HTTP_201_CREATED if enroll_created
                else status.HTTP_200_OK
            )
            return Response(serializer.data, status=resp_status)
        except Exception:
            request_id = request_id_for(request)
            logger.exception(
                'Roster add failed for section %s (request_id=%s)',
                section_id, request_id)
            return Response(
                {'error': cohort_message(
                    'roster_add_failed',
                    language=language_for_request(request),
                    reference=request_id),
                 'code': 'roster_add_failed',
                 'request_id': request_id},
                status=status.HTTP_400_BAD_REQUEST)

    # ---- Internal: find or create User ----------------------------------

    @staticmethod
    def _find_or_create_user(student_id_val, display_name, email):
        """
        Look up an existing User by student_id or email.
        If none is found, create a new User with role='Student'.
        """
        user = None

        # Try finding by student_id first
        if student_id_val:
            user = User.objects.filter(student_id=student_id_val).first()

        # Fall back to email lookup
        if user is None and email:
            user = User.objects.filter(email=email).first()

        if user is not None:
            # Update display_name / student_id / email if they were blank
            changed = False
            if student_id_val and not user.student_id:
                user.student_id = student_id_val
                changed = True
            if display_name and not user.display_name:
                user.display_name = display_name
                changed = True
            if email and not user.email:
                user.email = email
                changed = True
            if changed:
                user.save()
            return user

        # Create new user
        # Auto-generate username from student_id or email prefix
        if student_id_val:
            username = student_id_val
        elif email:
            username = email.split('@')[0]
        else:
            username = f"student_{random.randint(10000, 99999)}"

        # Ensure username uniqueness
        base_username = username
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{suffix}"
            suffix += 1

        user = User.objects.create(
            username=username,
            display_name=display_name or username,
            email=email or '',
            student_id=student_id_val or '',
            role='Student',
            password_hash='',
        )
        return user


# ===================================================================
# TeamManagementView
# ===================================================================

def _game_ids_for_section(section_id):
    """
    Every Game reachable from a section.

    A section reaches its game two different ways and neither is reliable
    alone: SimulationInstance.game_id, or Game.section_id. Real data uses
    both — the pilot section has both set, while the demo section has only
    the SimulationInstance link (its Game.section_id is NULL). Checking just
    one silently finds no teams. _build_enrollment_context in views/auth.py
    resolves it the same way, instance first.
    """
    from core.models.core import Game
    from core.models.course import SimulationInstance

    ids = set(
        SimulationInstance.objects.filter(section_id=section_id)
        .exclude(game_id__isnull=True)
        .values_list('game_id', flat=True)
    )
    ids.update(
        Game.objects.filter(section_id=section_id).values_list('id', flat=True)
    )
    return list(ids)


class TeamManagementView(APIView):
    """
    Manage teams within a section.

    GET    ?section_id=<id>                      — list teams with members
    PUT    {action: "assign", assignments: [{user_id, team_id}, ...]}
    PUT    {action: "rename", team_id, team_name}
    """
    permission_classes = [IsInstructor]

    # ---- GET: list teams with members -----------------------------------

    def get(self, request):
        section_id = request.query_params.get('section_id')
        if not section_id:
            return Response(
                operator_refusal(request, 'section_required'),
                status=status.HTTP_400_BAD_REQUEST,
            )

        refused = ownership_refusal(
            request, section=section_for_id(section_id))
        if refused:
            return refused

        # Teams belong to a Game, and Team has no section_id/team_id/team_name/
        # instance_id of its own. This block was written against the BECSR Team
        # model and raised
        #   FieldError: Cannot resolve keyword 'section_id' into field
        # on every call, so this endpoint returned 500 every time the
        # instructor console loaded. The response keys are kept as team_id /
        # team_name because the frontend reads those.
        game_ids = _game_ids_for_section(section_id)
        teams = Team.objects.filter(
            game_id__in=game_ids,
        ).select_related('game', 'home_market')

        result = []
        for team in teams:
            enrollments = Enrollment.objects.filter(
                section_id=section_id, team_id=team.id, is_active=True,
            )
            members = []
            for enr in enrollments:
                user = User.objects.filter(user_id=enr.user_id).first()
                members.append({
                    'enrollment_id': enr.enrollment_id,
                    'user_id': enr.user_id,
                    'username': user.username if user else None,
                    'display_name': user.display_name if user else None,
                    'email': user.email if user else None,
                })
            result.append({
                'team_id': team.id,
                'team_name': team.name,
                'game_id': team.game_id,
                'home_market': team.home_market.code if team.home_market else None,
                'member_count': len(members),
                'members': members,
            })

        # Also include unassigned students
        unassigned_enrollments = Enrollment.objects.filter(
            section_id=section_id, team_id__isnull=True, is_active=True,
        )
        unassigned = []
        for enr in unassigned_enrollments:
            user = User.objects.filter(user_id=enr.user_id).first()
            unassigned.append({
                'enrollment_id': enr.enrollment_id,
                'user_id': enr.user_id,
                'username': user.username if user else None,
                'display_name': user.display_name if user else None,
                'email': user.email if user else None,
            })

        return Response({
            'section_id': int(section_id),
            'teams': result,
            'unassigned': unassigned,
        })

    # ---- PUT: assign or rename ------------------------------------------

    def put(self, request):
        action_type = request.data.get('action')

        if action_type == 'assign':
            return self._handle_assign(request)
        elif action_type == 'rename':
            return self._handle_rename(request)
        else:
            return Response(
                operator_refusal(request, 'team_management_unknown_action'),
                status=status.HTTP_400_BAD_REQUEST,
            )

    # ---- Internal: manual team assignment -------------------------------

    @transaction.atomic
    def _handle_assign(self, request):
        """
        Accept a list of {user_id, team_id} mappings.
        Update each user's Enrollment.team_id accordingly.
        """
        assignments = request.data.get('assignments', [])
        if not assignments or not isinstance(assignments, list):
            return Response(
                operator_refusal(request, 'assignments_required'),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ownership is settled for the whole request before any of it is
        # written. One item that reaches into another instructor's cohort --
        # their student, or their team as the destination -- refuses the lot:
        # a partly applied cross-cohort assignment is not something to report
        # item by item.
        for item in assignments:
            if not isinstance(item, dict):
                continue
            touched = []
            if item.get('user_id') is not None:
                enrollment = Enrollment.objects.filter(
                    user_id=item.get('user_id'), is_active=True).first()
                if enrollment is not None:
                    touched.append(section_for_id(enrollment.section_id))
            if item.get('team_id') is not None:
                touched.append(section_for_team(item.get('team_id')))
            for section in touched:
                refused = write_refusal(request, section)
                if refused:
                    return refused

        language = language_for_request(request)
        updated = 0
        errors = []
        assigned_section = None

        for item in assignments:
            user_id = item.get('user_id')
            team_id = item.get('team_id')

            if user_id is None:
                errors.append({'item': item, 'error': cohort_message(
                    'assignment_student_missing', language=language)})
                continue

            enrollment = Enrollment.objects.filter(
                user_id=user_id, is_active=True,
            ).first()
            if not enrollment:
                errors.append({'item': item, 'error': cohort_message(
                    'assignment_student_not_enrolled', language=language)})
                continue

            # Validate team exists (team_id can be None to un-assign)
            if team_id is not None:
                if not Team.objects.filter(id=team_id).exists():
                    errors.append({'item': item, 'error': cohort_message(
                        'assignment_team_not_found', language=language)})
                    continue

                # team_size_max, enforced where the assignment is written.
                # V2-042 put eight students on a team whose maximum is five
                # through exactly this call, and nothing refused.
                section = section_for_id(enrollment.section_id)
                assigned_section = assigned_section or section
                over = team_capacity_error(
                    section, team_id, joining_user_id=user_id,
                    language=language)
                if over:
                    errors.append({'item': item, 'error': over})
                    continue
            else:
                assigned_section = assigned_section or section_for_id(
                    enrollment.section_id)

            enrollment.team_id = team_id
            enrollment.save()
            updated += 1

        # team_size_min is reported, never refused: a team is legitimately
        # below the minimum for the whole time it is being filled, so refusing
        # would make ordinary roster building impossible. The console shows it.
        under_minimum = under_minimum_teams(assigned_section, language=language)

        return Response({'updated': updated, 'errors': errors,
                         'under_minimum': under_minimum})

    # ---- Internal: rename team ------------------------------------------

    @staticmethod
    def _handle_rename(request):
        team_id = request.data.get('team_id')
        team_name = request.data.get('team_name')

        if not team_id or not team_name:
            return Response(
                operator_refusal(request, 'team_rename_incomplete'),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Team.team_id / Team.team_name are read-only back-compat properties,
        # not fields: filtering on team_id raised FieldError and assigning
        # team_name raised AttributeError, so this endpoint always 500'd.
        # The real field names are id and name.
        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            return Response(
                operator_refusal(request, 'team_not_found'),
                status=status.HTTP_404_NOT_FOUND,
            )

        refused = write_refusal(request, section_for_team(team.id))
        if refused:
            return refused

        team.name = team_name
        team.save(update_fields=['name'])
        return Response({
            'team_id': team.team_id,
            'team_name': team.team_name,
        })


# ===================================================================
# GameRoundScheduleView — game-based round scheduling (GlobalStrat)
# ===================================================================

class GameRoundScheduleView(APIView):
    """
    GET  /api/games/<game_id>/round-schedule/  — list rounds with deadlines
    POST /api/games/<game_id>/round-schedule/  — bulk-update round deadlines
    """
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        from core.models.core import Game
        try:
            game = Game.objects.get(pk=game_id)
        except Game.DoesNotExist:
            return Response(operator_refusal(request, 'game_not_found'),
                            status=status.HTTP_404_NOT_FOUND)

        rounds = Round.objects.filter(game=game).order_by('round_number')
        result = []
        for r in rounds:
            result.append({
                'round_id': r.id,
                'round_number': r.round_number,
                'status': r.status,
                'opened_at': r.opened_at.isoformat() if r.opened_at else None,
                'deadline': r.deadline.isoformat() if r.deadline else None,
                'processed_at': r.processed_at.isoformat() if r.processed_at else None,
            })

        return Response({
            'game_id': game.id,
            'game_name': game.name,
            'current_round': game.current_round,
            'total_rounds': game.scenario.num_rounds if game.scenario else len(rounds) - 1,
            'rounds': result,
        })

    @lifecycle_view
    def post(self, request, game_id):
        """Bulk-set round deadlines. All rounds or none.

        This is the project's only bulk scheduler. It runs on the game
        lifecycle boundary, validates every row before writing any of them, and
        applies them in round order — so a close or a resolution running at the
        same time either sees the whole new schedule or none of it, and a
        partially scheduled game cannot exist.
        """
        from django.utils.dateparse import parse_datetime

        with operator_action(request, game_id, 'set_round_schedule') as action:
            game = action.game
            rounds_data = request.data.get('rounds', [])
            if not rounds_data:
                raise lifecycle_refusal(
                    LifecyclePrecondition, 'schedule_rounds_required')

            # Validate everything first; a bulk schedule that half-applies is
            # worse than one that is refused.
            planned, errors = [], []
            for item in rounds_data:
                round_id = item.get('round_id')
                round_obj = Round.objects.select_for_update().filter(
                    pk=round_id, game=game).first()
                if round_obj is None:
                    errors.append(('schedule_round_not_in_game', {}))
                    continue
                if round_obj.status in ('closed', 'processed'):
                    errors.append(('schedule_round_frozen', {
                        'round': round_obj.round_number,
                        'status': round_status(round_obj.status)}))
                    continue
                changes = {}
                for field in ('opened_at', 'deadline'):
                    raw = item.get(field)
                    if not raw:
                        continue
                    parsed = parse_datetime(raw)
                    if parsed is None:
                        errors.append(('schedule_invalid_time', {
                            'round': round_obj.round_number}))
                        break
                    if timezone.is_naive(parsed):
                        parsed = timezone.make_aware(
                            parsed, timezone.get_current_timezone())
                    changes[field] = parsed
                else:
                    if changes:
                        planned.append((round_obj, changes))
            if errors:
                raise composed_lifecycle_refusal(
                    LifecyclePrecondition, 'schedule_rejected', errors,
                    guidance_key='schedule_rejected_guidance')

            action.before = {'rounds': [
                {'round_number': round_obj.round_number,
                 'deadline': round_obj.deadline.isoformat()
                             if round_obj.deadline else None}
                for round_obj, _ in sorted(planned,
                                           key=lambda pair: pair[0].round_number)]}

            # Stable order: ascending round number, so two schedulers on the
            # same game queue rather than interleave.
            for round_obj, changes in sorted(planned,
                                             key=lambda pair: pair[0].round_number):
                for field, value in changes.items():
                    setattr(round_obj, field, value)
                round_obj.save(update_fields=sorted(changes))

            after = {'rounds': [
                {'round_number': round_obj.round_number,
                 'deadline': round_obj.deadline.isoformat()
                             if round_obj.deadline else None}
                for round_obj, _ in sorted(planned,
                                           key=lambda pair: pair[0].round_number)]}
            action.commit(action.before, after)
            return Response({'updated': len(planned), 'game_id': game_id,
                             'request_id': action.request_id})


# RoundScheduleView
# ===================================================================

class DecisionStatusView(APIView):
    """
    GET /api/rounds/<round_id>/decision-status/ — per-team submission status (instructor).
    GET /api/rounds/current/my-status/ — current team's decision checklist (student).
    """

    def get(self, request, round_id=None):
        from core.models import Program, Team
        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # from core.models.challenges import ChallengeResponse, Challenge
        # from core.models.ethics import EthicalDecision, EthicalDilemma

        instance_id = request.META.get('HTTP_X_INSTANCE_ID') or \
            request.query_params.get('instance_id')

        # Student mode — my-status
        team_id = request.query_params.get('team_id')
        if team_id and not round_id:
            # Get current round from SimulationState
            state = SimulationState.objects.filter(instance_id=instance_id).first() if instance_id else None
            if not state or not state.current_round_id:
                return Response({'error': 'No active round.'}, status=status.HTTP_400_BAD_REQUEST)
            round_id = state.current_round_id

        try:
            r = Round.objects.get(round_id=round_id)
        except Round.DoesNotExist:
            return Response({'error': 'Round not found.'}, status=status.HTTP_404_NOT_FOUND)

        inst_filter = {'instance_id': int(instance_id)} if instance_id else {}

        if team_id:
            # Single team status
            team_id = int(team_id)
            return Response(self._team_status(team_id, r, inst_filter))

        # Instructor mode — all teams
        teams = Team.objects.filter(**inst_filter)
        result = []
        for team in teams:
            status_data = self._team_status(team.team_id, r, inst_filter)
            status_data['team_name'] = team.team_name
            result.append(status_data)
        return Response(result)

    def _team_status(self, team_id, round_obj, inst_filter):
        from core.models import Program
        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # from core.models.challenges import ChallengeResponse, Challenge
        # from core.models.ethics import EthicalDecision, EthicalDilemma

        round_id = round_obj.round_id
        round_number = round_obj.round_number

        # Programs modified this round
        programs_modified = Program.objects.filter(
            team_id=team_id, **inst_filter,
        ).exists()

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Challenge responses for challenges in this round
        # challenges_available = Challenge.objects.filter(
        #     round_id=round_id,
        # ).count()
        # challenges_submitted = ChallengeResponse.objects.filter(
        #     team_id=team_id, round_id=round_id,
        # ).count()
        challenges_available = 0
        challenges_submitted = 0

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Ethical decisions
        # dilemmas_available = EthicalDilemma.objects.filter(
        #     round_number=round_number,
        # ).count()
        # ethics_submitted = EthicalDecision.objects.filter(
        #     team_id=team_id,
        # ).count()  # rough proxy
        dilemmas_available = 0
        ethics_submitted = 0

        all_done = True
        items = []
        items.append({
            'item': 'CSR Programs',
            'done': programs_modified,
            'detail': 'Modified' if programs_modified else 'No changes',
        })
        if challenges_available > 0:
            done = challenges_submitted >= challenges_available
            items.append({
                'item': 'Challenge Responses',
                'done': done,
                'detail': f'{challenges_submitted}/{challenges_available} submitted',
            })
            if not done:
                all_done = False
        if dilemmas_available > 0:
            done = ethics_submitted > 0
            items.append({
                'item': 'Ethical Dilemma',
                'done': done,
                'detail': 'Submitted' if done else 'Pending',
            })
            if not done:
                all_done = False

        overall = 'Ready' if all_done else ('Partial' if any(i['done'] for i in items) else 'No Activity')

        return {
            'team_id': team_id,
            'round_id': round_obj.round_id,
            'round_number': round_obj.round_number,
            'decisions_locked': round_obj.decisions_locked,
            'deadline': round_obj.deadline.isoformat() if round_obj.deadline else None,
            'items': items,
            'overall': overall,
        }


class SendReminderView(APIView):
    """POST /api/rounds/<round_id>/send-reminder/ — send system reminder to incomplete teams."""
    permission_classes = [IsInstructor]

    def post(self, request, round_id):
        from core.models.messaging import Message

        try:
            r = Round.objects.get(round_id=round_id)
        except Round.DoesNotExist:
            return Response({'error': 'Round not found.'}, status=status.HTTP_404_NOT_FOUND)

        instance_id = request.data.get('instance_id')
        if not instance_id:
            return Response({'error': 'instance_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        inst_filter = {'instance_id': int(instance_id)}
        teams = Team.objects.filter(**inst_filter)

        sent = 0
        for team in teams:
            status_view = DecisionStatusView()
            ts = status_view._team_status(team.team_id, r, inst_filter)
            if ts['overall'] != 'Ready':
                pending = [i['item'] for i in ts['items'] if not i['done']]
                content = (
                    f"Reminder: Round {r.round_number} decisions "
                    f"{'lock at ' + r.deadline.strftime('%b %d at %I:%M %p') if r.deadline else 'are due soon'}. "
                    f"Pending: {', '.join(pending) if pending else 'review your decisions'}."
                )
                try:
                    Message.objects.create(
                        team_id=team.team_id,
                        sender_name='System',
                        content=content,
                        round_id=r.round_id,
                        instance_id=int(instance_id),
                    )
                    sent += 1
                except Exception:
                    pass

        return Response({'sent': sent, 'round_id': r.round_id})
