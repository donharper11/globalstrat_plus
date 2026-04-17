"""
CC-31: Instructor team configuration endpoints.
1a. PUT  /api/games/<game_id>/instructor/team-config/
1b. POST /api/games/<game_id>/instructor/randomize-home-markets/
"""
import random

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team, Round
from core.models.scenario import MarketDefinition
from core.models.decisions import DecisionSubmission
from core.permissions import IsInstructor
from core.utils.localization import get_localized_field, get_user_language


def _team_payload(team, language='en'):
    """Serialize a team for the response."""
    return {
        'team_id': team.id,
        'team_name': team.name,
        'home_market_id': team.home_market_id,
        'home_market_code': team.home_market.code if team.home_market else None,
        'home_market_name': get_localized_field(team.home_market, 'name', language) if team.home_market else None,
        'starter_profile_name': get_localized_field(team.firm_starter_profile, 'profile_name', language) if team.firm_starter_profile_id else None,
    }


def _has_round1_submissions(game):
    """Return True if any team has a Round 1 decision submission."""
    round1 = Round.objects.filter(game=game, round_number=1).first()
    if not round1:
        return False
    return DecisionSubmission.objects.filter(
        team__game=game, round=round1,
    ).exists()


class InstructorTeamConfigView(APIView):
    """
    GET  — return current team list with home market assignments.
    PUT  — update home market assignments for teams.
    """
    permission_classes = [IsInstructor]

    def get(self, request, game_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        teams = Team.objects.filter(game=game).select_related('home_market', 'firm_starter_profile').order_by('id')
        markets = MarketDefinition.objects.filter(scenario=game.scenario).order_by('display_order', 'name')

        return Response({
            'teams': [_team_payload(t, language) for t in teams],
            'available_markets': [
                {
                    'id': m.id,
                    'code': m.code,
                    'name': get_localized_field(m, 'name', language),
                    'description': get_localized_field(m, 'description', language),
                    'base_growth_rate': float(m.base_growth_rate),
                    'tax_rate': float(m.tax_rate),
                    'tariff_rate': float(m.tariff_rate),
                    'regulatory_difficulty': float(m.regulatory_difficulty),
                    'infrastructure_quality': float(m.infrastructure_quality),
                    'entry_cost_base': float(m.entry_cost_base),
                    'currency_code': m.currency_code,
                    'exchange_rate_volatility': float(m.exchange_rate_volatility),
                }
                for m in markets
            ],
            'locked': _has_round1_submissions(game),
        })

    def put(self, request, game_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)

        # Validation: cannot change after first Round 1 submission exists
        if _has_round1_submissions(game):
            return Response(
                {'error': 'Cannot change home markets after Round 1 decisions have been submitted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        teams_data = request.data.get('teams', [])
        if not teams_data:
            return Response(
                {'error': 'No teams provided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build lookup of valid market codes for this scenario
        valid_markets = {
            m.code: m
            for m in MarketDefinition.objects.filter(scenario=game.scenario)
        }

        teams = Team.objects.filter(game=game).select_related('home_market', 'firm_starter_profile')
        team_map = {t.id: t for t in teams}

        _MISSING = object()
        updated = []
        for entry in teams_data:
            team_id = entry.get('team_id')
            market_code = entry.get('home_market_code', _MISSING)

            team = team_map.get(team_id)
            if not team:
                return Response(
                    {'error': f'Team {team_id} not found in this game.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            save_fields = []

            # Allow renaming the team
            new_name = entry.get('team_name')
            if new_name is not None:
                new_name = str(new_name).strip()
                if new_name and new_name != team.name:
                    team.name = new_name
                    save_fields.append('name')

            if market_code is not _MISSING:
                if market_code is None:
                    team.home_market = None
                    save_fields.append('home_market')
                else:
                    market = valid_markets.get(market_code)
                    if not market:
                        return Response(
                            {'error': f'Invalid market code "{market_code}" for this scenario. '
                                      f'Valid codes: {", ".join(sorted(valid_markets.keys()))}'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if team.home_market != market:
                        team.home_market = market
                        save_fields.append('home_market')

            if save_fields:
                team.save(update_fields=save_fields)
            updated.append(_team_payload(team, language))

        return Response({'teams': updated})


class InstructorRandomizeHomeMarketsView(APIView):
    """
    POST — randomly assign home markets to teams (preview only, does NOT save).
    If teams <= markets, unique assignment; otherwise random with replacement.
    """
    permission_classes = [IsInstructor]

    def post(self, request, game_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        teams = Team.objects.filter(game=game).order_by('id')
        markets = list(
            MarketDefinition.objects.filter(scenario=game.scenario)
            .order_by('display_order', 'name')
        )

        if not markets:
            return Response(
                {'error': 'No markets defined for this scenario.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team_count = teams.count()
        if team_count <= len(markets):
            # Unique assignment (sample without replacement)
            assigned = random.sample(markets, team_count)
        else:
            # Random with replacement
            assigned = [random.choice(markets) for _ in range(team_count)]

        preview = []
        for team, market in zip(teams, assigned):
            preview.append({
                'team_id': team.id,
                'team_name': team.name,
                'home_market_id': market.id,
                'home_market_code': market.code,
                'home_market_name': get_localized_field(market, 'name', language),
            })

        return Response({
            'preview': preview,
            'saved': False,
        })
