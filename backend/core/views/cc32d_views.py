"""
CC-32D: AI Alliance Partners API Endpoints.
"""
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team
from core.models.cc32d_models import TeamAllianceState
from core.utils.localization import get_localized_field, get_user_language


class AllianceStateView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/alliances/"""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        alliances = TeamAllianceState.objects.filter(
            game=game, team=team,
        ).exclude(status='DISSOLVED').select_related('partner_profile', 'market')

        result = []
        for a in alliances:
            p = a.partner_profile
            result.append({
                'id': a.id,
                'partner_name': get_localized_field(p, 'name', language),
                'partner_type': p.partner_type,
                'partnership_code': p.partnership_code,
                'market_code': a.market.code,
                'market_name': get_localized_field(a.market, 'name', language),
                'description': get_localized_field(p, 'description', language),
                'satisfaction': float(a.satisfaction),
                'feature_satisfaction': a.feature_satisfaction or {},
                'preferences': p.preferences,
                'status': a.status,
                'benefit_delivery_pct': float(a.benefit_delivery_pct),
                'renegotiation_demands': a.renegotiation_demands,
                'renegotiation_threshold': float(p.renegotiation_threshold),
                'satisfaction_floor': float(p.satisfaction_floor),
                'patience_rounds': p.patience_rounds,
                'rounds_below_renegotiation': a.rounds_below_renegotiation,
                'rounds_below_dissolution': a.rounds_below_dissolution,
                'benefit_curve': p.benefit_curve,
                'established_round': a.established_round,
            })

        # Also include dissolved alliances for notification display
        dissolved = TeamAllianceState.objects.filter(
            game=game, team=team, status='DISSOLVED',
        ).select_related('partner_profile', 'market')

        dissolved_list = []
        for a in dissolved:
            p = a.partner_profile
            dissolved_list.append({
                'partner_name': get_localized_field(p, 'name', language),
                'partner_type': p.partner_type,
                'market_code': a.market.code,
                'market_name': get_localized_field(a.market, 'name', language),
                'dissolved_round': a.dissolved_round,
            })

        return Response({
            'alliances': result,
            'dissolved': dissolved_list,
        })
