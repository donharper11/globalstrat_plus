import csv
import io
import hashlib
import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.permissions import IsInstructor, IsInstructorOrReadOnly
from core.services.cohort_caps import (
    section_for_team, section_for_user, team_capacity_error)
from core.services.cohort_scope import (
    CohortOwnershipRefused, ownership_refusal, ownership_refusal_payload,
    record_refused_mutation)
from core.services.lifecycle import request_id_for
from core.utils.auth_context import get_request_role
from core.utils.cohort_messages import cohort_message, language_for_request
from core.utils.operator_messages import operator_refusal
from core.utils.participant_messages import participant_refusal
from core.views.mixins import InstanceScopedMixin
from core.models import (
    Team, User, Round, SimulationState,
    SimulationSettings, SimulationParameters, )
from core.serializers import (
    TeamSerializer, RoundSerializer,
    SimulationStateSerializer, SimulationSettingsSerializer,
    SimulationParametersSerializer, DashboardSerializer,
    UserSerializer, UserWriteSerializer,
)


logger = logging.getLogger(__name__)

STAFF_ONLY_CODE = 'staff_account_admin_only'


class TeamViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only, deliberately.

    This was a full `ModelViewSet` over `TeamSerializer`, whose fields are
    `'__all__'`: any instructor account could PATCH any team's cash, equity,
    performance index or participation status -- a rival cohort's included --
    with no lock, no reason and no audit row. Nothing in the product wrote
    through it. Every sanctioned team write has a guarded route of its own
    (team-management, team-config, instructor/teams/<id>/participation), so
    the write half is removed rather than scoped: a scoped version would still
    let an instructor edit their own teams' balance sheets behind the
    lifecycle boundary's back.
    """
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [IsInstructorOrReadOnly]


def _is_student_role(role):
    return (role or '').strip().lower() == 'student'


class UserViewSet(viewsets.ModelViewSet):
    """Accounts. An admin administers everyone; an instructor, their students.

    The viewset checked a role and nothing else, and its write serializer
    writes `role` and `password`. Driven with an instructor token: PATCH your
    own role to admin; POST a new admin with a password you chose; set another
    instructor's password; rename and re-password another cohort's student.

    For a caller who is not an admin:

    * the queryset is the students they may administer -- the same
      `_visible_users_qs` rule the student-accounts screen has always used
      (their courses, plus the unowned shared pilot cohort), and never an
      instructor or admin account. Anything else is a 404, as it is there;
    * `role` may only be Student, on create, update and bulk upload;
    * a team may only be assigned inside a cohort they may access.
    """
    # No select_related: `team_id` is an integer column, not a relation.
    queryset = User.objects.all()
    permission_classes = [IsInstructor]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return UserWriteSerializer
        return UserSerializer

    def _caller_is_admin(self):
        return (get_request_role(self.request) or '').lower() == 'admin'

    def _staff_only_payload(self):
        """The refusal, recorded: an instructor reaching for a staff role is
        exactly the attempt an investigator will want to find."""
        request_id = record_refused_mutation(
            self.request,
            'Instructor attempted to create or change a staff account')
        return {
            'error': cohort_message(
                STAFF_ONLY_CODE, language=language_for_request(self.request)),
            'code': STAFF_ONLY_CODE,
            'request_id': request_id,
        }

    def _refuse_unsafe_write(self, validated_data):
        """Role and team, the two fields that reach beyond the account."""
        if self._caller_is_admin():
            return
        if 'role' in validated_data and not _is_student_role(
                validated_data['role']):
            raise CohortOwnershipRefused(self._staff_only_payload())
        team_id = validated_data.get('team_id')
        if team_id is not None:
            refused = ownership_refusal_payload(
                self.request, section=section_for_team(team_id))
            if refused:
                raise CohortOwnershipRefused(refused)

    def perform_create(self, serializer):
        self._refuse_unsafe_write(serializer.validated_data)
        if not self._caller_is_admin():
            # An omitted role must not fall through to a model default.
            serializer.save(role='Student')
            return
        serializer.save()

    def perform_update(self, serializer):
        self._refuse_unsafe_write(serializer.validated_data)
        serializer.save()

    def get_queryset(self):
        qs = super().get_queryset()
        if not self._caller_is_admin():
            from core.views.instructor_accounts import _visible_users_qs
            visible = _visible_users_qs(self.request).values('user_id')
            qs = qs.filter(user_id__in=visible, role__iexact='student')
        role = self.request.query_params.get('role')
        team_id = self.request.query_params.get('team_id')
        if role:
            qs = qs.filter(role__iexact=role)
        if team_id:
            qs = qs.filter(team_id=team_id)
        return qs

    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        """Accept CSV text with columns: username, role, team_id, password.
        Create users in bulk and return created count plus any errors."""
        csv_text = request.data.get('csv', '')
        if not csv_text:
            return Response(operator_refusal(request, 'accounts_csv_empty'),
                            status=status.HTTP_400_BAD_REQUEST)

        rows = list(csv.DictReader(io.StringIO(csv_text)))
        created = 0
        errors = []

        # A row that seats an account on another instructor's team refuses the
        # whole upload, before any account is created.
        if not self._caller_is_admin():
            for row in rows:
                raw_team = (row.get('team_id') or '').strip()
                if raw_team.isdigit():
                    refused = ownership_refusal(
                        request, section=section_for_team(int(raw_team)))
                    if refused:
                        return refused

        for row_num, row in enumerate(rows, start=2):
            username = (row.get('username') or '').strip()
            if not username:
                errors.append({'row': row_num, **operator_refusal(
                    request, 'accounts_row_missing_username')})
                continue

            role = (row.get('role') or 'Student').strip()
            if not self._caller_is_admin() and not _is_student_role(role):
                errors.append({'row': row_num, **{
                    key: value
                    for key, value in self._staff_only_payload().items()
                    if key != 'request_id'}})
                continue
            team_id = (row.get('team_id') or '').strip() or None
            password = (row.get('password') or '').strip()

            if team_id:
                try:
                    team_id = int(team_id)
                except ValueError:
                    errors.append({'row': row_num, **operator_refusal(
                        request, 'accounts_row_invalid_team', value=team_id)})
                    continue

            password_hash = ''
            if password:
                password_hash = hashlib.sha256(password.encode()).hexdigest()

            try:
                if team_id:
                    over = team_capacity_error(
                        section_for_team(team_id), team_id,
                        language=language_for_request(request))
                    if over:
                        errors.append({'row': row_num, 'error': over})
                        continue
                User.objects.create(
                    username=username,
                    role=role,
                    team_id=team_id,
                    password_hash=password_hash,
                )
                created += 1
            except Exception:
                request_id = request_id_for(request)
                logger.exception(
                    'Account bulk upload failed at row %s (request_id=%s)',
                    row_num, request_id)
                errors.append({
                    'row': row_num,
                    'error': cohort_message(
                        'account_row_failed',
                        language=language_for_request(request),
                        reference=request_id),
                    'code': 'account_row_failed',
                })

        return Response({'created': created, 'errors': errors},
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='assign-team')
    def assign_team(self, request, pk=None):
        """Assign a user to a team. Expects {"team_id": <int|null>}."""
        user = self.get_object()
        team_id = request.data.get('team_id')

        if team_id is not None:
            try:
                team = Team.objects.get(pk=int(team_id))
            except (Team.DoesNotExist, ValueError, TypeError):
                return Response(operator_refusal(request, 'team_not_found'),
                                status=status.HTTP_404_NOT_FOUND)
            # `get_object` has already settled whose student this is; this
            # settles whose team.
            refused = ownership_refusal(
                request, section=section_for_team(team.pk))
            if refused:
                return refused
            # This route writes User.team_id, a second membership record the
            # roster surface does not write. Capping only the other one would
            # leave the cap trivially reachable from here (see cohort_caps).
            section = (section_for_user(user.user_id)
                       or section_for_team(team.pk))
            over = team_capacity_error(
                section, team.pk, joining_user_id=user.user_id,
                language=language_for_request(request), team_name=team.name)
            if over:
                return Response({'error': over, 'code': 'team_full'},
                                status=status.HTTP_400_BAD_REQUEST)
            user.team_id = team.pk
        else:
            user.team_id = None

        user.save()
        serializer = UserSerializer(user)
        return Response(serializer.data)


class RoundViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Round.objects.all()
    serializer_class = RoundSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        game_id = self.request.query_params.get('game_id')
        if game_id:
            qs = qs.filter(game_id=game_id)
        return qs


class SimulationStateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SimulationState.objects.all()
    serializer_class = SimulationStateSerializer


class SimulationSettingsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SimulationSettings.objects.all()
    serializer_class = SimulationSettingsSerializer


class SimulationParametersViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SimulationParameters.objects.all()
    serializer_class = SimulationParametersSerializer


class DashboardViewSet(viewsets.ViewSet):
    """Aggregated dashboard data for a team."""

    def _get_instance_id(self, request):
        instance_id = request.META.get('HTTP_X_INSTANCE_ID') or \
            request.query_params.get('instance_id')
        if instance_id:
            try:
                return int(instance_id)
            except (ValueError, TypeError):
                pass
        return None

    def list(self, request):
        team_id = request.query_params.get('team_id')
        if not team_id:
            return Response(
                participant_refusal(request, 'request_incomplete'), status=400)

        try:
            team_id = int(team_id)
        except ValueError:
            return Response(
                participant_refusal(request, 'request_incomplete'), status=400)

        instance_id = self._get_instance_id(request)

        from core.models import (
            Team, SimulationState, TeamIncomeStatement,
            Program, Score, TeamPerformance,
        )

        try:
            team = Team.objects.get(pk=team_id)
        except Team.DoesNotExist:
            return Response(
                participant_refusal(request, 'team_not_found'), status=404)

        # Instance filter dict — reused across queries
        inst_filter = {'instance_id': instance_id} if instance_id else {}

        # Get current round
        sim_state = SimulationState.objects.filter(**inst_filter).first()
        current_round_id = sim_state.current_round_id if sim_state else None

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # ESGScorecard model has been removed.
        esg_scores = {
            'environmental': 0,
            'social': 0,
            'governance': 0,
        }

        # Financial summary — latest available income statement
        income = TeamIncomeStatement.objects.filter(
            team_id=team_id, **inst_filter
        ).order_by('-round_id').first()
        gross_margin = (float(income.revenue) if income and income.revenue else 0) - \
                       (float(income.cogs) if income and income.cogs else 0)
        financial_summary = {
            'revenue': float(income.revenue) if income and income.revenue else 0,
            'cogs': float(income.cogs) if income and income.cogs else 0,
            'gross_margin': gross_margin,
            'csr_operating_costs': float(income.operating_costs) if income and income.operating_costs else 0,
            'net_profit': float(income.net_profit) if income and income.net_profit else 0,
        }

        # TODO: GlobalStrat — update to use new scenario models (CC-3)
        # Segment/Scenario models removed; return raw scores without names
        stakeholder_scores = []
        scores_qs = Score.objects.filter(
            team_id=team_id, **inst_filter
        ).order_by('-round_id')
        if scores_qs.exists():
            latest_round = scores_qs.first().round_id
            raw_scores = list(
                scores_qs.filter(round_id=latest_round).values('segment_id', 'score')
            )
            for s in raw_scores:
                s['segment_name'] = f"Segment {s['segment_id']}"
                s['economy_id'] = None
                s['economy_name'] = 'Unknown'
            stakeholder_scores = raw_scores

        # Total programs
        total_programs = Program.objects.filter(team_id=team_id).count()

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # SDG coverage — FeatureSdgMapping (core.models.frameworks) has been removed.
        sdg_count = 0

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Scope 1/2/3 scores — FeatureScopeMapping, EmissionScope (core.models.frameworks) removed.
        scope_scores = {}

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # Compliance status — TeamFrameworkAdoption, TeamComplianceCheck (core.models.frameworks) removed.
        compliance_status = 'no_framework'

        # TODO: GlobalStrat — replace with new engine logic (CC-5/CC-6)
        # International framework compliance — core.models.intl_frameworks removed.
        intl_framework_status = []

        # Leaderboard rank — scoped to instance
        leaderboard_rank = None
        all_perf = TeamPerformance.objects.filter(**inst_filter).order_by('-total_score')
        for idx, perf in enumerate(all_perf, 1):
            if perf.team_id == team_id:
                leaderboard_rank = idx
                break

        # Round deadline / lock info
        current_round_obj = Round.objects.filter(
            round_id=current_round_id,
        ).first() if current_round_id else None
        deadline = current_round_obj.deadline if current_round_obj else None
        decisions_locked = current_round_obj.decisions_locked if current_round_obj else False
        lock_reason = current_round_obj.lock_reason if current_round_obj else None

        data = {
            'team_id': team_id,
            'team_name': team.team_name,
            'current_round': current_round_id or 0,
            'esg_scores': esg_scores,
            'financial_summary': financial_summary,
            'stakeholder_scores': stakeholder_scores,
            'leaderboard_rank': leaderboard_rank,
            'total_programs': total_programs,
            'sdg_count': sdg_count,
            'scope_scores': scope_scores,
            'compliance_status': compliance_status,
            'intl_framework_status': intl_framework_status,
            'deadline': deadline,
            'decisions_locked': decisions_locked,
            'lock_reason': lock_reason,
        }

        serializer = DashboardSerializer(data)
        return Response(serializer.data)
