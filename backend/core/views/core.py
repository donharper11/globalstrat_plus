import csv
import io
import hashlib

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.permissions import IsInstructor, IsInstructorOrReadOnly
from core.views.mixins import InstanceScopedMixin
from core.models import (
    Team, User, Round, SimulationState,
    SimulationSettings, SimulationParameters, ComponentStatus,
)
from core.serializers import (
    TeamSerializer, RoundSerializer,
    SimulationStateSerializer, SimulationSettingsSerializer,
    SimulationParametersSerializer, ComponentStatusSerializer,
    DashboardSerializer,
    UserSerializer, UserWriteSerializer,
)


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [IsInstructorOrReadOnly]


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related('team').all()
    permission_classes = [IsInstructor]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return UserWriteSerializer
        return UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
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
            return Response({'error': 'No CSV data provided.'},
                            status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(io.StringIO(csv_text))
        created = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):
            username = (row.get('username') or '').strip()
            if not username:
                errors.append({'row': row_num, 'error': 'Missing username'})
                continue

            role = (row.get('role') or 'Student').strip()
            team_id = (row.get('team_id') or '').strip() or None
            password = (row.get('password') or '').strip()

            if team_id:
                try:
                    team_id = int(team_id)
                except ValueError:
                    errors.append({'row': row_num,
                                   'error': f'Invalid team_id: {team_id}'})
                    continue

            password_hash = ''
            if password:
                password_hash = hashlib.sha256(password.encode()).hexdigest()

            try:
                User.objects.create(
                    username=username,
                    role=role,
                    team_id=team_id,
                    password_hash=password_hash,
                )
                created += 1
            except Exception as e:
                errors.append({'row': row_num, 'error': str(e)})

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
                user.team = team
            except (Team.DoesNotExist, ValueError, TypeError):
                return Response({'error': 'Team not found.'},
                                status=status.HTTP_404_NOT_FOUND)
        else:
            user.team = None

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

    @action(detail=True, methods=['post'], permission_classes=[IsInstructor])
    def advance(self, request, pk=None):
        """Advance the simulation by one round."""
        from core.services.round_engine import advance_round
        state = self.get_object()
        try:
            result = advance_round(state.state_id)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class SimulationSettingsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SimulationSettings.objects.all()
    serializer_class = SimulationSettingsSerializer


class SimulationParametersViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SimulationParameters.objects.all()
    serializer_class = SimulationParametersSerializer


class ComponentStatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ComponentStatus.objects.all()
    serializer_class = ComponentStatusSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        return qs


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
            return Response({'error': 'team_id is required'}, status=400)

        try:
            team_id = int(team_id)
        except ValueError:
            return Response({'error': 'team_id must be an integer'}, status=400)

        instance_id = self._get_instance_id(request)

        from core.models import (
            Team, SimulationState, TeamIncomeStatement,
            Program, Score, TeamPerformance,
        )

        try:
            team = Team.objects.get(pk=team_id)
        except Team.DoesNotExist:
            return Response({'error': 'Team not found'}, status=404)

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
