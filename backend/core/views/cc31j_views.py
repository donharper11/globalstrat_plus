"""
CC-31J: Governance Commitments API.

Provides commitment type definitions (costs, benefits, interactions)
and current team governance state for the frontend.
"""
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models.core import Game, Team
from core.models.cc31_models import GovernanceCommitmentType, TeamGovernanceCommitment
from core.models.team_state import TeamMarketPresence
from core.models.decisions import DecisionSubmission, DecisionESG
from core.utils.localization import get_localized_field, get_user_language


class GovernanceContextView(APIView):
    """GET /api/games/{game_id}/teams/{team_id}/context/governance/"""

    def get(self, request, game_id, team_id):
        language = get_user_language(request)
        game = get_object_or_404(Game, id=game_id)
        team = get_object_or_404(Team, id=team_id, game=game)
        scenario = game.scenario

        # Commitment type definitions
        types = GovernanceCommitmentType.objects.filter(scenario=scenario)
        commitment_defs = []
        for ct in types:
            commitment_defs.append({
                'code': ct.code,
                'name': get_localized_field(ct, 'name', language),
                'description': get_localized_field(ct, 'description', language),
                'ongoing_cost_per_round': float(ct.ongoing_cost_per_round),
                'benefits': ct.benefits or [],
                'interactions': ct.interactions or [],
                'revocation_penalty': ct.revocation_penalty or {},
                'prerequisite': ct.prerequisite,
                'amplifier': ct.amplifier,
                'display_order': ct.display_order,
            })

        # Current team governance state
        team_state = {}
        for tgc in TeamGovernanceCommitment.objects.filter(
            game=game, team=team,
        ).select_related('commitment_type'):
            team_state[tgc.commitment_type.code] = {
                'is_active': tgc.is_active,
                'activated_round': tgc.activated_round,
                'revoked_round': tgc.revoked_round,
                'penalty_rounds_remaining': tgc.penalty_rounds_remaining,
            }

        # Current interaction conditions (so frontend can show warnings)
        interaction_warnings = _evaluate_all_interactions(team, game)

        # Cumulative ESG investment for greenwashing check
        cumulative_esg = 0
        subs = DecisionSubmission.objects.filter(
            team=team, round__game=game,
        ).order_by('round__round_number')
        for sub in subs:
            try:
                esg = sub.esg
                if esg:
                    cumulative_esg += float(esg.environmental_investment or 0)
                    cumulative_esg += float(esg.social_investment or 0)
            except Exception:
                pass

        return Response({
            'commitment_types': commitment_defs,
            'team_state': team_state,
            'interaction_warnings': interaction_warnings,
            'cumulative_esg_investment': cumulative_esg,
        })


def _evaluate_all_interactions(team, game):
    """Evaluate interaction conditions and return warnings for the frontend."""
    warnings = {}

    # Check salary levels (for pay_transparency)
    sub = DecisionSubmission.objects.filter(
        team=team, round__game=game, round__round_number=game.current_round,
    ).first()
    below_market_pools = []
    if sub:
        try:
            talent = sub.talent
            for pool, level in [('R&D', talent.rd_salary_level),
                                ('Commercial', talent.commercial_salary_level),
                                ('Operations', talent.operations_salary_level)]:
                if level < 2:
                    below_market_pools.append(pool)
        except Exception:
            pass

    if below_market_pools:
        warnings['pay_transparency'] = {
            'active': True,
            'message': f'Your {", ".join(below_market_pools)} salary is Below Market. Pay transparency is exposing the gap \u2014 turnover increased +5%. Raise salaries to Market Rate or above to resolve.',
        }

    # Check JV entry mode (for anti_corruption)
    jv_markets = list(
        TeamMarketPresence.objects.filter(
            team=team, status='active', entry_mode__code='jv',
        ).values_list('market__name', flat=True)
    )
    if jv_markets:
        warnings['anti_corruption'] = {
            'active': True,
            'message': f'You have JV partnerships in {", ".join(jv_markets)}. Anti-corruption monitoring adds $100K/round per JV market.',
        }

    # Check contract manufacturing (for supply_chain_audit)
    contract_mfg_markets = list(
        TeamMarketPresence.objects.filter(
            team=team, status='active', market__contract_mfg_available=True,
        ).values_list('market__name', flat=True)
    )
    if contract_mfg_markets:
        warnings['supply_chain_audit'] = {
            'active': True,
            'message': f'You use contract manufacturing in {", ".join(contract_mfg_markets)}. Audit may expose labor concerns (15% probability per round).',
        }

    # Check cumulative ESG investment (for public_esg_reporting greenwashing)
    cumulative = 0
    if sub:
        try:
            esg = sub.esg
            if esg:
                cumulative = float(esg.environmental_investment or 0) + float(esg.social_investment or 0)
        except Exception:
            pass
    if cumulative < 1_000_000:
        warnings['public_esg_reporting'] = {
            'active': True,
            'message': f'Total ESG investment is only ${cumulative:,.0f}. Reporting without substance is seen as greenwashing. Increase environmental/social investment above $1M or remove this commitment.',
        }

    return warnings
