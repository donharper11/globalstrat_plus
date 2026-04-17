"""
CC-31A: Origin-Trust Framework API Endpoints.
D1: Talent allocation context
D2: Compliance investment context
D3: Market localization summary
"""
import math
from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team
from core.models.cc31_models import (
    CulturalDistanceMatrix, TeamMarketCompliance, TalentAllocation,
)
from core.models.team_state import TeamMarketPresence
from core.models.decisions import DecisionSubmission
from core.models.talent import TeamTalentState
from core.utils.localization import get_localized_field, get_user_language


def _get_team(team_id):
    return get_object_or_404(Team, pk=team_id)


class TalentAllocationContextView(APIView):
    """D1: GET — talent allocation context for decision UI."""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        team = _get_team(team_id)
        game = get_object_or_404(Game, pk=game_id)
        scenario = game.scenario

        current_round = game.current_round
        prev_round = current_round - 1

        # Current headcount per pool
        pools = {}
        for pool in ['rd', 'commercial', 'operations']:
            state = TeamTalentState.objects.filter(
                team=team, talent_pool=pool, round_number=prev_round,
            ).first()
            pools[pool] = {
                'headcount': state.headcount if state else 0,
                'talent_level': float(state.talent_level) if state else 3.0,
            }

        # Active markets with cultural distance
        presences = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).select_related('market')

        markets = []
        for p in presences:
            distance = CulturalDistanceMatrix.objects.filter(
                scenario=scenario,
                from_market=team.home_market,
                to_market=p.market,
            ).first() if team.home_market_id else None

            compliance = TeamMarketCompliance.objects.filter(
                game=game, team=team, market=p.market,
            ).first()

            markets.append({
                'code': p.market.code,
                'name': get_localized_field(p.market, 'name', language),
                'market_id': p.market.id,
                'is_home_market': team.home_market_id == p.market.id if team.home_market_id else False,
                'distance_level': distance.distance_level if distance else 'HOME',
                'base_effectiveness': float(distance.base_effectiveness) if distance else 1.0,
                'effective_rd_multiplier': float(compliance.effective_rd_multiplier) if compliance else 1.0,
                'effective_commercial_multiplier': float(compliance.effective_commercial_multiplier) if compliance else 1.0,
                'effective_operations_multiplier': float(compliance.effective_operations_multiplier) if compliance else 1.0,
            })

        # Current draft allocations
        from core.models.core import Round
        rnd = Round.objects.filter(game=game, round_number=current_round).first()
        draft_allocations = {}
        if rnd:
            sub = DecisionSubmission.objects.filter(team=team, round=rnd).first()
            if sub:
                for alloc in TalentAllocation.objects.filter(submission=sub):
                    draft_allocations[alloc.talent_pool] = {
                        'hq_count': alloc.hq_count,
                        'market_allocation': alloc.market_allocation,
                    }

        from core.engine.utils import get_config
        hq_baseline = int(get_config(scenario, 'localization_staff_baseline', default=10))

        return Response({
            'pools': pools,
            'markets': markets,
            'draft_allocations': draft_allocations,
            'localization_staff_baseline': hq_baseline,
            'home_market': {
                'code': team.home_market.code,
                'name': get_localized_field(team.home_market, 'name', language),
            } if team.home_market else None,
        })


class ComplianceContextView(APIView):
    """D2: GET — compliance investment context for decision UI."""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        team = _get_team(team_id)
        game = get_object_or_404(Game, pk=game_id)
        scenario = game.scenario

        presences = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).select_related('market')

        from core.engine.utils import get_config
        scale_factor = float(get_config(scenario, 'compliance_scale_factor', default=5000000))

        markets = []
        for p in presences:
            compliance = TeamMarketCompliance.objects.filter(
                game=game, team=team, market=p.market,
            ).first()

            current_level = float(compliance.compliance_level) if compliance else 0.0
            cumulative = float(compliance.cumulative_investment) if compliance else 0.0
            trust = float(compliance.current_trust_multiplier) if compliance else 1.0

            # What the next $1M buys
            next_level = 1 - math.exp(-(cumulative + 1000000) / scale_factor)
            marginal_gain = next_level - current_level

            markets.append({
                'code': p.market.code,
                'name': get_localized_field(p.market, 'name', language),
                'market_id': p.market.id,
                'compliance_level': current_level,
                'cumulative_investment': cumulative,
                'current_trust_multiplier': trust,
                'next_1m_compliance_gain': round(marginal_gain, 4),
            })

        return Response({
            'markets': markets,
            'scale_factor': scale_factor,
        })


class MarketLocalizationView(APIView):
    """D3: GET — market localization summary (read-only)."""

    def get(self, request, game_id, team_id, market_code):
        language = get_user_language(request)
        team = _get_team(team_id)
        game = get_object_or_404(Game, pk=game_id)
        scenario = game.scenario

        from core.models.scenario import MarketDefinition
        market = get_object_or_404(MarketDefinition, scenario=scenario, code=market_code)

        # Distance
        distance = CulturalDistanceMatrix.objects.filter(
            scenario=scenario,
            from_market=team.home_market,
            to_market=market,
        ).first() if team.home_market_id else None

        # Compliance
        compliance = TeamMarketCompliance.objects.filter(
            game=game, team=team, market=market,
        ).first()

        # Talent allocation
        current_round = game.current_round
        sub = DecisionSubmission.objects.filter(
            team=team,
            round__round_number=current_round,
            round__game=game,
        ).first()

        allocations = {}
        if sub:
            for alloc in TalentAllocation.objects.filter(submission=sub):
                allocations[alloc.talent_pool] = {
                    'hq_count': alloc.hq_count,
                    'market_count': alloc.market_allocation.get(market_code, 0),
                }

        # Global talent levels (for display: "3.12 (65% of 4.8 global)")
        prev_round = max(current_round - 1, 0)
        global_talent = {}
        for pool in ['rd', 'commercial', 'operations']:
            state = TeamTalentState.objects.filter(
                team=team, talent_pool=pool, round_number=prev_round,
            ).first()
            global_talent[pool] = float(state.talent_level) if state else 3.0

        is_home = team.home_market_id == market.id if team.home_market_id else False

        return Response({
            'is_home_market': is_home,
            'home_market': {
                'code': team.home_market.code,
                'name': get_localized_field(team.home_market, 'name', language),
            } if team.home_market else None,
            'distance': {
                'level': 'HOME' if is_home else (distance.distance_level if distance else 'UNKNOWN'),
                'base_effectiveness': 1.0 if is_home else (float(distance.base_effectiveness) if distance else 1.0),
                'repatriation_cost_pct': 0.0 if is_home else (float(distance.repatriation_cost_pct) if distance else 0.0),
            },
            'talent_allocation': allocations,
            'global_talent_levels': global_talent,
            'effective_multipliers': {
                'rd': global_talent['rd'] if is_home else (float(compliance.effective_rd_multiplier) if compliance else 1.0),
                'commercial': global_talent['commercial'] if is_home else (float(compliance.effective_commercial_multiplier) if compliance else 1.0),
                'operations': global_talent['operations'] if is_home else (float(compliance.effective_operations_multiplier) if compliance else 1.0),
            },
            'compliance_level': 0.0 if is_home else (float(compliance.compliance_level) if compliance else 0.0),
            'trust_multiplier': 1.0 if is_home else (float(compliance.current_trust_multiplier) if compliance else 1.0),
            'rounds_present': compliance.rounds_present if compliance else 0,
        })
