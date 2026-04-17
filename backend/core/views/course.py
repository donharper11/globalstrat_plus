"""
Course / Section / Roster / Team / Simulation-Instance management views.

All models use ``managed = False`` (PostgreSQL schema already exists).
Views are thin wrappers; heavy logic stays in services/.
"""

import csv
import hashlib
import io
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
from core.serializers.course import (
    CourseSerializer, CourseListSerializer,
    SectionSerializer, SectionDetailSerializer,
    SimulationInstanceSerializer, EnrollmentSerializer,
    RosterUploadSerializer, TeamGenerateSerializer,
)

# Futuristic company names used when auto-generating teams.
COMPANY_NAMES = [
    'Nexus Dynamics', 'Aether Industries', 'Solaris Corp',
    'Zenith Innovations', 'Orion Collective', 'Helios Ventures',
    'Vantage Systems', 'Prism Technologies', 'Astra Enterprises',
    'Vertex Global', 'Nova Synthetica', 'Quantum Forge',
    'Eclipse Digital', 'Cipher Networks', 'Parallax Labs',
    'Meridian Works', 'Stratos Group', 'Axiom Devices',
    'Pulse Robotics', 'Titan Microtech', 'Lumen Industries',
    'Catalyst Corp', 'Helix Foundry', 'Aegis Solutions',
    'Photon Systems', 'Nebula Dynamics', 'Tesseract Inc',
    'Arc Innovations', 'Cobalt Ventures', 'Apex Synergies',
]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _generate_password(length=10):
    """Generate a random alphanumeric temporary password."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def _hash_password(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


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
            qs = qs.annotate(section_count=Count('sections'))
        return qs

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

    @transaction.atomic
    def perform_create(self, serializer):
        """Create the section, then auto-create its SimulationInstance."""
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
                {'error': 'section_id query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
                {'error': f"Unknown action: '{action_type}'. Use 'upload' or 'add'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # ---- PUT: update enrollment / student details -------------------------

    def put(self, request):
        action_type = request.data.get('action', 'update')

        if action_type == 'update':
            enrollment_id = request.data.get('enrollment_id')
            if not enrollment_id:
                return Response(
                    {'error': 'enrollment_id is required.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                enrollment = Enrollment.objects.get(enrollment_id=enrollment_id)
            except Enrollment.DoesNotExist:
                return Response(
                    {'error': 'Enrollment not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Update the underlying User record
            user = User.objects.filter(user_id=enrollment.user_id).first()
            if not user:
                return Response(
                    {'error': 'User not found.'},
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
            {'error': f"Unknown action: '{action_type}'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---- DELETE: remove enrollment --------------------------------------

    def delete(self, request):
        enrollment_id = request.query_params.get('enrollment_id')
        if not enrollment_id:
            return Response(
                {'error': 'enrollment_id query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            enrollment = Enrollment.objects.get(enrollment_id=enrollment_id)
        except Enrollment.DoesNotExist:
            return Response(
                {'error': 'Enrollment not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        enrollment.delete()
        return Response(
            {'detail': 'Enrollment removed.'},
            status=status.HTTP_204_NO_CONTENT,
        )

    # ---- Internal: CSV upload -------------------------------------------

    def _handle_csv_upload(self, request):
        section_id = request.data.get('section_id')

        if not section_id:
            return Response(
                {'error': 'section_id is required for CSV upload.'},
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
                {'error': 'No CSV data provided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate section exists
        try:
            Section.objects.get(section_id=section_id)
        except Section.DoesNotExist:
            return Response(
                {'error': 'Section not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

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
                    'error': 'Row must have at least student_id or email.',
                })
                continue

            try:
                user = self._find_or_create_user(
                    student_id_val, display_name, email,
                )
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
            except Exception as e:
                errors.append({'row': row_num, 'error': str(e)})

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
                {'error': 'section_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not student_id_val and not email:
            return Response(
                {'error': 'At least student_id or email is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            Section.objects.get(section_id=section_id)
        except Section.DoesNotExist:
            return Response(
                {'error': 'Section not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            user = self._find_or_create_user(
                student_id_val, display_name, email,
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
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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

class TeamManagementView(APIView):
    """
    Manage teams within a section.

    GET    ?section_id=<id>                      — list teams with members
    POST   {action: "generate", section_id, method, team_name_prefix}
    PUT    {action: "assign", assignments: [{user_id, team_id}, ...]}
    PUT    {action: "rename", team_id, team_name}
    """
    permission_classes = [IsInstructor]

    # ---- GET: list teams with members -----------------------------------

    def get(self, request):
        section_id = request.query_params.get('section_id')
        if not section_id:
            return Response(
                {'error': 'section_id query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        teams = Team.objects.filter(section_id=section_id)
        result = []
        for team in teams:
            enrollments = Enrollment.objects.filter(
                section_id=section_id, team_id=team.team_id, is_active=True,
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
                'team_id': team.team_id,
                'team_name': team.team_name,
                'instance_id': team.instance_id,
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

    # ---- POST: generate teams -------------------------------------------

    @transaction.atomic
    def post(self, request):
        section_id = request.data.get('section_id')
        method = request.data.get('method', 'random')
        team_name_prefix = request.data.get('team_name_prefix', 'Team')

        if not section_id:
            return Response(
                {'error': 'section_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            section = Section.objects.get(section_id=section_id)
        except Section.DoesNotExist:
            return Response(
                {'error': 'Section not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get the simulation instance for this section
        sim_instance = SimulationInstance.objects.filter(
            section_id=section_id,
        ).first()
        instance_id = sim_instance.instance_id if sim_instance else None

        # Get active enrolled students
        enrollments = list(
            Enrollment.objects.filter(section_id=section_id, is_active=True)
        )
        student_count = len(enrollments)
        if student_count == 0:
            return Response(
                {'error': 'No enrolled students in this section.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Calculate optimal team count
        team_size_min = section.team_size_min or 3
        team_size_max = section.team_size_max or 5
        max_teams = section.max_teams or 8

        # Ideal: as many teams as possible within min/max bounds
        ideal_size = (team_size_min + team_size_max) / 2.0
        team_count = round(student_count / ideal_size)
        # Clamp so that per-team size stays within bounds
        team_count = max(team_count, math.ceil(student_count / team_size_max))
        team_count = min(team_count, math.floor(student_count / team_size_min))
        # Clamp to max_teams
        team_count = max(team_count, 1)
        team_count = min(team_count, max_teams)

        # Sort or shuffle students depending on method
        if method == 'alphabetical':
            # Sort by display_name (or username fallback)
            def _sort_key(enr):
                user = User.objects.filter(user_id=enr.user_id).first()
                if user:
                    return (user.display_name or user.username or '').lower()
                return ''
            enrollments.sort(key=_sort_key)
        else:
            random.shuffle(enrollments)

        # Create team records with futuristic company names
        created_teams = []
        available_names = list(COMPANY_NAMES)
        random.shuffle(available_names)
        for i in range(team_count):
            if i < len(available_names):
                team_name = available_names[i]
            else:
                team_name = f"{team_name_prefix} {i + 1}"

            team = Team.objects.create(
                team_name=team_name,
                instance_id=instance_id,
                section_id=section_id,
                created_at=timezone.now(),
            )
            created_teams.append(team)

        # Distribute students evenly across teams (round-robin) — unless 'empty'
        if method != 'empty':
            for idx, enrollment in enumerate(enrollments):
                assigned_team = created_teams[idx % team_count]
                enrollment.team_id = assigned_team.team_id
                enrollment.save()

        # Build response
        teams_data = []
        for team in created_teams:
            member_count = Enrollment.objects.filter(
                section_id=section_id, team_id=team.team_id, is_active=True,
            ).count()
            teams_data.append({
                'team_id': team.team_id,
                'team_name': team.team_name,
                'member_count': member_count,
            })

        return Response({
            'section_id': int(section_id),
            'teams_created': len(created_teams),
            'student_count': student_count,
            'teams': teams_data,
        }, status=status.HTTP_201_CREATED)

    # ---- PUT: assign or rename ------------------------------------------

    def put(self, request):
        action_type = request.data.get('action')

        if action_type == 'assign':
            return self._handle_assign(request)
        elif action_type == 'rename':
            return self._handle_rename(request)
        else:
            return Response(
                {'error': f"Unknown action: '{action_type}'. Use 'assign' or 'rename'."},
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
                {'error': 'assignments must be a non-empty list of {user_id, team_id}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = 0
        errors = []

        for item in assignments:
            user_id = item.get('user_id')
            team_id = item.get('team_id')

            if user_id is None:
                errors.append({'item': item, 'error': 'Missing user_id.'})
                continue

            enrollment = Enrollment.objects.filter(
                user_id=user_id, is_active=True,
            ).first()
            if not enrollment:
                errors.append({
                    'item': item,
                    'error': f'No active enrollment for user_id={user_id}.',
                })
                continue

            # Validate team exists (team_id can be None to un-assign)
            if team_id is not None:
                if not Team.objects.filter(id=team_id).exists():
                    errors.append({
                        'item': item,
                        'error': f'Team {team_id} not found.',
                    })
                    continue

            enrollment.team_id = team_id
            enrollment.save()
            updated += 1

        return Response({'updated': updated, 'errors': errors})

    # ---- Internal: rename team ------------------------------------------

    @staticmethod
    def _handle_rename(request):
        team_id = request.data.get('team_id')
        team_name = request.data.get('team_name')

        if not team_id or not team_name:
            return Response(
                {'error': 'team_id and team_name are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            team = Team.objects.get(team_id=team_id)
        except Team.DoesNotExist:
            return Response(
                {'error': 'Team not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        team.team_name = team_name
        team.save()
        return Response({
            'team_id': team.team_id,
            'team_name': team.team_name,
        })


# ===================================================================
# SimulationControlView
# ===================================================================

class SimulationControlView(APIView):
    """
    Control the lifecycle of a simulation instance.

    POST {action: "start",   instance_id}
    POST {action: "advance", instance_id}
    POST {action: "pause",   instance_id}
    POST {action: "resume",  instance_id}
    POST {action: "reset",   instance_id, confirm: true}
    """
    permission_classes = [IsInstructor]

    def post(self, request):
        action_type = request.data.get('action')
        instance_id = request.data.get('instance_id')

        if not instance_id:
            return Response(
                {'error': 'instance_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            instance = SimulationInstance.objects.get(instance_id=instance_id)
        except SimulationInstance.DoesNotExist:
            return Response(
                {'error': 'Simulation instance not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        dispatch = {
            'start': self._start,
            'advance': self._advance,
            'pause': self._pause,
            'resume': self._resume,
            'reset': self._reset,
        }

        handler = dispatch.get(action_type)
        if handler is None:
            return Response(
                {'error': f"Unknown action: '{action_type}'. "
                          "Use 'start', 'advance', 'pause', 'resume', or 'reset'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return handler(request, instance)

    # ---- start ----------------------------------------------------------

    @staticmethod
    def _start(request, instance):
        if instance.status == 'active':
            return Response(
                {'error': 'Simulation is already active.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.status = 'active'
        instance.current_round = 1
        instance.started_at = timezone.now()
        instance.save()

        # Ensure a SimulationState row exists for this instance
        state, _created = SimulationState.objects.get_or_create(
            instance_id=instance.instance_id,
            defaults={
                'current_round_id': 1,
                'status': 'active',
                'last_updated': timezone.now(),
            },
        )
        if not _created:
            state.status = 'active'
            state.current_round_id = 1
            state.last_updated = timezone.now()
            state.save()

        return Response({
            'instance_id': instance.instance_id,
            'status': instance.status,
            'current_round': instance.current_round,
            'started_at': instance.started_at.isoformat() if instance.started_at else None,
        })

    # ---- advance --------------------------------------------------------

    @staticmethod
    def _advance(request, instance):
        if instance.status != 'active':
            return Response(
                {'error': 'Simulation must be active to advance. '
                          f'Current status: {instance.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find the SimulationState for this instance
        state = SimulationState.objects.filter(
            instance_id=instance.instance_id,
        ).first()
        if not state:
            return Response(
                {'error': 'No SimulationState found for this instance.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        from core.services.round_engine import advance_round
        try:
            result = advance_round(state.state_id)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Sync instance current_round from the state
        state.refresh_from_db()
        if state.current_round_id:
            from core.models import Round
            next_round = Round.objects.filter(
                round_id=state.current_round_id,
            ).first()
            if next_round:
                instance.current_round = next_round.round_number
                instance.save()

        if state.status == 'completed':
            instance.status = 'completed'
            instance.completed_at = timezone.now()
            instance.save()

        return Response(result)

    # ---- pause ----------------------------------------------------------

    @staticmethod
    def _pause(request, instance):
        if instance.status != 'active':
            return Response(
                {'error': 'Can only pause an active simulation.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.status = 'paused'
        instance.save()

        # Also pause the SimulationState
        SimulationState.objects.filter(
            instance_id=instance.instance_id,
        ).update(status='paused', last_updated=timezone.now())

        return Response({
            'instance_id': instance.instance_id,
            'status': instance.status,
        })

    # ---- resume ---------------------------------------------------------

    @staticmethod
    def _resume(request, instance):
        if instance.status != 'paused':
            return Response(
                {'error': 'Can only resume a paused simulation.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.status = 'active'
        instance.save()

        SimulationState.objects.filter(
            instance_id=instance.instance_id,
        ).update(status='active', last_updated=timezone.now())

        return Response({
            'instance_id': instance.instance_id,
            'status': instance.status,
        })

    # ---- reset ----------------------------------------------------------

    @staticmethod
    def _reset(request, instance):
        confirm = request.data.get('confirm', False)
        if not confirm:
            return Response(
                {'error': 'You must pass confirm=true to reset a simulation. '
                          'This will delete all game state for this instance.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reset_competitors = request.data.get('reset_competitors', True)
        inst_id = instance.instance_id

        from django.db import connection
        from core.management.commands.reset_simulation import (
            FULL_TRUNCATE_TABLES, CONDITIONAL_DELETE_TABLES,
        )

        deleted_counts = {}

        with connection.cursor() as cursor:
            # ── 1. Delete non-baseline programs (cascade to children) ──
            cursor.execute(
                "SELECT COUNT(*) FROM programs WHERE round_launched != 11"
            )
            cnt = cursor.fetchone()[0]
            if cnt > 0:
                cursor.execute("DELETE FROM programs WHERE round_launched != 11")
            deleted_counts['programs (non-baseline)'] = cnt

            # ── 1b. Reset R&D fields on surviving baseline programs ──
            cursor.execute(
                "UPDATE programs SET development_status = 'ready', "
                "development_rounds_total = 0, "
                "development_rounds_remaining = 0, "
                "r_and_d_investment = 0, "
                "development_started_round = NULL "
                "WHERE round_launched = 11"
            )

            # ── 2. Conditional deletes (keep round 0 baseline) ─────
            for table, where in CONDITIONAL_DELETE_TABLES:
                try:
                    cursor.execute(
                        f'SELECT COUNT(*) FROM "{table}" WHERE {where}'
                    )
                    cnt = cursor.fetchone()[0]
                    if cnt > 0:
                        cursor.execute(
                            f'DELETE FROM "{table}" WHERE {where}'
                        )
                    deleted_counts[table] = cnt
                except Exception:
                    connection.ensure_connection()

            # ── 3. Full truncates ──────────────────────────────────
            for table in FULL_TRUNCATE_TABLES:
                try:
                    cursor.execute(f'TRUNCATE TABLE "{table}" CASCADE')
                    deleted_counts[table] = 'truncated'
                except Exception:
                    connection.ensure_connection()

            # ── 4. Persona messages ────────────────────────────────
            try:
                cursor.execute(
                    "DELETE FROM messages WHERE instance_id IS NOT NULL"
                )
                deleted_counts['messages (persona)'] = cursor.rowcount
            except Exception:
                connection.ensure_connection()

            # ── 5. team_performance reset to baseline ──────────────
            try:
                cursor.execute(
                    "UPDATE team_performance SET "
                    "total_score = 0, "
                    "average_stakeholder_satisfaction = 0.10, "
                    "ethical_alignment = 0, "
                    "updated_at = NOW()"
                )
            except Exception:
                connection.ensure_connection()

            # ── 6. Reset simulation_state ──────────────────────────
            try:
                cursor.execute(
                    "UPDATE simulation_state SET current_round_id = 1, "
                    "status = 'active', last_updated = NOW()"
                )
            except Exception:
                connection.ensure_connection()

            # ── 7. Reset simulation_instance ───────────────────────
            try:
                cursor.execute(
                    "UPDATE simulation_instance SET current_round = 0, "
                    "status = 'setup' "
                    "WHERE instance_id = %s",
                    [inst_id],
                )
            except Exception:
                connection.ensure_connection()

            # ── 8. Reset round statuses ────────────────────────────
            try:
                cursor.execute(
                    "UPDATE rounds SET status = 'pending', "
                    "start_date = NULL, end_date = NULL, "
                    "start_time = NULL, end_time = NULL, "
                    "deadline = NULL, decisions_locked = FALSE, "
                    "lock_reason = NULL"
                )
                cursor.execute(
                    "UPDATE rounds SET status = 'completed' "
                    "WHERE round_number = 0"
                )
                cursor.execute(
                    "UPDATE rounds SET status = 'active' "
                    "WHERE round_number = 1"
                )
            except Exception:
                connection.ensure_connection()

            # ── 9. Reset challenge statuses ────────────────────────
            try:
                cursor.execute(
                    "UPDATE challenges SET status = 'active', "
                    "carryover_round = NULL "
                    "WHERE round_id IS NOT NULL"
                )
            except Exception:
                connection.ensure_connection()

            # ── 10. Optionally reset competitor baselines ──────────
            if reset_competitors:
                COMPETITOR_BASELINES = [
                    (3, '171.77', '{"Social": 19, "Governance": 10, "Environmental": 72}'),
                    (4, '124.43', '{"Social": 10, "Governance": 74, "Environmental": 17}'),
                    (5, '280.32', '{"Social": 71, "Governance": 15, "Environmental": 15}'),
                    (6, '335.83', '{"Social": 30, "Governance": 30, "Environmental": 40}'),
                ]
                try:
                    for cid, score, priority in COMPETITOR_BASELINES:
                        cursor.execute(
                            "UPDATE competitors SET total_esg_score = %s, "
                            "esg_priority = %s::jsonb "
                            "WHERE competitor_id = %s",
                            [score, priority, cid],
                        )
                except Exception:
                    connection.ensure_connection()

        # Reset instance model fields
        instance.current_round = 0
        instance.status = 'setup'
        instance.started_at = None
        instance.completed_at = None
        instance.save()

        return Response({
            'instance_id': inst_id,
            'status': 'setup',
            'current_round': 0,
            'detail': 'Full simulation reset complete. All game state cleared, '
                      'round statuses restored, baseline data preserved.',
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
            return Response({'error': 'Game not found.'}, status=status.HTTP_404_NOT_FOUND)

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

    def post(self, request, game_id):
        import datetime as dt
        from django.utils.dateparse import parse_datetime
        from core.models.core import Game

        try:
            game = Game.objects.get(pk=game_id)
        except Game.DoesNotExist:
            return Response({'error': 'Game not found.'}, status=status.HTTP_404_NOT_FOUND)

        rounds_data = request.data.get('rounds', [])
        if not rounds_data:
            return Response({'error': 'rounds list is required.'}, status=status.HTTP_400_BAD_REQUEST)

        updated = 0
        errors = []
        for item in rounds_data:
            round_id = item.get('round_id')
            try:
                r = Round.objects.get(pk=round_id, game=game)
            except Round.DoesNotExist:
                errors.append(f"Round {round_id} not found in game {game_id}.")
                continue

            opened_at = item.get('opened_at')
            deadline_val = item.get('deadline')

            if opened_at:
                parsed = parse_datetime(opened_at)
                if parsed is None:
                    errors.append(f"Invalid opened_at for round {round_id}.")
                    continue
                r.opened_at = parsed

            if deadline_val:
                parsed = parse_datetime(deadline_val)
                if parsed is None:
                    errors.append(f"Invalid deadline for round {round_id}.")
                    continue
                r.deadline = parsed

            r.save()
            updated += 1

        resp = {'updated': updated, 'game_id': game_id}
        if errors:
            resp['errors'] = errors
        return Response(resp)


# RoundScheduleView
# ===================================================================

class RoundScheduleView(APIView):
    """
    Manage round scheduling for a simulation instance.

    GET  ?instance_id=<id>  — list all rounds with their schedule
    POST {instance_id, rounds: [{round_id, start_date, start_time, end_date, end_time}, ...]}
         — bulk-update round schedule
    PUT  {instance_id, auto_advance: true/false}
         — toggle auto-advance for the simulation instance
    """
    permission_classes = [IsInstructor]

    def get(self, request):
        instance_id = request.query_params.get('instance_id')
        if not instance_id:
            return Response(
                {'error': 'instance_id query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            instance = SimulationInstance.objects.get(instance_id=instance_id)
        except SimulationInstance.DoesNotExist:
            return Response(
                {'error': 'Simulation instance not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Find the SimulationState to get game_id
        state = SimulationState.objects.filter(
            instance_id=instance.instance_id,
        ).first()

        # Get rounds for this game
        rounds_qs = Round.objects.all().order_by('round_number')
        if state and state.current_round_id:
            current_round = Round.objects.filter(
                round_id=state.current_round_id,
            ).first()
            if current_round and current_round.game_id is not None:
                rounds_qs = rounds_qs.filter(game_id=current_round.game_id)

        # Compute display status for each round based on position and dates
        import datetime as dt
        now = timezone.now()
        today = now.date()
        current_time = now.time()
        active_round_number = instance.current_round or 0
        sim_status = instance.status  # setup, active, paused, completed

        rounds_data = []
        for r in rounds_qs:
            # Derive display_status from round position + dates
            if sim_status in ('setup',) or active_round_number == 0:
                # Simulation hasn't started — all rounds are pending
                display_status = 'Pending'
            elif r.round_number < active_round_number:
                display_status = 'Completed'
            elif r.round_number == active_round_number:
                if sim_status == 'completed':
                    display_status = 'Completed'
                elif sim_status == 'paused':
                    display_status = 'Paused'
                else:
                    display_status = 'In Progress'
            else:
                # Future round — check if it has scheduled dates
                if r.start_date:
                    start_dt = dt.datetime.combine(
                        r.start_date,
                        r.start_time or dt.time(0, 0),
                    )
                    if timezone.is_aware(now):
                        start_dt = timezone.make_aware(
                            start_dt, timezone.get_current_timezone()
                        )
                    if now >= start_dt:
                        display_status = 'In Progress'
                    else:
                        display_status = 'Pending'
                else:
                    display_status = 'Pending'

            rounds_data.append({
                'round_id': r.round_id,
                'round_number': r.round_number,
                'start_date': r.start_date.isoformat() if r.start_date else None,
                'start_time': r.start_time.isoformat() if r.start_time else None,
                'end_date': r.end_date.isoformat() if r.end_date else None,
                'end_time': r.end_time.isoformat() if r.end_time else None,
                'deadline': r.deadline.isoformat() if r.deadline else None,
                'decisions_locked': r.decisions_locked,
                'lock_reason': r.lock_reason,
                'auto_advance': r.auto_advance,
                'status': display_status,
            })

        return Response({
            'instance_id': instance.instance_id,
            'current_round': instance.current_round,
            'total_rounds': instance.total_rounds,
            'auto_advance': instance.auto_advance,
            'rounds': rounds_data,
        })

    def post(self, request):
        """Bulk-update round schedule."""
        instance_id = request.data.get('instance_id')
        rounds_updates = request.data.get('rounds', [])

        if not instance_id:
            return Response(
                {'error': 'instance_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            SimulationInstance.objects.get(instance_id=instance_id)
        except SimulationInstance.DoesNotExist:
            return Response(
                {'error': 'Simulation instance not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not rounds_updates or not isinstance(rounds_updates, list):
            return Response(
                {'error': 'rounds must be a non-empty list.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = 0
        errors = []

        for item in rounds_updates:
            round_id = item.get('round_id')
            if not round_id:
                errors.append({'item': item, 'error': 'Missing round_id.'})
                continue

            try:
                r = Round.objects.get(round_id=round_id)
            except Round.DoesNotExist:
                errors.append({'item': item, 'error': f'Round {round_id} not found.'})
                continue

            changed = False
            for field in ('start_date', 'end_date'):
                if field in item:
                    setattr(r, field, item[field] or None)
                    changed = True
            for field in ('start_time', 'end_time'):
                if field in item:
                    setattr(r, field, item[field] or None)
                    changed = True

            if changed:
                r.save()
                updated += 1

        return Response({
            'updated': updated,
            'errors': errors,
        })

    def put(self, request):
        """Toggle auto_advance on the simulation instance."""
        instance_id = request.data.get('instance_id')
        auto_advance = request.data.get('auto_advance')

        if not instance_id:
            return Response(
                {'error': 'instance_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if auto_advance is None:
            return Response(
                {'error': 'auto_advance is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            instance = SimulationInstance.objects.get(instance_id=instance_id)
        except SimulationInstance.DoesNotExist:
            return Response(
                {'error': 'Simulation instance not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        instance.auto_advance = bool(auto_advance)
        instance.save()

        return Response({
            'instance_id': instance.instance_id,
            'auto_advance': instance.auto_advance,
        })


class RoundLockView(APIView):
    """POST /api/rounds/<round_id>/lock/ — manually lock decisions."""
    permission_classes = [IsInstructor]

    def post(self, request, round_id):
        try:
            r = Round.objects.get(round_id=round_id)
        except Round.DoesNotExist:
            return Response({'error': 'Round not found.'}, status=status.HTTP_404_NOT_FOUND)

        r.decisions_locked = True
        r.lock_reason = 'instructor_locked'
        r.save()
        return Response({
            'round_id': r.round_id,
            'decisions_locked': True,
            'lock_reason': r.lock_reason,
        })


class RoundUnlockView(APIView):
    """POST /api/rounds/<round_id>/unlock/ — manually unlock decisions."""
    permission_classes = [IsInstructor]

    def post(self, request, round_id):
        try:
            r = Round.objects.get(round_id=round_id)
        except Round.DoesNotExist:
            return Response({'error': 'Round not found.'}, status=status.HTTP_404_NOT_FOUND)

        r.decisions_locked = False
        r.lock_reason = None
        r.save()
        return Response({
            'round_id': r.round_id,
            'decisions_locked': False,
            'lock_reason': None,
        })


class RoundExtendView(APIView):
    """POST /api/rounds/<round_id>/extend/ — extend deadline by N hours."""
    permission_classes = [IsInstructor]

    def post(self, request, round_id):
        import datetime as dt
        hours = request.data.get('hours', 0)
        try:
            hours = int(hours)
        except (ValueError, TypeError):
            return Response({'error': 'hours must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)
        if hours <= 0:
            return Response({'error': 'hours must be positive.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            r = Round.objects.get(round_id=round_id)
        except Round.DoesNotExist:
            return Response({'error': 'Round not found.'}, status=status.HTTP_404_NOT_FOUND)

        if r.deadline:
            r.deadline = r.deadline + dt.timedelta(hours=hours)
        else:
            r.deadline = timezone.now() + dt.timedelta(hours=hours)

        # Also extend end_date/end_time to stay consistent
        r.end_date = r.deadline.date()
        r.end_time = r.deadline.time()
        r.save()
        return Response({
            'round_id': r.round_id,
            'deadline': r.deadline.isoformat(),
        })


class RoundScheduleSetView(APIView):
    """PUT /api/rounds/<round_id>/schedule/ — set start time, deadline, auto-advance."""
    permission_classes = [IsInstructor]

    def put(self, request, round_id):
        import datetime as dt
        try:
            r = Round.objects.get(round_id=round_id)
        except Round.DoesNotExist:
            return Response({'error': 'Round not found.'}, status=status.HTTP_404_NOT_FOUND)

        start_datetime = request.data.get('start_datetime')
        deadline = request.data.get('deadline')
        auto_advance = request.data.get('auto_advance')

        if start_datetime:
            parsed = dt.datetime.fromisoformat(start_datetime)
            r.start_date = parsed.date()
            r.start_time = parsed.time()

        if deadline:
            parsed = dt.datetime.fromisoformat(deadline)
            r.deadline = parsed
            r.end_date = parsed.date()
            r.end_time = parsed.time()

        if auto_advance is not None:
            r.auto_advance = bool(auto_advance)

        r.save()
        return Response({
            'round_id': r.round_id,
            'start_date': r.start_date.isoformat() if r.start_date else None,
            'start_time': r.start_time.isoformat() if r.start_time else None,
            'deadline': r.deadline.isoformat() if r.deadline else None,
            'auto_advance': r.auto_advance,
        })


class BulkScheduleView(APIView):
    """POST /api/instances/<instance_id>/bulk-schedule/ — schedule all remaining rounds."""
    permission_classes = [IsInstructor]

    def post(self, request, instance_id):
        import datetime as dt

        try:
            instance = SimulationInstance.objects.get(instance_id=instance_id)
        except SimulationInstance.DoesNotExist:
            return Response({'error': 'Instance not found.'}, status=status.HTTP_404_NOT_FOUND)

        start_datetime = request.data.get('start_datetime')
        duration_hours = request.data.get('duration_hours', 48)
        grace_period_minutes = request.data.get('grace_period_minutes', 15)

        if not start_datetime:
            return Response({'error': 'start_datetime is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            current_start = dt.datetime.fromisoformat(start_datetime)
            duration_hours = int(duration_hours)
            grace_period_minutes = int(grace_period_minutes)
        except (ValueError, TypeError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        state = SimulationState.objects.filter(instance_id=instance_id).first()
        current_round_num = instance.current_round or 0

        # Get rounds for this game, ordered by round_number
        rounds_qs = Round.objects.all().order_by('round_number')
        if state and state.current_round_id:
            current_round = Round.objects.filter(round_id=state.current_round_id).first()
            if current_round and current_round.game_id is not None:
                rounds_qs = rounds_qs.filter(game_id=current_round.game_id)

        scheduled = 0
        for r in rounds_qs:
            if r.round_number <= current_round_num:
                continue
            r.start_date = current_start.date()
            r.start_time = current_start.time()
            deadline = current_start + dt.timedelta(hours=duration_hours)
            r.deadline = deadline
            r.end_date = deadline.date()
            r.end_time = deadline.time()
            r.save()
            scheduled += 1
            current_start = deadline + dt.timedelta(minutes=grace_period_minutes)

        return Response({
            'scheduled': scheduled,
            'instance_id': instance_id,
        })


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
