"""
CC-32F: AI Government Agent API Endpoints.
"""
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team
from core.models.cc32f_models import (
    GovernmentProfile, GovernmentSatisfaction, GovernmentAction,
)
from core.utils.localization import get_localized_field, get_user_language


class GovernmentRelationsView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/government-relations/"""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)

        profiles = GovernmentProfile.objects.filter(
            scenario=game.scenario,
        ).select_related('market')

        result = []
        for gp in profiles:
            is_home = (team.home_market_id and team.home_market_id == gp.market_id)

            sat = GovernmentSatisfaction.objects.filter(
                game=game, team=team, market=gp.market,
            ).first()

            # Recent actions for this team in this market
            recent_actions = GovernmentAction.objects.filter(
                game=game, market=gp.market,
            ).filter(
                # Team-specific or market-wide
                **({'target_team__in': [team, None]}
                   if False else {}),
            ).order_by('-created_at')[:5]

            actions_list = []
            for a in recent_actions:
                if a.target_team_id is not None and a.target_team_id != team.id:
                    continue  # Skip actions targeted at other teams
                actions_list.append({
                    'round': a.round.round_number if a.round else None,
                    'action_type': a.action_type,
                    'narrative': a.narrative,
                    'parameters': a.parameters,
                    'target_is_me': a.target_team_id == team.id if a.target_team_id else False,
                })

            # Get all actions for this team in this market (for procurement history)
            procurement_history = GovernmentAction.objects.filter(
                game=game, market=gp.market,
                action_type='PROCUREMENT_AWARD',
                target_team=team,
            ).order_by('-round__round_number').values_list(
                'round__round_number', 'parameters',
            )[:5]

            result.append({
                'market_code': gp.market.code,
                'market_name': get_localized_field(gp.market, 'name', language),
                'is_home_market': is_home,
                'government_name': get_localized_field(gp, 'name', language),
                'description': get_localized_field(gp, 'description', language),
                'policy_priorities': gp.policy_priorities,
                'incentive_threshold': float(gp.incentive_threshold),
                'warning_threshold': float(gp.warning_threshold),
                'restriction_threshold': float(gp.restriction_threshold),
                'procurement_frequency': gp.procurement_frequency,
                'patience_rounds': gp.patience_rounds,
                'satisfaction': float(sat.satisfaction) if sat else None,
                'objective_scores': sat.objective_scores if sat else {},
                'status': sat.status if sat else 'NEUTRAL',
                'rounds_below_warning': sat.rounds_below_warning if sat else 0,
                'rounds_below_restriction': sat.rounds_below_restriction if sat else 0,
                'active_incentive': sat.active_incentive if sat else None,
                'active_restriction': sat.active_restriction if sat else None,
                'recent_actions': actions_list,
                'procurement_history': [
                    {'round': r, 'parameters': p}
                    for r, p in procurement_history
                ],
            })

        return Response({'government_relations': result})
