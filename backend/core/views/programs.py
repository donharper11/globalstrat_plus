from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.views.mixins import InstanceScopedMixin, DecisionLockedMixin
from core.models import (
    Program, ProgramType, ProgramPortfolio, ProgramFeature,
    Decision,
)
from core.serializers import (
    ProgramSerializer, ProgramTypeSerializer,
    ProgramPortfolioSerializer, ProgramFeatureSerializer,
    DecisionSerializer,
)


# ---------------------------------------------------------------------------
# Core program tables
# ---------------------------------------------------------------------------

# TODO: GlobalStrat — FeaturesViewSet removed, update to use new scenario models (CC-3)


class ProgramTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProgramType.objects.all()
    serializer_class = ProgramTypeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        economy_id = self.request.query_params.get('economy_id')
        if economy_id:
            # Traditional types have economy_id=NULL in DB; treat economy_id=1 as NULL
            if str(economy_id) == '1':
                qs = qs.filter(economy_id__isnull=True)
            else:
                qs = qs.filter(economy_id=economy_id)
        # Filter to only types that have at least one feature (direct or via mapping)
        # TODO: GlobalStrat — update to use new scenario models (CC-3)
        # has_features filter removed — Feature model removed
        return qs


class ProgramViewSet(DecisionLockedMixin, InstanceScopedMixin, viewsets.ModelViewSet):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        status_param = self.request.query_params.get('status')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def create(self, request, *args, **kwargs):
        team_id = request.data.get('team_id')
        prog_status = request.data.get('status', '')
        if team_id and prog_status and prog_status.lower() == 'active':
            from core.services.budget import validate_program_activation
            ok, warnings, errors = validate_program_activation(int(team_id))
            if not ok:
                return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
        response = super().create(request, *args, **kwargs)

        # Apply R&D development time to newly created platform
        if response.status_code == 201:
            try:
                from core.services.r_and_d import apply_development_time
                program_id = response.data.get('program_id')
                if program_id:
                    platform = Program.objects.get(pk=program_id)
                    dev_rounds = apply_development_time(platform)
                    # Refresh serialized data
                    response.data = ProgramSerializer(
                        platform, context={'request': request}
                    ).data
            except Exception:
                pass  # R&D is non-critical; platform still created

        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_status = request.data.get('status', '')
        old_status = instance.status or ''
        if new_status.lower() == 'active' and old_status.lower() != 'active':
            team_id = instance.team_id
            if team_id:
                from core.services.budget import validate_program_activation
                ok, warnings, errors = validate_program_activation(int(team_id))
                if not ok:
                    return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='accelerate')
    def accelerate(self, request, pk=None):
        """Spend R&D budget to reduce development time by 1 round."""
        platform = self.get_object()
        team_id = platform.team_id
        if not team_id:
            return Response(
                {'error': 'Platform has no team_id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from core.services.r_and_d import accelerate_development
        result = accelerate_development(platform, team_id)
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        # Return updated platform data
        platform.refresh_from_db()
        result['platform'] = ProgramSerializer(
            platform, context={'request': request}
        ).data
        return Response(result)

    @action(detail=False, methods=['get'], url_path='budget-status')
    def budget_status(self, request):
        """Return CSR budget, committed costs, program cap, and loan status."""
        team_id = request.query_params.get('team_id')
        if not team_id:
            return Response({'error': 'team_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        from core.services.budget import get_budget_status
        from core.models import SimulationState
        state = SimulationState.objects.filter(status='active').first()
        round_id = state.current_round_id if state else None
        result = get_budget_status(int(team_id), round_id)
        return Response(result)


class ProgramPortfolioViewSet(viewsets.ModelViewSet):
    queryset = ProgramPortfolio.objects.all()
    serializer_class = ProgramPortfolioSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        program_id = self.request.query_params.get('program_id')
        if program_id:
            qs = qs.filter(program_id=program_id)
        return qs

    def create(self, request, *args, **kwargs):
        # Block program creation from platforms still in development
        program_id = request.data.get('program_id')
        if program_id:
            platform = Program.objects.filter(program_id=program_id).first()
            if platform and getattr(platform, 'development_status', 'ready') == 'developing':
                remaining = platform.development_rounds_remaining or 0
                return Response(
                    {'error': (
                        f'Platform "{platform.program_name}" is still in '
                        f'development. {remaining} round(s) remaining.'
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return super().create(request, *args, **kwargs)


class ProgramFeatureViewSet(viewsets.ModelViewSet):
    queryset = ProgramFeature.objects.all()
    serializer_class = ProgramFeatureSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        program_id = self.request.query_params.get('program_id')
        program_portfolio_id = self.request.query_params.get('program_portfolio_id')
        if program_id:
            qs = qs.filter(program_id=program_id)
        if program_portfolio_id:
            qs = qs.filter(program_portfolio_id=program_portfolio_id)
        return qs


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

class DecisionViewSet(InstanceScopedMixin, viewsets.ModelViewSet):
    queryset = Decision.objects.all()
    serializer_class = DecisionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        team_id = self.request.query_params.get('team_id')
        round_id = self.request.query_params.get('round_id')
        if team_id:
            qs = qs.filter(team_id=team_id)
        if round_id:
            qs = qs.filter(round_id=round_id)
        return qs
